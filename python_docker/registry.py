import json
import gzip
import time
import functools
import base64
from urllib.parse import urlparse, parse_qs

import requests

from python_docker.base import Image, Layer
from python_docker import schema


def ttlhash(seconds=60):
    return int(time.time() // seconds)


def basic_authentication(username, password, *args, **kwargs):
    credentials = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode(
        "utf-8"
    )
    return {"headers": {"Authorization": f"Basic {credentials}"}}


def dockerhub_authentication(*args, **kwargs):
    query = {
        "service": "registry.docker.io",
    }

    if "image" in kwargs and "action" in kwargs:
        query["scope"] = f"repository:{kwargs['image']}:{kwargs['action']}"

    base_url = "https://auth.docker.io/token"
    if query:
        base_url += "?" + "&".join(f"{key}={value}" for key, value in query.items())

    token = requests.get(base_url).json()["token"]
    return {
        "headers": {
            "Authorization": f"Bearer {token}",
        }
    }


class Registry:
    def __init__(
        self,
        hostname="https://registry-1.docker.io",
        authentication=dockerhub_authentication,
        ttl=60,
    ):
        self.hostname = hostname

        self.authentication_method = None
        if authentication:

            @functools.lru_cache(maxsize=None)
            def _authentication_method(ttlhash, *args, **kwargs):
                return authentication(*args, **kwargs)

            self.authentication_method = _authentication_method
        self.ttl = ttl

    def request(
        self, url: str, method="GET", headers=None, params=None, data=None, **kwargs
    ):
        method_map = {
            "HEAD": requests.head,
            "GET": requests.get,
            "POST": requests.post,
            "PUT": requests.put,
            "DELETE": requests.delete,
        }

        headers = headers or {}
        if self.authentication_method:
            credentials = self.authentication_method(
                ttlhash=ttlhash(self.ttl), **kwargs
            )
            headers.update(credentials["headers"])

        return method_map[method](
            f"{self.hostname}{url}", headers=headers, params=params, data=data
        )

    def authenticated(self):
        response = self.request("/v2/")
        return response.status_code != 401

    def get_manifest(self, image: str, tag: str, version="v1"):
        version_map = {
            "v1": "application/vnd.docker.distribution.manifest.v1+json",
            "v2": "application/vnd.docker.distribution.manifest.v2+json",
        }

        if version not in version_map:
            raise ValueError(f"manifest version={version} not supported")

        response = self.request(
            f"/v2/{image}/manifests/{tag}",
            image=image,
            action="pull",
            headers={"Accept": version_map[version]},
        )

        response.raise_for_status()
        data = response.json()
        if version == "v1":
            return schema.DockerManifestV1.parse_obj(data)
        elif version == "v2":
            return schema.DockerManifestV2.parse_obj(data)

    def get_manifest_configuration(self, image: str, tag: str):
        manifestV2 = self.get_manifest(image, tag, version="v2")
        config_data = json.loads(self.get_blob(image, manifestV2.config.digest))
        return schema.DockerConfig.parse_obj(config_data)

    def get_manifest_digest(self, image: str, tag: str):
        response = self.request(
            f"/v2/{image}/manifests/{tag}",
            method="HEAD",
            image=image,
            action="pull",
            headers={"Accept": "application/vnd.docker.distribution.manifest.v2+json"},
        )
        response.raise_for_status()
        return response.headers["Docker-Content-Digest"]

    def check_blob(self, image: str, blobsum: str):
        response = self.request(
            f"/v2/{image}/blobs/{blobsum}", method="HEAD", image=image, action="pull"
        )
        return response.status_code == 200

    def get_blob(self, image: str, blobsum: str):
        response = self.request(
            f"/v2/{image}/blobs/{blobsum}", image=image, action="pull"
        )
        response.raise_for_status()
        return response.content

    def begin_upload(self, image: str):
        response = self.request(
            f"/v2/{image}/blobs/uploads/", method="POST", image=image, action="push"
        )
        response.raise_for_status()
        location = urlparse(response.headers["Location"])
        return location.path, parse_qs(location.query)

    def upload_blob(self, image: str, digest, checksum):
        upload_location, upload_query = self.begin_upload(image)
        upload_query["digest"] = f"sha256:{checksum}"

        response = self.request(
            upload_location,
            method="PUT",
            data=digest,
            image=image,
            action="push",
            params=upload_query,
            headers={"Content-Type": "application/octet-stream"},
        )
        response.raise_for_status()

    def upload_manifest(self, image: str, tag: str, manifest: dict):
        manifest_config, manifest_config_checksum = manifest["config"]
        manifest, manifest_checksum = manifest["manifest"]

        if not self.check_blob(image, f"sha256:{manifest_config_checksum}"):
            self.upload_blob(image, manifest_config, manifest_config_checksum)

        response = self.request(
            f"/v2/{image}/manifests/{tag}",
            method="PUT",
            data=manifest,
            iamge=image,
            action="push",
            headers={
                "Content-Type": "application/vnd.docker.distribution.manifest.v2+json"
            },
        )
        response.raise_for_status()

    def list_images(self, n: int = None, last: int = None):
        query = {}
        if n is not None:
            query["n"] = n
        if last is not None:
            query["last"] = last

        return self.request("/v2/_catalog", params=query).json()["repositories"]

    def list_image_tags(self, image: str, n: int = None, last: int = None):
        query = {}
        if n is not None:
            query["n"] = n
        if last is not None:
            query["last"] = last

        return self.request(f"/v2/{image}/tags/list", params=query).json()["tags"]

    def pull_image(self, image: str, tag: str = "latest", lazy: bool = False):
        """Pull specific image from docker registry

        Crates an Image object with a list of ordered Layers
        inside. If `lazy` is set to True the layer content is not
        actually downloaded unless actually referenced. Useful if you
        are making small modifications to docker images adding a few
        layers.

        """

        def _get_layer_blob(image, blobsum):
            return gzip.decompress(self.get_blob(image, blobsum))

        manifest = self.get_manifest(image, tag, version="v2")
        manifest_config = self.get_manifest_configuration(image, tag)

        layers = []
        parent = None
        # traverse in reverse order so that parent id can be correct
        for diffid_checksum, layer in zip(
            manifest_config.rootfs.diff_ids[::-1], manifest.layers[::-1]
        ):
            checksum = diffid_checksum.split(":")[1]
            compressed_size = layer.size
            compressed_checksum = layer.digest.split(":")[1]

            if lazy:
                digest = functools.partial(_get_layer_blob, image, layer.digest)
            else:
                digest = _get_layer_blob(image, layer.digest)

            layers.insert(
                0,
                Layer(
                    id=checksum,
                    parent=parent,
                    architecture=manifest_config.architecture,
                    os=manifest_config.os,
                    created=manifest_config.created,
                    author=None,
                    config=manifest_config.config.dict(),
                    content=digest,
                    checksum=checksum,
                    compressed_size=compressed_size,
                    compressed_checksum=compressed_checksum,
                ),
            )

            parent = checksum
        return Image(image, tag, layers)

    def push_image(self, image: Image):
        for layer in image.layers:
            # make sure to check if the layer already exists on the
            # registry this way if the layer is lazy (has not actually
            # been downloaded) it does not have to be downloaded
            if not self.check_blob(image.name, f"sha256:{layer.compressed_checksum}"):
                self.upload_blob(
                    image.name, layer.compressed_content, layer.compressed_checksum
                )

        self.upload_manifest(image.name, image.tag, image.manifest_v2)

    def delete_image(self, image, tag):
        digest = self.get_manifest_digest(image, tag)
        response = self.request(f"/v2/{image}/manifests/{digest}", method="DELETE")
        response.raise_for_status()

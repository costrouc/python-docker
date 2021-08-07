import json
import gzip
import time
import functools
import base64
from urllib.parse import urlparse, parse_qs

import requests

from python_docker.base import Image, Layer


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

    def get_manifest(self, image: str, tag: str):
        response = self.request(
            f"/v2/{image}/manifests/{tag}", image=image, action="pull"
        )
        response.raise_for_status()
        return response.json()

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
        return gzip.decompress(response.content)

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

    def pull_image(self, image: str, tag: str = "latest"):
        manifest = self.get_manifest(image, tag)

        layers = []
        for metadata, blob in zip(manifest["history"], manifest["fsLayers"]):
            d = json.loads(metadata["v1Compatibility"])
            digest = self.get_blob(image, blob["blobSum"])

            layers.append(
                Layer(
                    id=d["id"],
                    parent=d.get("parent"),
                    architecture=d.get("architecture"),
                    os=d.get("os"),
                    created=d.get("created"),
                    author=d.get("author"),
                    config=d.get("config"),
                    content=digest,
                )
            )
        return Image(image, tag, layers)

    def push_image(self, image: Image):
        for layer in image.layers:
            self.upload_blob(
                image.name, layer.compressed_content, layer.compressed_checksum
            )

        self.upload_manifest(image.name, image.tag, image.manifest_v2)

    def delete_image(self, image, tag):
        digest = self.get_manifest_digest(image, tag)
        response = self.request(f"/v2/{image}/manifests/{digest}", method="DELETE")
        response.raise_for_status()

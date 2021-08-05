from urllib.request import Request, urlopen
import json
import gzip
import time
import functools

from python_docker.base import Image, Layer


def ttlhash(seconds=60):
    return int(time.time() // seconds)


def dockerhub_authenticate(image, action="pull"):
    scope = f"repository:{image}:pull"
    url = f"https://auth.docker.io/token?service=registry.docker.io&scope={scope}"
    token = json.loads(get_request(url).decode("utf-8"))["token"]
    return {
        "headers": {
            "Authorization": f"Bearer {token}",
        }
    }


def get_request(url, headers=None):
    headers = headers or {}

    request = Request(url)
    for key, value in headers.items():
        request.add_header(key, value)

    return urlopen(request).read()


def get_json_request(url, headers=None):
    return json.loads(get_request(url, headers).decode("utf-8"))


class Registry:
    def __init__(
        self,
        hostname="https://registry-1.docker.io",
        authentication_method=dockerhub_authenticate,
        ttl=60,
    ):
        self.hostname = hostname

        self.authentication_method = None
        if authentication_method:

            @functools.cache
            def _authentication_method(image, action, ttlhash):
                return authentication_method(image, action)

            self.authentication_method = _authentication_method

        self.ttl = ttl

    def get_manifest(self, image, tag):
        headers = {}
        if self.authentication_method:
            credentials = self.authentication_method(image, "pull", ttlhash(self.ttl))
            headers.update(credentials["headers"])

        url = f"{self.hostname}/v2/{image}/manifests/{tag}"
        return get_json_request(url, headers)

    def get_blob(self, image, blobsum):
        headers = {}
        if self.authentication_method:
            credentials = self.authentication_method(image, "pull", ttlhash(self.ttl))
            headers.update(credentials["headers"])

        url = f"{self.hostname}/v2/{image}/blobs/{blobsum}"
        return gzip.decompress(get_request(url, headers))

    def pull_image(self, image, tag="latest"):
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

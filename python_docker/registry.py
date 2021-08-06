from urllib.request import Request, urlopen
from urllib import error
import json
import gzip
import time
import functools
import base64

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

    print(base_url)

    token = json.loads(get_request(base_url).decode("utf-8"))["token"]
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

    def authenticated(self):
        headers = {}
        if self.authentication_method:
            credentials = self.authentication_method(ttlhash=ttlhash(self.ttl))
            headers.update(credentials["headers"])

        try:
            url = f"{self.hostname}/v2/"
            get_request(url, headers)
            return True
        except error.HTTPError:
            return False

    def get_manifest(self, image, tag):
        headers = {}
        if self.authentication_method:
            credentials = self.authentication_method(
                image=image, action="pull", ttlhash=ttlhash(self.ttl)
            )
            headers.update(credentials["headers"])

        url = f"{self.hostname}/v2/{image}/manifests/{tag}"
        return get_json_request(url, headers)

    def get_blob(self, image, blobsum):
        headers = {}
        if self.authentication_method:
            credentials = self.authentication_method(
                image=image, action="pull", ttlhash=ttlhash(self.ttl)
            )
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

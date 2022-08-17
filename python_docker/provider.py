import os

from python_docker import registry


class DockerRegistry(registry.Registry):
    def __init__(
        self,
        hostname: str = "https://registry-1.docker.io",
        username: str = os.environ.get("DOCKER_USERNAME"),
        password: str = os.environ.get("DOCKER_PASSWORD"),
    ):
        super().__init__(hostname, username, password)

    def pull_image(self, image: str, tag: str = "latest", lazy: bool = False):
        if "/" not in image:
            image = "library/" + image

        return super().pull_image(image, tag, lazy)

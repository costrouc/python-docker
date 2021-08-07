import pytest
import functools

from python_docker import docker
from python_docker.registry import (
    Registry,
    basic_authentication,
    dockerhub_authentication,
)
from python_docker.base import Image


@pytest.mark.parametrize(
    "image_name, tag, layers",
    [
        ("library/hello-world", "latest", 2),
        ("library/busybox", "latest", 2),
    ],
)
def test_dockerhub_pull(image_name, tag, layers):
    registry = Registry()
    image = registry.pull_image(image_name, tag)
    assert image.name == image_name
    assert image.tag == tag
    assert len(image.layers) == layers


@pytest.mark.parametrize(
    "hostname, authentication",
    [
        ("http://localhost:5000", None),
        (
            "http://localhost:6000",
            functools.partial(basic_authentication, "admin", "password"),
        ),
        ("https://registry-1.docker.io", dockerhub_authentication),
    ],
)
def test_registry_authenticated(hostname, authentication):
    r = Registry(hostname, authentication)
    assert r.authenticated()


@pytest.mark.parametrize(
    "hostname, authentication",
    [
        (
            "http://localhost:6000",
            functools.partial(basic_authentication, "admin", "wrongpassword"),
        ),
    ],
)
def test_registry_not_authenticated(hostname, authentication):
    r = Registry(hostname, authentication)
    assert not r.authenticated()


def test_local_docker_pull():
    image_filename = "tests/assets/busybox.tar"
    image, tag = "busybox", "latest"
    new_image_full, new_image, new_tag = (
        "localhost:5000/library/mybusybox",
        "library/mybusybox",
        "mylatest",
    )

    docker.load(image_filename)
    docker.tag(image, tag, new_image_full, new_tag)
    docker.push(new_image_full, new_tag)

    registry = Registry(hostname="http://localhost:5000", authentication=None)

    assert new_image in registry.list_images()
    assert new_tag in registry.list_image_tags("library/mybusybox")

    image = registry.pull_image(new_image, new_tag)

    assert image.name == new_image
    assert image.tag == new_tag
    assert len(image.layers) == 2


@pytest.mark.parametrize(
    "hostname, authentication",
    [
        ("http://localhost:5000", None),
        (
            "http://localhost:6000",
            functools.partial(basic_authentication, "admin", "password"),
        ),
    ],
)
def test_local_docker_push(hostname, authentication):
    filename = "tests/assets/hello-world.tar"
    image = Image.from_filename(filename)[0]

    registry = Registry(hostname=hostname, authentication=authentication)
    registry.push_image(image)

    assert image.name in registry.list_images()
    assert image.tag in registry.list_image_tags(image.name)


def test_local_docker_delete():
    image_filename = "tests/assets/busybox.tar"
    image, tag = "busybox", "latest"
    new_image_full, new_image, new_tag = (
        "localhost:5000/library/mybusybox",
        "library/mybusybox",
        "mylatest",
    )

    docker.load(image_filename)
    docker.tag(image, tag, new_image_full, new_tag)
    docker.push(new_image_full, new_tag)

    registry = Registry(hostname="http://localhost:5000", authentication=None)

    assert new_image in registry.list_images()
    assert new_tag in registry.list_image_tags(new_image)

    registry.delete_image(new_image, new_tag)

    available_tags = registry.list_image_tags(new_image)
    assert available_tags is None or new_tag not in available_tags

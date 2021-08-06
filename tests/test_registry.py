import pytest
import subprocess
import functools

from python_docker.registry import Registry, basic_authentication, dockerhub_authentication
from python_docker.base import Image


@pytest.mark.parametrize('image_name, tag, layers', [
    ('library/hello-world', 'latest', 2),
    ('library/busybox', 'latest', 2),
])
def test_dockerhub_pull(image_name, tag, layers):
    registry = Registry()
    image = registry.pull_image(image_name, tag)
    assert image.name == image_name
    assert image.tag == tag
    assert len(image.layers) == layers


@pytest.mark.parametrize('hostname, authentication', [
    ('http://localhost:5000', None),
    ('http://localhost:6000', functools.partial(basic_authentication, 'admin', 'password')),
    ('https://registry-1.docker.io', dockerhub_authentication),
])
def test_registry_authenticated(hostname, authentication):
    r = Registry(hostname, authentication)
    assert r.authenticated()


@pytest.mark.parametrize('hostname, authentication', [
    ('http://localhost:6000', functools.partial(basic_authentication, 'admin', 'wrongpassword')),
])
def test_registry_not_authenticated(hostname, authentication):
    r = Registry(hostname, authentication)
    assert not r.authenticated()


def test_local_docker_pull():
    subprocess.check_output(['docker', 'load', '-i', 'tests/assets/busybox.tar'])
    subprocess.check_output(['docker', 'tag', 'busybox:latest', 'localhost:5000/library/mybusybox:mylatest'])
    subprocess.check_output(['docker', 'push', 'localhost:5000/library/mybusybox:mylatest'])

    registry = Registry(hostname='http://localhost:5000', authentication=None)
    image = registry.pull_image('library/mybusybox', 'mylatest')

    assert image.name == 'library/mybusybox'
    assert image.tag == 'mylatest'
    assert len(image.layers) == 2


@pytest.mark.parametrize('hostname, authentication', [
    ('http://localhost:5000', None),
    ('http://localhost:6000', functools.partial(basic_authentication, 'admin', 'password')),
])
def test_local_docker_push(hostname, authentication):
    filename = 'tests/assets/hello-world.tar'
    image = Image.from_filename(filename)[0]

    registry = Registry(hostname=hostname, authentication=authentication)
    registry.push_image(image)

    assert image.name in registry.catalog()

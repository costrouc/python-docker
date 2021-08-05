import tempfile
import os

from python_docker.base import Image

def test_read_docker_image_from_file():
    filename = 'tests/assets/hello-world.tar'

    image = Image.from_filename(filename)[0]

    assert image.name == 'hello-world'
    assert image.tag == 'latest'
    assert len(image.layers) == 1
    assert image.layers[0].checksum == 'f22b99068db93900abe17f7f5e09ec775c2826ecfe9db961fea68293744144bd'
    assert image.layers[0].compressed_checksum == 'ea2345d37a3341b61dcb1538a2520b3614f9ca07f47947595581c8a0c4e55b36'


def test_read_write_read_docker_image_from_file():
    filename = 'tests/assets/hello-world.tar'
    image = Image.from_filename(filename)[0]

    with tempfile.TemporaryDirectory() as tmpdir:
        filename = os.path.join(tmpdir, 'docker.tar')
        image.write_filename(filename)
        new_image = Image.from_filename(filename)[0]

    assert image.name == new_image.name
    assert image.tag == new_image.tag
    assert len(image.layers) == len(new_image.layers)
    assert image.layers[0].checksum == new_image.layers[0].checksum
    assert image.layers[0].compressed_checksum == new_image.layers[0].compressed_checksum

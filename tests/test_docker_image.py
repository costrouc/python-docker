import tempfile
import os

from python_docker.base import Image


def test_read_docker_image_from_file():
    filename = "tests/assets/busybox.tar"

    image = Image.from_filename(filename)[0]

    assert image.name == "busybox"
    assert image.tag == "latest"
    assert len(image.layers) == 1
    assert (
        image.layers[0].checksum
        == "5b8c72934dfc08c7d2bd707e93197550f06c0751023dabb3a045b723c5e7b373"
    )
    assert (
        image.layers[0].compressed_checksum
        == "8cff16fb5a3a3d60cbe59e72f2ec02291d78afc3e214e75e1ddbbe79766473e3"
    )


def test_read_write_read_docker_image_from_file():
    filename = "tests/assets/busybox.tar"
    image = Image.from_filename(filename)[0]

    with tempfile.TemporaryDirectory() as tmpdir:
        filename = os.path.join(tmpdir, "docker.tar")
        image.write_filename(filename)
        new_image = Image.from_filename(filename)[0]

    assert image.name == new_image.name
    assert image.tag == new_image.tag
    assert len(image.layers) == len(new_image.layers)
    assert image.layers[0].checksum == new_image.layers[0].checksum
    assert (
        image.layers[0].compressed_checksum == new_image.layers[0].compressed_checksum
    )


def test_run_read_docker_image_from_file():
    filename = "tests/assets/busybox.tar"
    image = Image.from_filename(filename)[0]

    message = "hello, world!"
    assert image.run(["echo", message]).decode("utf-8") == f"{message}"

    # assert default permissions
    assert (
        image.run(["id"]).decode("utf-8") == "uid=0(root) gid=0(root) groups=10(wheel)"
    )

    output = image.run(["env"])[:-1].decode("utf-8")
    environment = {row.split("=")[0]: row.split("=")[1] for row in output.split("\n")}
    assert (
        environment["PATH"]
        == "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    )

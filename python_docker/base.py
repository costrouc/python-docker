import io
import os
import tarfile
import secrets
from datetime import datetime, timezone
import hashlib
import gzip
import tempfile

from python_docker import schema, utils, docker
from python_docker.tar import (
    parse_v1,
    write_v1,
    write_tar_from_contents,
    write_tar_from_path,
    write_tar_from_paths,
)


class Layer:
    def __init__(
        self,
        id,
        parent,
        content,
        architecture: str = "x86-64",
        os: str = "linux",
        created: str = None,
        author: str = "conda-docker",
        config: dict = None,
    ):
        self.id = id
        self.parent = parent
        self._content = content
        self.architecture = architecture
        self.os = os
        self.created = created or datetime.now(timezone.utc).astimezone().isoformat()
        self.author = author
        self.config = config or schema.DockerConfigConfig().dict()

    @property
    def content(self):
        return self._content

    @property
    def size(self):
        return len(self.content)

    @property
    def checksum(self):
        return hashlib.sha256(self.content).hexdigest()

    @property
    def compressed_content(self):
        if hasattr(self, "_compressed_content"):
            return self._compressed_content
        # mtime needs to be set to a constant to ensure reproducibility
        self._compressed_content = gzip.compress(self.content, mtime=0)
        return self._compressed_content

    @property
    def compressed_size(self):
        return len(self.content)

    @property
    def compressed_checksum(self):
        return hashlib.sha256(self.compressed_content).hexdigest()

    @property
    def tar(self):
        return tarfile.TarFile(fileobj=io.BytesIO(self.content))

    @property
    def targz(self):
        return self.compressed_content

    def list_files(self):
        return self.tar.getnames()


class Image:
    def __init__(self, name, tag, layers=None):
        self.name = name
        self.tag = tag
        self.layers = layers or []

    def remove_layer(self):
        self.layers.pop(0)

    def add_layer_path(
        self, path, arcpath=None, recursive=True, filter=None, base_id=None
    ):
        digest = write_tar_from_path(
            path, arcpath=arcpath, recursive=recursive, filter=filter
        )
        self._add_layer(digest, base_id=base_id)

    def add_layer_paths(self, paths, filter=None, base_id=None):
        digest = write_tar_from_paths(paths, filter=filter)
        self._add_layer(digest, base_id=base_id)

    def add_layer_contents(self, contents, filter=None, base_id=None):
        digest = write_tar_from_contents(contents, filter=filter)
        self._add_layer(digest, base_id=base_id)

    def _add_layer(self, digest, base_id=None):
        if len(self.layers) == 0:
            parent_id = None
        else:
            parent_id = self.layers[0].id
        layer_id = secrets.token_hex(32) if base_id is None else base_id

        layer = Layer(
            id=layer_id,
            parent=parent_id,
            content=digest,
        )

        self.layers.insert(0, layer)

    @classmethod
    def from_filename(cls, filename):
        tar = tarfile.TarFile(filename)
        return parse_v1(tar)

    def write_filename(self, filename, version="v1"):
        if version != "v1":
            raise ValueError("only support writting v1 spec")

        write_v1(self, filename)

    @property
    def manifest_v2(self):
        docker_manifest = schema.DockerManifest.construct()
        docker_config = schema.DockerConfig.construct(
            config=schema.DockerConfigConfig(),
            container_config=schema.DockerConfigConfig(),
            rootfs=schema.DockerConfigRootFS(),
        )

        for layer in self.layers:
            docker_layer = schema.DockerManifestLayer(
                size=layer.compressed_size, digest=f"sha256:{layer.compressed_checksum}"
            )
            docker_manifest.layers.append(docker_layer)
            docker_config_history = schema.DockerConfigHistory()
            docker_config.history.append(docker_config_history)
            docker_config.rootfs.diff_ids.append(f"sha256:{layer.checksum}")

        docker_config_content = utils.sorted_json_dumps(docker_config.dict())
        docker_config_hash = hashlib.sha256(docker_config_content).hexdigest()

        docker_manifest.config = schema.DockerManifestConfig(
            size=len(docker_config_content), digest=f"sha256:{docker_config_hash}"
        )
        docker_manifest_content = utils.sorted_json_dumps(docker_manifest.dict())
        docker_manifest_hash = hashlib.sha256(docker_manifest_content).hexdigest()

        return {
            "manifest": (docker_manifest_content, docker_manifest_hash),
            "config": (docker_config_content, docker_config_hash),
        }

    def load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, "docker.tar")
            self.write_filename(filename)
            docker.load(filename)

    def run(self, cmd=None):
        self.load()
        return docker.run(self.name, self.tag, cmd=cmd)

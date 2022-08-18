import datetime
from typing import List, Optional, Dict
import enum

from pydantic import BaseModel, Field

from python_docker import __version__ as VERSION


def _docker_datetime_factory():
    """utcnow datetime + timezone as string"""
    return datetime.datetime.utcnow().astimezone().isoformat()


class DockerManifestV1Layer(BaseModel):
    blobSum: str


class DockerManifestV1History(BaseModel):
    v1Compatibility: str


class DockerManifestV1Signatures(BaseModel):
    header: Dict
    signature: str
    protected: str


class DockerManifestV1(BaseModel):
    schemaVersion: int = 1
    name: str
    tag: str
    architecture: str

    fsLayers: List[DockerManifestV1Layer]
    history: List[DockerManifestV1History]
    signatures: List[DockerManifestV1Signatures]


class DockerManifestV2Layer(BaseModel):
    mediaType: str = "application/vnd.docker.image.rootfs.diff.tar.gzip"
    size: int
    digest: str


class DockerManifestV2Config(BaseModel):
    mediaType: str = "application/vnd.docker.container.image.v1+json"
    size: int
    digest: str


class DockerManifestV2(BaseModel):
    schemaVersion: int = 2
    mediaType: str = "application/vnd.docker.distribution.manifest.v2+json"
    config: DockerManifestV2Config
    layers: List[DockerManifestV2Layer] = []


class DockerConfigConfig(BaseModel):
    Hostname: str = ""
    Domainname: str = ""
    User: str = "0:0"
    AttachStdin: bool = False
    AttachStdout: bool = False
    AttachStderr: bool = False
    Tty: bool = False
    OpenStdin: bool = False
    StdinOnce: bool = False
    Env: List[str] = [
        "PATH=/opt/conda/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    ]
    Cmd: Optional[List[str]] = ["/bin/sh"]
    ArgsEscaped: bool = True
    Image: Optional[str] = None
    Volumes: Optional[List[str]]
    WorkingDir: str = "/"
    Entrypoint: Optional[List[str]] = ["/bin/sh", "-c"]
    OnBuild: Optional[str] = None
    Labels: Optional[Dict[str, str]] = {"PYTHON_DOCKER": VERSION}


class DockerConfigRootFS(BaseModel):
    type: str = "layers"
    diff_ids: List[str] = []


class DockerConfigHistory(BaseModel):
    created: str = Field(default_factory=_docker_datetime_factory)
    created_by: str = ""


class DockerConfig(BaseModel):
    architecture: str = "amd64"
    os: str = "linux"
    config: DockerConfigConfig
    container: Optional[str]
    container_config: Optional[DockerConfigConfig]
    created: str = Field(default_factory=_docker_datetime_factory)
    docker_version: str = "18.09.7"
    history: List[DockerConfigHistory] = []
    rootfs: DockerConfigRootFS


# https://docs.docker.com/registry/spec/api/#errors-2
class DockerRegistryError(enum.Enum):
    NAME_UNKNOWN = {
        "message": "repository name not known to registry",
        "detail": "This is returned if the name used during an operation is unknown to the registry",
        "status": 404,
    }
    BLOB_UNKNOWN = {
        "message": "blob unknown to registry",
        "detail": "This error may be returned when a blob is unknown to the registry in a specified repository. This can be returned with a standard get or if a manifest references an unknown layer during upload",
        "status": 404,
    }
    MANIFEST_UNKNOWN = {
        "message": "manifest unknown",
        "detail": "This error is returned when the manifest, identified by name and tag is unknown to the repository",
        "status": 404,
    }
    UNAUTHORIZED = {
        "message": "authentication required",
        "detail": "The access controller was unable to authenticate the client. Often this will be accompanied by a Www-Authenticate HTTP response header indicating how to authenticate",
        "status": 401,
    }
    UNSUPPORTED = {
        "message": "The operation is unsupported",
        "detail": "The operation was unsupported due to a missing implementation or invalid set of parameters",
        "status": 405,
    }
    DENIED = {
        "message": "requested access to the resource is denied",
        "detail": "The access controller denied access for the operation on a resource",
        "status": 403,
    }

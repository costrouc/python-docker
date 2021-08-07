# python-docker

A pure python implementation to build docker images without `docker`
and provide a python api for interacting with docker
registries.

Examples using Library
----------------------

Downloading docker images without docker!

```python
from python_docker.registry import Registry

registry = Registry()
image = registry.pull_image('frolvlad/alpine-glibc', 'latest')
```

Modify docker image from filesystem

```python
from python_docker.base import Image
from python_docker.registry import Registry

registry = Registry()
image = registry.pull_image('continuumio/miniconda3', 'latest')
image.remove_layer()
image.name = 'this-is-a-test'
image.add_layer_path('./')
image.add_layer_contents({
    '/this/is/a/test1': b'this is test 1',
    '/this/is/a/test2': b'this is test 2'
})
image.layers[0].config['Env'].append('FOO=BAR')

# write docker image to filesystem
image.write_filename('example-docker-image.tar')

# run docker image (does require docker)
image.run(['cat /this/is/a/test1'])
```

How does this work?
-------------------

Turns out that docker images are just a tar collection of files. There
are several versions of the spec. For `v1.0` the specification is
[defined here](https://github.com/moby/moby/blob/master/image/spec/v1.md).
Instead of writing down the spec lets look into a single docker image.

```shell
docker pull ubuntu:latest
docker save ubuntu:latest -o /tmp/ubuntu.tar
```

List the directory structure of the docker image. Notice how it is a
collection of `layer.tar` which is a tar archive of filesystems. And
several json files. `VERSION` file is always `1.0` currently.

```shell
tar -tvf /tmp/ubuntu.tar
```

Dockerhub happens to export docker images in a `v1` - `v1.2` compatible
format. Lets only look at the files important for `v1`. Repositories
tells the layer to use as the layer head of the current name/tag.

```shell
tar -xf /tmp/ubuntu.tar $filename
cat $filename | python -m json.tool
```

For each layer there are three files: `VERSION`, `layer.tar`, and
`json`.

```shell
tar -xf /tmp/ubuntu.tar $filename
cat $filename
```

```shell
tar -xf /tmp/ubuntu.tar $filename
cat $filename | python -m json.tool
```

Looking at layer metadata.

```json
{
    "id": "93935bf1450219e4351893e546b97b4584083b01d19daeba56cab906fc75fc1c",
    "created": "1969-12-31T19:00:00-05:00",
    "container_config": {
        "Hostname": "",
        "Domainname": "",
        "User": "",
        "AttachStdin": false,
        "AttachStdout": false,
        "AttachStderr": false,
        "Tty": false,
        "OpenStdin": false,
        "StdinOnce": false,
        "Env": null,
        "Cmd": null,
        "Image": "",
        "Volumes": null,
        "WorkingDir": "",
        "Entrypoint": null,
        "OnBuild": null,
        "Labels": null
    },
    "os": "linux"
}
```

Looking at the layer filesystem.

```shell
tar -xf /tmp/ubuntu.tar $filename
tar -tvf $filename | head
```

References
----------
-   [Docker Registry API
    Specification](https://docs.docker.com/registry/spec/api/)
-   Docker Image Specification
    -   [Summary](https://github.com/moby/moby/blob/master/image/spec/v1.2.md)
    -   [Registry V2
        Specification](https://docs.docker.com/registry/spec/manifest-v2-2/)



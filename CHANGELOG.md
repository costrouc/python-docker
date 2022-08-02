# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

### Deprecated

### Removed

### Fixed

### Security

## [0.2.0] - 2022-08-01

### Added

 - tests for python 3.10
 - tests for pushing images to dockerhub and quay.io
 - properly implemented authentication for basic and token based authentication

### Fixed

 - no longer trust the docker checksum for content recompute each time

## [0.1.2] - 2021-10-21

### Added

 - test for wider range of docker images for download

### Fixed

 - bug in `container_config` field being an optional field in specification

## [0.1.1] - 2021-10-21

### Added

 - support for lazily pulling layers of images for registries
 - support for not uploading a layer when pushing if it already exists 
 - test for the removing of a layer

## [0.1.0] - 2021-07-07

Before this release new features were not documented

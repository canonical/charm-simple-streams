# Simple Streams

## Description

Simple Streams describe streams of like items in a structural fashion.
A client provides a way to sync or act on changes in a remote stream.

## Usage

The charm can be deployed using juju:
```
juju deploy ch:simple-streams
```

## Developing

Create and activate a virtualenv with the development requirements:

    make dev-environment
    source .venv/bin/activate


## Testing

You can use either tox or Makefile.

    tox
    # or
    make test

It is possible to run only some tests using the following commands:

    tox -e lint  # make lint
    tox -e unit  # make unittests
    tox -e func  # make functional

# Simple Streams

## Description

Simple Streams describe streams of like items in a structural fashion.
A client provides a way to sync or act on changes in a remote stream.

## Usage

The charm can be deployed using juju:
```
juju deploy cs:simple-streams
```

## Developing

Create and activate a virtualenv,
and install the development requirements,

    virtualenv -p python3 venv
    source venv/bin/activate
    pip install -r requirements-dev.txt

## Testing

Just run `run_tests`:

    ./run_tests

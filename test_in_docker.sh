#!/bin/bash

docker run --rm -it \
  -v "./:/app/" \
  --workdir "/app/" \
  python:3.9 "/app/test.sh"
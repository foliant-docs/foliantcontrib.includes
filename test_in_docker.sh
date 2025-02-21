#!/bin/bash

docker run --rm -it \
  -v "./:/app/" \
  -w "/app/" \
  python:3.9 "/app/test.sh"

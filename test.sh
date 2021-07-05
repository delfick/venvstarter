#!/bin/bash

if [[ -z $PARALLEL_PYTEST ]]; then
  exec bash -c "pytest -q $*"
else
  exec bash -c "pytest -q --workers $PARALLEL_PYTEST $*"
fi

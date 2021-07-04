#!/bin/bash
if [[ -z $PARALLEL_PYTEST ]]; then
  pytest -q "$*"
else
  pytest -q --workers $PARALLEL_PYTEST "$*"
fi

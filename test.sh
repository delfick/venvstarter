#!/bin/bash

if ! which pytest >/dev/null; then
    echo "Please \`pip install -e '.[tests]'\` first"
    exit 1
fi

PYTEST="$(which pytest)"

if [[ -z $PARALLEL_PYTEST ]]; then
    exec bash -c "$PYTEST -q $*"
else
    exec bash -c "$PYTEST -q --workers $PARALLEL_PYTEST $*"
fi

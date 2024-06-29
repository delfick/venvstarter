#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]:-$0}" )" && pwd )"

mkdir -p "$DIR/deps"

export VIRTUAL_ENV="$DIR/deps/uv-venv"

if which uv >/dev/null; then
    UV="$(which uv)"
else
    if [ ! -d "$VIRTUAL_ENV" ]; then
        echo "## uv not found on PATH, bootstrapping one"

        if which python3 >/dev/null; then
            python3 -m venv "$VIRTUAL_ENV"
        elif which python >/dev/null; then
            python -m venv "$VIRTUAL_ENV"
        elif which pip3 >/dev/null; then
            pip3 install uv -t "$DIR/deps" --disable-pip-version-check
            UV="$DIR/deps/bin/uv"
        elif which pip >/dev/null; then
            pip install uv -t "$DIR/deps" --disable-pip-version-check
            UV="$DIR/deps/bin/uv"
        fi
    fi

    if [ -z "$UV" ]; then
        if [ -f "$VIRTUAL_ENV/bin/uv" ]; then
            UV="$VIRTUAL_ENV/bin/uv"
        fi

        if [ -z "$UV" ]; then
            if [ ! -f "$VIRTUAL_ENV/bin/pip" ]; then
                "$VIRTUAL_ENV/bin/python" -m ensurepip
            fi

            if [ ! -f "$VIRTUAL_ENV/bin/pip" ]; then
                echo "Failed to bootstrap a 'uv' to use"
            else
                "$VIRTUAL_ENV/bin/pip" install uv
                UV="$VIRTUAL_ENV/bin/uv"
            fi
        fi
    fi


    if [ -z "$UV" ]; then
        exit 1
    fi
fi

if [ ! -d "$VIRTUAL_ENV" ]; then
    echo "## bootstrapping a virtualenv to bootstrap from"
    "$UV" venv "$VIRTUAL_ENV" >/dev/null
fi

exec "$UV" "$@"

#!/bin/bash

pushd ${BASH_SOURCE%/*}

pipenv run python main.py &
popd




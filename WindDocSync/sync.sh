#!/bin/bash

pushd ${BASH_SOURCE%/*}

php sync.php
pipenv run python sync.py

popd

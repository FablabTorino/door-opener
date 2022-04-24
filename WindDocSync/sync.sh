#!/bin/bash

pushd ${BASH_SOURCE%/*}

php sync.php
timeout 300 pipenv run python door1.py && timeout 300 pipenv run python door2.py

popd

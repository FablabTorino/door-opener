#!/bin/bash

pushd ${BASH_SOURCE%/*}

php sync.php &&
#timeout 300 pipenv run python door1.py
timeout 300 pipenv run python door1.py && timeout 300 pipenv run python door3.py 
popd

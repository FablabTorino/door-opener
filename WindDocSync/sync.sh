#!/bin/bash

pushd ${BASH_SOURCE%/*}

timeout 300 pipenv run python pysync.py && timeout 300 pipenv run python door1.py && timeout 300 pipenv run python door2.py && timeout 300 pipenv run python door3.py && timeout 300 pipenv run python door4.py
popd

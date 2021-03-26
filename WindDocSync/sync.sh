#!/bin/bash

pushd ${BASH_SOURCE%/*}

php sync.php
pipenv shell
python sync.py

popd
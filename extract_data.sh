#!/usr/bin/env bash

tar -C ./data -xjvf ./data/DeepCoder_data.tar.bz2

mkdir -p ./program_synthesis/data/generated
tar -C ./program_synthesis/data/generated -xzvf ./data/metaset3.tar.gz


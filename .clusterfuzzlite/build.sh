#!/bin/bash -eu
# Builds the Atheris fuzz targets in fuzz/ for ClusterFuzzLite.
# fuzz/requirements.txt: uv export --frozen --no-dev --package obsei --no-emit-workspace --no-emit-project
python3 -m pip install --require-hashes --no-deps -r fuzz/requirements.txt
export PYTHONPATH="$SRC/obsei/packages/obsei/src"
for target in fuzz/fuzz_*.py; do
  compile_python_fuzzer "$target"
done

FROM gcr.io/oss-fuzz-base/base-builder-python:v1@sha256:855167924712ac98dedabf0ae44071caccbb0130bb0544ea06522b1f82288371
COPY . $SRC/obsei
WORKDIR $SRC/obsei
COPY .clusterfuzzlite/build.sh $SRC/

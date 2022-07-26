FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# install dependencies
RUN apt-get update && \
    apt-get install -y curl unzip wget bzip2 && \
    apt-get clean

# install micromamba
RUN mkdir -p /software/micromamba && \
    cd /software/micromamba && \
    wget -qO- https://micromamba.snakepit.net/api/micromamba/linux-64/0.15.2 | tar -xvj bin/micromamba
ENV PATH="/software/micromamba/bin:${PATH}"

# create conda/mamba environment
COPY ./environment.yaml /sumstat-data/
RUN micromamba install --name base --file /sumstat-data/environment.yaml --root-prefix /software/micromamba --yes

# copy other files and folders
COPY ./ /sumstat-data

# set default directory
WORKDIR /sumstat-data

# default command
CMD ["/bin/bash"]

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# install dependencies
# TODO: is `update-ca-certificates` really necessary?
RUN apt-get update && \
    apt-get install --no-install-recommends --yes ca-certificates-java curl \
      unzip wget bzip2 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    update-ca-certificates -f

# install micromamba
RUN mkdir -p /software/micromamba && \
    cd /software/micromamba && \
    curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/0.15.2 | tar -xvj bin/micromamba
ENV PATH="/software/micromamba/bin:${PATH}"

# create conda/mamba environment
COPY ./environment.yaml /sumstat-data/
RUN micromamba install --name base --file /sumstat-data/environment.yaml --root-prefix /software/micromamba --yes && \
    rm -rf /software/micromamba/pkgs

# copy other files and folders
COPY ./ /sumstat-data

# set default directory
WORKDIR /sumstat-data

# default command
CMD ["/bin/bash"]

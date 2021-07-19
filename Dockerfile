FROM continuumio/miniconda3:4.9.2

# save current directory for later
RUN export root=$(pwd)

# copy requirements for conda envirounment and build it
COPY ./environment.yaml /sumstat-data/
WORKDIR /sumstat-data
RUN conda env create -n sumstat-data --file environment.yaml
RUN echo "source activate sumstat-data" > ~/.bashrc
ENV PATH /opt/conda/envs/sumstat-data/bin:$PATH

# copy other files and folders
# doing it here means changes to the these files/folders do not require building
# the conda environment from scratch
COPY $pwd/extras /sumstat-data/extras/
COPY $pwd/filters /sumstat-data/filters/
COPY $pwd/ingest /sumstat-data/ingest/
COPY $pwd/run_extract_significant_window.py /sumstat-data/
COPY $pwd/test_pyspark.py /sumstat-data/

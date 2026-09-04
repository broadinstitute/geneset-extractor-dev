FROM continuumio/miniconda3:latest

ARG GIT_COMMIT=587d74cc8413a50378a582ef9f9884e010872fa3

WORKDIR /opt

RUN apt-get update && apt-get install -y \
    git \
    bash \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/flannick/dig-gene-set-extractors.git

WORKDIR /opt/dig-gene-set-extractors

RUN git checkout ${GIT_COMMIT}

COPY environment.yml /tmp/environment.yml

RUN conda env create -f /tmp/environment.yml && \
    conda clean -afy

SHELL ["conda", "run", "-n", "geneset-extractors", "/bin/bash", "-c"]

RUN pip install -e .

RUN python -c "import rdflib, yaml; print('DAPPER provenance dependencies OK')"

WORKDIR /work

ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "geneset-extractors"]
CMD ["geneset-extractors", "--help"]

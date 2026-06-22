FROM continuumio/miniconda3:latest

ARG DIG_BRANCH=md_liger
ARG DIG_REF=

WORKDIR /opt

RUN apt-get update && apt-get install -y \
    git \
    bash \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --branch "${DIG_BRANCH}" --single-branch https://github.com/flannick/dig-gene-set-extractors.git

WORKDIR /opt/dig-gene-set-extractors

RUN if [ -n "${DIG_REF}" ]; then git checkout "${DIG_REF}"; fi

COPY environment.yml /tmp/environment.yml

RUN conda env create -f /tmp/environment.yml && \
    conda clean -afy

SHELL ["conda", "run", "-n", "geneset-extractors", "/bin/bash", "-c"]

RUN pip install -e ".[dev,scrna_tools]"

RUN Rscript -e "options(repos = c(CRAN = 'https://cloud.r-project.org')); BiocManager::install(c('XVector', 'SparseArray', 'DelayedArray', 'rhdf5', 'rhdf5filters', 'Rhdf5lib', 'HDF5Array', 'SummarizedExperiment', 'SingleCellExperiment', 'Biostrings', 'KEGGREST', 'AnnotationDbi', 'GenomicRanges'), ask = FALSE, update = FALSE)" && \
    Rscript -e "options(repos = c(CRAN = 'https://cloud.r-project.org')); install.packages(c('hdf5r', 'RcppPlanc'), dependencies = TRUE)" && \
    Rscript -e "options(repos = c(CRAN = 'https://cloud.r-project.org')); if (!requireNamespace('rliger', quietly=TRUE)) install.packages('rliger', dependencies=FALSE)" && \
    Rscript -e "if (!requireNamespace('rliger', quietly=TRUE)) remotes::install_github('welch-lab/liger', dependencies=FALSE)" && \
    Rscript -e "pkgs <- c('rliger', 'Seurat', 'dplyr', 'purrr', 'clue', 'proxy', 'reticulate', 'anndata', 'XVector', 'SparseArray', 'DelayedArray', 'HDF5Array', 'rhdf5', 'hdf5r', 'RcppPlanc'); missing <- pkgs[!vapply(pkgs, requireNamespace, logical(1), quietly=TRUE)]; if (length(missing)) stop(paste('Missing R packages after environment creation:', paste(missing, collapse=', ')))"

WORKDIR /work

ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "geneset-extractors"]
CMD ["geneset-extractors", "--help"]

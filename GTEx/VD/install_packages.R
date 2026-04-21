# Install required packages for DE analysis

# Set CRAN mirror
options(repos = c(CRAN = "https://cloud.r-project.org/"))

# Create user library if it doesn't exist
user_lib <- path.expand("~/R/library")
if (!dir.exists(user_lib)) {
  dir.create(user_lib, recursive = TRUE)
}

# Add user library to search path
.libPaths(c(user_lib, .libPaths()))

cat("User library location:", user_lib, "\n")

if (!require("BiocManager", quietly = TRUE))
    install.packages("BiocManager", lib = user_lib)

BiocManager::install(c("limma", "edgeR"), lib = user_lib)
install.packages("tidyverse", lib = user_lib)

cat("Packages installed successfully!\n")

# IDG runtime

The wrapper requires Python with the paired `dig-gene-set-extractors` checkout
available through `DIG_REPO`. Full execution additionally requires outbound
HTTPS access to the named Enrichr endpoint. Smoke execution uses only committed
fixtures. Cluster execution requires the site Apptainer image and qsub setup.

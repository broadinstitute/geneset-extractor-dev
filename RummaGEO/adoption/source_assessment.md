# RummaGEO source assessment

The historical RummaGEO gene- and drug-perturbation notebooks query mutable
RummaGEO and SigCom-LINCS services, and use query results with notebook-era
selection rules. Their exact response snapshots are not a stable published
release. The DIG implementation preserves those selection rules and records
the acquired query payloads, source hashes, and selection manifest as runtime
provenance artifacts.

This is therefore a scientific reimplementation. A full run must be compared
against the supplied legacy GMT snapshots by normalized source term and
direction before this submission can become ready. The required review remains
pending until that comparison is recorded in the paired pull requests.

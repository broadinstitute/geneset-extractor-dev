# Documentation manifest

This index describes each maintained Markdown document under `docs/`, its
intended reader, and why it exists. Start with `submissions/README.md` for the
current submission system; use `dev/add_new_library/` as historical and
practical supporting guidance rather than as a replacement for the validated
submission contract.

| Document | Primary audience | Value |
| --- | --- | --- |
| [MANIFEST.md](MANIFEST.md) | Contributors and maintainers | This inventory: a quick way to find the right documentation and understand its intended authority. |
| [dev/add_new_library/AGENTS.md](dev/add_new_library/AGENTS.md) | Coding agents and maintainers | Local instructions for work in the add-new-library documentation area, including boundaries and expectations for safe edits. |
| [dev/add_new_library/add_new_library_workflow.md](dev/add_new_library/add_new_library_workflow.md) | Library contributors | Practical end-to-end background for adding a library, useful when learning the established repository conventions. |
| [dev/add_new_library/new_library_checklist.md](dev/add_new_library/new_library_checklist.md) | Contributors and reviewers | A concise completeness checklist for source metadata, implementation, reproducibility, and publication readiness. |
| [dev/add_new_library/new_library_wrapper_workflow.md](dev/add_new_library/new_library_wrapper_workflow.md) | Wrapper implementers | Explains the wrapper-side workflow and helps keep orchestration separate from substantive scientific processing. |
| [dev/add_new_library/publishable_library_attributes.md](dev/add_new_library/publishable_library_attributes.md) | Maintainers and reviewers | Defines the characteristics needed for a library to be safely published and maintained. |
| [submissions/README.md](submissions/README.md) | All submission-system users | Entry point for the current submission contract, local/CI commands, safety model, and links to specialized guides. |
| [submissions/architecture.md](submissions/architecture.md) | Contributors and maintainers | Defines the DIG-versus-wrapper ownership boundary and the expected submitted-library layout. |
| [submissions/contributor-workflow.md](submissions/contributor-workflow.md) | New-library contributors | Gives the proposal-to-paired-PR sequence for a newly developed library. |
| [submissions/creating-new-library.md](submissions/creating-new-library.md) | New-library contributors and maintainers | Documents `create-library`, isolated workspaces, source-input protection, verification, and submission. |
| [submissions/adopting-existing-library.md](submissions/adopting-existing-library.md) | Legacy-library adopters | Explains the general adoption contract, architecture migration, provenance, ignore policy, comparisons, and advanced commands. |
| [submissions/adopting-trusted-existing-submission.md](submissions/adopting-trusted-existing-submission.md) | Maintainers adopting trusted legacy libraries | Complete operational tutorial for exact reproduction or scientific reimplementation, preserving previous attempts, isolated artifacts, verification, and same-repository PRs. |
| [submissions/submission-schema.md](submissions/submission-schema.md) | Submission authors and validator maintainers | Summarizes `submission.yaml`, readiness constraints, provenance declarations, and isolated-runtime output settings. |
| [submissions/reproduction-contract.md](submissions/reproduction-contract.md) | Reproduction-script authors and reviewers | Specifies manifests, strict scripts, runtime artifacts, receipts, source URLs, and provenance-completeness limits. |
| [submissions/review-policy.md](submissions/review-policy.md) | Reviewers and maintainers | States blocking validation rules, legacy compatibility, provenance expectations, boundary exceptions, and paired-PR review order. |
| [submissions/patterns/generic.md](submissions/patterns/generic.md) | Contributors with no closer assay pattern | Provides the minimal generic template for a wrapper that dispatches a reusable DIG workflow. |
| [submissions/patterns/gtex.md](submissions/patterns/gtex.md) | GTEx-like library contributors | Describes the intended tissue-partitioned bulk RNA-seq wrapper shape and DIG responsibilities. |
| [submissions/patterns/motrpac.md](submissions/patterns/motrpac.md) | MoTrPAC-like library contributors | Describes transcriptomics model/tissue orchestration and the related DIG processing boundary. |
| [submissions/patterns/hubmap.md](submissions/patterns/hubmap.md) | HuBMAP-like library contributors | Describes released-model/source orchestration and DIG ownership of ASCT+B processing and gene-set construction. |
| [submissions/patterns/lincs_l1000.md](submissions/patterns/lincs_l1000.md) | LINCS L1000-like library contributors | Describes signature-source wrapper selection and DIG ownership of matrix processing, ranking, mapping, and GMT generation. |

The documents in `docs/submissions/` are the current submission-system
reference. No document in this manifest authorizes moving scientific logic from
DIG into a wrapper.

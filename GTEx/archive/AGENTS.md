# Repository Guidelines

## Project Structure & Module Organization
This repository is currently minimal, but contributors should follow the established layout rules:

- `src/`: new Python scripts. Use versioned filenames such as `src/summarize_gtex_tables.v1.py`.
- `run/`: bash wrappers for Python entrypoints, using the same basename as the Python script.
- `outputs/`: all generated results, written to a named subfolder such as `outputs/qc_tables_v1/`.
- `history/`: entire session history, including user prompts and agent responses in markdown format files, named appropriately for the content.

Keep generated tables as tab-delimited `.tsv` files. Write plot outputs as both `.pdf` and `.png` with the same basename, and add companion `.tsv` and `.md` files alongside new outputs.

Always write companion logging files with extension `.log` next to the outputs

## Build, Test, and Development Commands
No project-wide build system or test runner is present yet. Use CLI-first commands and keep runs explicit.

- `python3 src/example_task.v1.py`: run a Python workflow directly.
- `bash run/example_task.v1.sh`: run the matching shell wrapper.
- `find outputs/ -maxdepth 2 -type f | sort`: inspect generated deliverables.

Do not run scripts or modify existing files unless the task explicitly requires it.

## Coding Style & Naming Conventions
Prefer small, single-purpose scripts with clear logging at each major step, including file discovery, table loading, grouped summaries, dataframe shapes, and output writes.

- Use lowercase snake_case for variables, functions, columns, and filenames.
- Use explicit version suffixes: `.v1.py`, `.v1.tsv`, `.v1.md`.
- Avoid hidden state and avoid editing shell startup files.
- Prefer standard library or local code over system-wide installs unless explicitly requested.

## Testing Guidelines
There is no configured test framework in the current checkout. When adding tests, keep them CLI-friendly and colocate them in a `tests/` directory if one is introduced. Name test files `test_<feature>.py` and prefer deterministic checks over manual inspection.

At minimum, validate:

- expected row and column counts
- required output files under `outputs/`
- schema details such as lowercase underscore-delimited column names

## Commit & Pull Request Guidelines
Git history is not available in this workspace, so no repository-specific commit convention can be inferred. Use short, imperative commit messages such as `add gtex table summarizer v1` if commits are requested.

For pull requests, include a concise description, the exact commands run, the output directory created, and any assumptions or skipped validation steps. Show diffs before suggesting a commit.

## Safety & Agent Notes
Do not use destructive commands unless explicitly requested. Do not modify existing files or run existing scripts without clear user approval.

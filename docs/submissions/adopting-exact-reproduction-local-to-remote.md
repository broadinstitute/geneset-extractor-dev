# Exact reproduction: local authoring → remote full reproduction

This is the recommended adoption path. The local machine holds read-only
legacy code/configuration/reference GMTs plus small fixtures; the remote/HPC
machine holds full inputs and performs the full run.

## Local authoring machine

Before creating the workspace, prepare `SMOKE_INPUTS` as a small,
redistributable file or directory that exercises the intended path and can
produce at least one deterministic gene set. It is the only source data Codex
may use locally; do not provide or download the complete dataset here.

```bash
export LIBRARY_ID="MY_LIBRARY"
export GITHUB_USER="USERNAME"
export LEGACY_LOCAL="/local/path/to/legacy_evidence"
export LOCAL_WORKSPACE="$HOME/gene-set-adoptions/$LIBRARY_ID-authoring"
export SMOKE_INPUTS="/local/path/to/small_redistributable_fixtures"

git clone --branch main https://github.com/broadinstitute/geneset-extractor-dev.git submission-system-tools
cd submission-system-tools
python3 -m submission_tools adopt \
  --existing "$LEGACY_LOCAL" --library-id "$LIBRARY_ID" \
  --workspace "$LOCAL_WORKSPACE" --github-user "$GITHUB_USER" \
  --smoke-inputs "$SMOKE_INPUTS" --ai-mode authoring
cd "$LOCAL_WORKSPACE"
codex
```

Tell Codex:

```text
Follow AI_ADOPTION_PROMPT.md completely.

This is an exact_reproduction adoption. Preserve scientific behavior and map
every authoritative full legacy GMT to its full regenerated counterpart using
set_equivalent comparison. Work only with supplied smoke fixtures locally: do
not download, locate, or create replacement inputs; do not submit jobs or
claim full equivalence. Inspect the supplied fixtures and ensure they exercise
the intended path and produce at least one deterministic gene set. If they
cannot, report the exact small fixture requirement to the user. Complete
input_manifest.tsv with every full input's identifier, release, URL/access
instructions, and feasible checksum. Keep substantive logic in DIG and the
wrapper thin.
```

After Codex completes local work:

```bash
./verify-adoption --stage authoring
python3 -m submission_tools export-adoption \
  --workspace "$LOCAL_WORKSPACE" --output reproduction-handoff.tar.gz
# Transfer reproduction-handoff.tar.gz to the remote/HPC machine.
```

## Remote/HPC reproduction machine

```bash
export LIBRARY_ID="MY_LIBRARY"
export LEGACY_REMOTE="/remote/path/to/authoritative_legacy_submission"
export REMOTE_WORKSPACE="$HOME/gene-set-adoptions/$LIBRARY_ID-full"
export REMOTE_BINDINGS="/secure/project/$LIBRARY_ID/input-bindings.yaml"

python3 -m submission_tools import-adoption \
  --bundle reproduction-handoff.tar.gz --workspace "$REMOTE_WORKSPACE" \
  --legacy-root "$LEGACY_REMOTE" --ai-mode full
less "$REMOTE_WORKSPACE/adoption/remote_input_requirements.md"
cp "$REMOTE_WORKSPACE/adoption/remote_input_bindings.template.yaml" "$REMOTE_BINDINGS"
# Edit $REMOTE_BINDINGS with authorized full-input paths.

cd "$REMOTE_WORKSPACE/geneset-extractor-dev"
cat ../adoption/gitignore_allowlist.md >> .gitignore
cd "$REMOTE_WORKSPACE/geneset-extractor-dev/$LIBRARY_ID"
SUBMISSION_WORK_DIR="$REMOTE_WORKSPACE/work-full" bash reproduction/reproduce.sh full
cd "$REMOTE_WORKSPACE"
./verify-adoption --stage full --work-dir work-full --input-bindings "$REMOTE_BINDINGS"
./submit-adoption --yes
```

Stop if full comparison or provenance fails. Never commit full inputs, output
artifacts, work directories, receipts, or `$REMOTE_BINDINGS`.

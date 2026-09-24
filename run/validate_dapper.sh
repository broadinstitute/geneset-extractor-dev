#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<EOF
Usage:
  $(basename "$0") \
    --dir DIRECTORY \
    --linter /path/to/lint_provenance.py \
    --output-prefix PREFIX

Options:
  -d, --dir DIRECTORY
      Root directory to search recursively for:
        geneset.provenance.dapper.yaml

  -l, --linter PATH
      Path to DAPPER lint_provenance.py.

  -o, --output-prefix PREFIX
      Output prefix. Produces:
        PREFIX.tsv
        PREFIX.summary.txt

  -h, --help
      Show this help message.

Example:
  $(basename "$0") \
    --dir /path/to/gene_sets \
    --linter /path/to/dapper/schema/lint/lint_provenance.py \
    --output-prefix dapper_validation
EOF
}


SEARCH_DIR=""
LINTER=""
OUTPUT_PREFIX=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        -d|--dir)
            SEARCH_DIR="$2"
            shift 2
            ;;
        -l|--linter)
            LINTER="$2"
            shift 2
            ;;
        -o|--output-prefix)
            OUTPUT_PREFIX="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "ERROR: Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done


# Check required arguments.
if [[ -z "$SEARCH_DIR" ]]; then
    echo "ERROR: --dir is required" >&2
    usage >&2
    exit 1
fi

if [[ -z "$LINTER" ]]; then
    echo "ERROR: --linter is required" >&2
    usage >&2
    exit 1
fi

if [[ -z "$OUTPUT_PREFIX" ]]; then
    echo "ERROR: --output-prefix is required" >&2
    usage >&2
    exit 1
fi

if [[ ! -d "$SEARCH_DIR" ]]; then
    echo "ERROR: Directory not found: $SEARCH_DIR" >&2
    exit 1
fi

if [[ ! -f "$LINTER" ]]; then
    echo "ERROR: Linter not found: $LINTER" >&2
    exit 1
fi


TSV="${OUTPUT_PREFIX}.tsv"
SUMMARY="${OUTPUT_PREFIX}.summary.txt"


# Create output directory if needed.
OUTPUT_DIR=$(dirname "$TSV")

if [[ "$OUTPUT_DIR" != "." ]]; then
    mkdir -p "$OUTPUT_DIR"
fi


# Find all DAPPER gene-set provenance files recursively.
mapfile -d '' -t files < <(
    find "$SEARCH_DIR" \
        -type f \
        -name 'geneset.provenance.dapper.yaml' \
        -print0 \
    | sort -z
)


if [[ ${#files[@]} -eq 0 ]]; then
    echo "ERROR: No geneset.provenance.dapper.yaml files found under: $SEARCH_DIR" >&2
    exit 1
fi


total=${#files[@]}


echo "DAPPER batch validation" >&2
echo "Directory: $SEARCH_DIR" >&2
echo "Files:     $total" >&2
echo "Linter:    $LINTER" >&2
echo "TSV:       $TSV" >&2
echo "Summary:   $SUMMARY" >&2
echo >&2


{
    printf 'file\tstatus\tprofile\tnodes\tedges\traw_sources\terrors\twarnings\n'

    i=0

    for f in "${files[@]}"; do
        i=$((i + 1))

        printf '[%d/%d] Validating %s...\n' \
            "$i" "$total" "$f" >&2

        uv run "$LINTER" "$f" 2>&1 \
        | awk -v file="$f" '
        NR == 1 {
            nodes = $2
            edges = $4

            if (match($0, /\[([^]]+)\]/, a))
                profile = a[1]
            else
                profile = ""

            if (match($0, /, ([0-9]+) raw source\(s\)/, b))
                raw_sources = b[1]
            else
                raw_sources = ""
        }

        $1 == "PASS" || $1 == "FAIL" {
            status = $1

            if (match($0, /([0-9]+) error\(s\)/, e))
                errors = e[1]
            else
                errors = ""

            if (match($0, /([0-9]+) warning\(s\)/, w))
                warnings = w[1]
            else
                warnings = ""
        }

        END {
            print file "\t" \
                  status "\t" \
                  profile "\t" \
                  nodes "\t" \
                  edges "\t" \
                  raw_sources "\t" \
                  errors "\t" \
                  warnings
        }'
    done

} > "$TSV"


# Build summary from TSV.
awk -F'\t' '
BEGIN {
    total = 0
    pass = 0
    fail = 0
    nodes = 0
    edges = 0
    raw_sources = 0
    errors = 0
    warnings = 0
}

NR > 1 {
    total++

    if ($2 == "PASS")
        pass++
    else if ($2 == "FAIL")
        fail++

    nodes += $4
    edges += $5
    raw_sources += $6
    errors += $7
    warnings += $8
}

END {
    print "DAPPER validation summary"
    print "========================="
    print "Documents:    " total
    print "Passed:       " pass
    print "Failed:       " fail
    print "Errors:       " errors
    print "Warnings:     " warnings
    print ""
    print "Nodes:        " nodes
    print "Edges:        " edges
    print "Raw sources:  " raw_sources
}
' "$TSV" > "$SUMMARY"


echo >&2
echo "Validation complete." >&2
echo "TSV:     $TSV" >&2
echo "Summary: $SUMMARY" >&2
echo >&2

cat "$SUMMARY"

from pathlib import Path


def test_hz_converter_uses_age_pair_directories_and_canonical_gmt_prefix() -> None:
    source = (Path(__file__).resolve().parents[1] / "src/run_hz_notebook_model.py").read_text(encoding="utf-8")
    assert '"gmt_comparison_label"' in source
    assert 'gtex_aging_signature_name(args.tissue_label)' in source
    assert '"__comparison_only__"' not in source

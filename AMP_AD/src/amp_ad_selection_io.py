from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def amp_ad_root() -> Path:
    return repo_root() / "geneset-extractor-dev" / "AMP_AD"


def default_model_manifest_path() -> Path:
    return amp_ad_root() / "config" / "model_manifest.tsv"

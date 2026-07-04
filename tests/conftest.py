from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def samples_dir() -> Path:
    return Path(__file__).parent / "samples"


@pytest.fixture(scope="session")
def catalog_json_text(samples_dir: Path) -> str:
    return (samples_dir / "catalog.json").read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def catalog_binary_bytes(samples_dir: Path) -> bytes:
    return (samples_dir / "catalog.bin").read_bytes()

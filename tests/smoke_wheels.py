"""Verify installed wheels from a clean environment, without importing src/."""

from pathlib import Path
import platform

import _addressablestools_rust as native
import addressablestools
from addressablestools import DecoderRegistry, available_backends, parse


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    assert not Path(addressablestools.__file__).resolve().is_relative_to(root / "src")
    assert not Path(native.__file__).resolve().is_relative_to(root / "native")
    assert native.API_VERSION == 3
    print(f"Python {platform.python_version()} / {platform.system()} {platform.machine()} / native {native.__version__}")
    samples = root / "tests" / "samples"
    for format, data in (
        ("binary", (samples / "catalog.bin").read_bytes()),
        ("json", (samples / "catalog.json").read_text(encoding="utf-8")),
    ):
        assert "rust" in available_backends(format)
        reference = parse(data, backend="python")
        result = parse(data, backend="rust")
        assert result == reference
        if format == "binary":
            assert parse(data, DecoderRegistry(), backend="rust") == reference
        for key, locations in result.resources.items():
            for location, expected in zip(locations, reference.resources[key]):
                assert location._data_type == expected._data_type
        print(f"{format}: installed wheel verified ({len(result.resources)} keys)")


if __name__ == "__main__":
    main()

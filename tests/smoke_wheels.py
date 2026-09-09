"""Verify installed wheels from a clean environment, without importing src/."""

from pathlib import Path
import platform
from importlib.metadata import distribution

import addressablestools._rust as native
import addressablestools
from addressablestools import DecoderRegistry, available_backends, parse


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    assert not Path(addressablestools.__file__).resolve().is_relative_to(root / "src")
    assert not Path(native.__file__).resolve().is_relative_to(root / "native")
    assert Path(native.__file__).resolve().parent == Path(addressablestools.__file__).resolve().parent
    assert native.API_VERSION == 3
    assert native.__version__ == addressablestools.__version__ == distribution("addressablestools").version
    assert not distribution("addressablestools").requires
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
    import warnings
    import AddressablesTools
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        assert AddressablesTools.parse_binary((samples / "catalog.bin").read_bytes()).Resources
    assert AddressablesTools.__version__ == addressablestools.__version__


if __name__ == "__main__":
    main()

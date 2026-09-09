"""Verify the source archive can reproduce the complete mixed Python/Rust package."""

import argparse
from pathlib import Path, PurePosixPath
import tarfile
import tomllib


def check_sdist(path: Path, version: str) -> None:
    prefix = f"addressablestools-{version}/"
    required = {
        "pyproject.toml", "README.md", "LICENSE", "CHANGELOG.md", "PUBLISHING.md", "uv.lock",
        "native/Cargo.toml", "native/Cargo.lock", "native/src/lib.rs",
        "native/src/binary.rs", "native/src/json.rs", "src/AddressablesTools.py",
        "src/addressablestools/__init__.py", "src/addressablestools/_native.py",
        "src/addressablestools/py.typed", "tests/test_native_registry.py",
        "tests/samples/catalog.bin", "tests/samples/catalog.json",
        ".github/workflows/publish.yml", ".github/workflows/native.yml",
    }
    with tarfile.open(path) as archive:
        names = set()
        for member in archive.getmembers():
            name = member.name
            if not name.startswith(prefix) or ".." in PurePosixPath(name).parts:
                raise ValueError(f"invalid archive member {name!r}")
            if not member.isfile():
                raise ValueError(f"unexpected non-file archive member {name!r}")
            relative = name.removeprefix(prefix)
            if "__pycache__" in relative or relative.endswith((".pyd", ".so", ".pyc")):
                raise ValueError(f"compiled/cache file in source archive: {name}")
            names.add(relative)
        if not required <= names:
            raise ValueError(f"missing source files: {sorted(required - names)}")
        if "native/pyproject.toml" in names:
            raise ValueError("obsolete independent native project is included")
        for name, section in [("pyproject.toml", "project"), ("native/Cargo.toml", "package")]:
            stream = archive.extractfile(prefix + name)
            assert stream is not None
            if tomllib.loads(stream.read().decode())[section]["version"] != version:
                raise ValueError(f"version mismatch in {name}")
    print(f"{path.name}: complete source archive, version {version}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    archives = list(args.directory.glob("*.tar.gz"))
    if len(archives) != 1:
        raise ValueError("expected one source archive")
    root = Path(__file__).resolve().parents[1]
    version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    check_sdist(archives[0], version)


if __name__ == "__main__":
    main()

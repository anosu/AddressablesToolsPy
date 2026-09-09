"""Reject wheels with an unexpected ABI or deployment platform before installation."""

import argparse
from email.parser import Parser
from pathlib import Path
import tomllib
from zipfile import ZipFile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--platform", required=True)
    args = parser.parse_args()
    wheels = list(args.directory.glob("*.whl"))
    if len(wheels) != 1:
        raise ValueError(f"expected exactly one native wheel, found {len(wheels)}")
    wheel = wheels[0]
    root = Path(__file__).resolve().parents[1]
    with (root / "pyproject.toml").open("rb") as stream:
        version = tomllib.load(stream)["project"]["version"]
    with ZipFile(wheel) as archive:
        wheel_metadata = [name for name in archive.namelist() if name.endswith(".dist-info/WHEEL")]
        package_metadata = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(wheel_metadata) != 1 or len(package_metadata) != 1:
            raise ValueError("wheel must contain one set of package metadata")
        metadata = Parser().parsestr(archive.read(package_metadata[0]).decode())
        tags = Parser().parsestr(archive.read(wheel_metadata[0]).decode()).get_all("Tag", [])
        expected = f"cp312-abi3-{args.platform}"
        if expected not in tags or any(not tag.startswith("cp312-abi3-") for tag in tags):
            raise ValueError(f"expected {expected}, found {tags}")
        if metadata["Name"] != "addressablestools" or metadata["Version"] != version:
            raise ValueError("wheel package name/version does not match pyproject.toml")
        if metadata.get_all("Requires-Dist", []):
            raise ValueError("the unified wheel must not depend on a separate runtime package")
        names = archive.namelist()
        if not {"AddressablesTools.py", "addressablestools/__init__.py", "addressablestools/py.typed"} <= set(names):
            raise ValueError("Python API, legacy module or typing marker is missing")
        extensions = [name for name in names if name.endswith((".so", ".pyd"))]
        if len(extensions) != 1 or not extensions[0].startswith("addressablestools/_rust."):
            raise ValueError("expected one bundled addressablestools._rust extension")
    print(f"{wheel.name}: {expected}, version {version}")


if __name__ == "__main__":
    main()

"""Validate the complete platform set and write hashes for the release candidate."""

import argparse
from email.parser import Parser
import hashlib
import json
import os
from pathlib import Path
import tomllib
from zipfile import ZipFile

from check_sdist import check_sdist


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    platforms = {
        "manylinux_2_17_x86_64", "manylinux_2_17_aarch64",
        "macosx_10_13_x86_64", "macosx_11_0_arm64", "win_amd64",
    }
    wheels = sorted(args.directory.glob("*.whl"))
    archives = list(args.directory.glob("*.tar.gz"))
    if len(wheels) != 5 or len(archives) != 1 or len(list(args.directory.iterdir())) != 6:
        raise ValueError("release must contain exactly five wheels and one source archive")
    seen = set()
    for wheel in wheels:
        with ZipFile(wheel) as archive:
            names = archive.namelist()
            metadata = Parser().parsestr(archive.read(next(n for n in names if n.endswith(".dist-info/METADATA"))).decode())
            if metadata["Name"] != "addressablestools" or metadata["Version"] != version:
                raise ValueError(f"wrong release package in {wheel.name}")
            if metadata.get_all("Requires-Dist", []):
                raise ValueError(f"unexpected runtime dependency in {wheel.name}")
            info = Parser().parsestr(archive.read(next(n for n in names if n.endswith(".dist-info/WHEEL"))).decode())
            tags = info.get_all("Tag", [])
            matched = {p for p in platforms if f"cp312-abi3-{p}" in tags}
            if len(matched) != 1 or seen & matched or any(not t.startswith("cp312-abi3-") for t in tags):
                raise ValueError(f"invalid or duplicate platform in {wheel.name}")
            seen.update(matched)
    if seen != platforms:
        raise ValueError("missing release platform")
    check_sdist(archives[0], version)
    artifacts = [{"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                  "size": path.stat().st_size} for path in wheels + archives]
    report = {"version": version, "commit": os.environ.get("GITHUB_SHA"),
              "platforms": sorted(seen), "artifacts": artifacts}
    args.manifest.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Verified {version}: five platform wheels and one source archive")


if __name__ == "__main__":
    main()

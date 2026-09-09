# Publishing

Releases use PyPI Trusted Publishing through GitHub Actions. No PyPI API token
or repository secret is required.

## One-time setup

1. In the GitHub repository settings, create an environment named `pypi`.
2. Add required reviewers to the `pypi` environment so every production
   release requires explicit approval.
3. In the PyPI project publishing settings, add a GitHub Trusted Publisher
   with these values:

   - PyPI project: `addressablestools`
   - GitHub owner: `anosu`
   - Repository: `AddressablesToolsPy`
   - Workflow: `publish.yml`
   - Environment: `pypi`

For the first release, the same values can be registered as a pending publisher
from the PyPI account publishing settings.

## Release process

1. Update the version in `pyproject.toml` and
   `src/addressablestools/__init__.py`.
2. Add the release to `CHANGELOG.md`, refresh the lock file, and run the local
   checks:

   ```shell
   uv lock
   uv run python -m pytest -q
   uv run python -m ruff check .
   uv run python -m mypy
   uv build
   ```

3. Commit the release changes, create a matching version tag, and push it:

   ```shell
   VERSION=X.Y.Z
   git tag "v${VERSION}"
   git push origin "v${VERSION}"
   ```

The workflow rejects a tag that does not exactly match the version in
`pyproject.toml`. After verification and approval of the `pypi` environment, it
publishes the source distribution and wheel using OpenID Connect. The PyPA
publish action also uploads PEP 740 attestations by default.

## Native companion

The default dependency `addressablestools-rust` is versioned independently in
`native/pyproject.toml` and `native/Cargo.toml`. `uv sync --locked` resolves its local
source in a checkout; published metadata resolves it from the package index. The
old `native` extra remains accepted but no longer changes the dependency set.
Publish the required companion version and its platform wheels before releasing
the main package. The existing `publish.yml` publishes only the main package and
checks that compatible native wheels are available from PyPI for all five targets
before allowing publication. Bump the main package version before its next release;
the current checkout's packaging changes have not been published.

The `native.yml` workflow builds portable release wheels on native runners:

| Platform | Wheel target | Minimum platform |
| --- | --- | --- |
| Linux x86_64 | `manylinux_2_17_x86_64` / `manylinux2014_x86_64` | glibc 2.17 |
| Linux ARM64 | `manylinux_2_17_aarch64` / `manylinux2014_aarch64` | glibc 2.17 |
| macOS Intel | `macosx_10_13_x86_64` | macOS 10.13 |
| macOS Apple Silicon | `macosx_11_0_arm64` | macOS 11 |
| Windows x64 | `win_amd64` | Python-supported Windows x64 |

Each wheel uses `cp312-abi3` for standard GIL-enabled CPython 3.12 and newer.
Linux wheels are built inside manylinux2014 containers, rather than tagged after
compilation on a newer host. macOS wheels have explicit deployment targets.
Alpine/musl, 32-bit systems, Windows ARM64, PyPy, and free-threaded Python do not
have wheels in this matrix. The minimum platform tags describe the binaries;
runtime testing uses the current runners, not every historical OS release.

Before uploading an artifact, CI checks package metadata, exact platform/ABI tags,
stable ABI symbols (`abi3audit`), and Linux library requirements (`auditwheel`).
It requests only the main Python wheel in isolated Python 3.12 and 3.14 environments,
with the native wheel directory supplied as a package source. The dependency resolver
must install the native companion automatically. Source builds and package indexes
are disabled during these checks, ensuring the newly built wheel is tested. CI then runs the installed
wheel smoke check and the complete test suite. Tests import installed packages
using `-o pythonpath=`. All platform jobs and source checks must pass before the
`addressablestools-rust-distributions` artifact is assembled (five wheels and one
sdist).

Run the workflow by pushing changes that match its paths, or use its manual
dispatch once the workflow exists on the default branch. Download a successful
run's release candidates with:

```shell
gh run download RUN_ID --name addressablestools-rust-distributions --dir dist/native-release
```

For a local host-only build, use `uv build native`; it does not replace the portable
Linux build. Configure a separate Trusted Publisher/release workflow for the
companion before publishing it. The wheel workflow only stores artifacts and does
not publish either distribution.

## References

- [PyPI: Publishing with a Trusted Publisher](https://docs.pypi.org/trusted-publishers/using-a-publisher/)
- [Python Packaging User Guide: Publishing with GitHub Actions](https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/)

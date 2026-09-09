# Publishing

`addressablestools` 1.1 ships the Python API and Rust module in one wheel. There is
no separate native distribution, runtime dependency, or companion publishing order.
Releases use PyPI Trusted Publishing through GitHub Actions.

## One-time setup

1. Create the GitHub environment `pypi` and configure required reviewers for
   production releases.
2. Configure the PyPI Trusted Publisher (or pending publisher) with:
   - Project: `addressablestools`
   - Owner: `anosu`
   - Repository: `AddressablesToolsPy`
   - Workflow: `publish.yml`
   - Environment: `pypi`

The existing publisher identity is retained. No PyPI API token or repository
secret is required.

## Platforms

| Platform | Wheel tag | Binary deployment target |
| --- | --- | --- |
| Linux x86_64 | `manylinux_2_17_x86_64` / `manylinux2014_x86_64` | glibc 2.17 |
| Linux ARM64 | `manylinux_2_17_aarch64` / `manylinux2014_aarch64` | glibc 2.17 |
| macOS Intel | `macosx_10_13_x86_64` | macOS 10.13 |
| macOS Apple Silicon | `macosx_11_0_arm64` | macOS 11 |
| Windows x64 | `win_amd64` | Python-supported Windows x64 |

The wheels use `cp312-abi3` for standard GIL-enabled CPython 3.12+. Tests run on
current runners under Python 3.12 and 3.14; minimum platform tags are build targets,
not a claim that every historical OS was runtime-tested. Alpine/musl, 32-bit systems,
Windows ARM64, PyPy, and free-threaded Python are outside this wheel matrix.
Source builds require Rust 1.88+ and a platform C/C++ linker.

## Release preparation

1. Keep the version synchronized in `pyproject.toml`, `native/Cargo.toml`, and
   `src/addressablestools/__init__.py`. Update `CHANGELOG.md` and run:

   ```shell
   uv lock
   uv sync --locked
   uv run --no-sync python -m pytest -q
   uv run --no-sync python -m ruff check .
   uv run --no-sync python -m mypy
   cargo fmt --manifest-path native/Cargo.toml --check
   cargo clippy --locked --manifest-path native/Cargo.toml --lib -- -D warnings
   uv build --wheel --sdist --out-dir dist/local
   ```

2. Commit the candidate and run `native.yml` on that commit. It builds the complete
   sdist, verifies its contents, and builds all five wheels from that exact archive.
   Each wheel is checked with `twine`, `abi3audit`, and the package-content validator;
   Linux wheels also run `auditwheel`. Offline installation tests request only the
   single wheel, then run the smoke check and full test suite with `-o pythonpath=`
   to ensure the installed code is tested. Source-only Python fallback tests run
   separately, along with a Rust 1.88 compile check.
3. A fully successful run creates `addressablestools-distributions` (five wheels
   and one sdist) and `release-verification` (version, commit and SHA256 hashes):

   ```shell
   gh run download RUN_ID --name addressablestools-distributions --dir dist/release
   gh run download RUN_ID --name release-verification --dir dist/verification
   ```

Local `uv build` creates a host wheel; portable Linux wheels must come from the
manylinux build. Keep verification files outside the distribution upload directory.

## Publish an approved release

After review, tag the validated commit with its exact package version and push
that tag. For the 1.1.0 candidate:

```shell
git tag v1.1.0 APPROVED_COMMIT
git push origin v1.1.0
```

`publish.yml` rejects mismatched tags and calls the same reusable wheel-verification
workflow on the tagged source. Publication depends on all build, test and audit
jobs succeeding. After approval of the `pypi` environment, the PyPA publish action
uploads exactly that run's six verified distributions with OpenID Connect and
PEP 740 attestations. It does not rebuild packages in the publication job.

Preparing artifacts or pushing a verification branch does not publish to PyPI.
The 1.1.0 candidate is unpublished until the approved tag workflow completes.

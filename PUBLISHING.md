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

## References

- [PyPI: Publishing with a Trusted Publisher](https://docs.pypi.org/trusted-publishers/using-a-publisher/)
- [Python Packaging User Guide: Publishing with GitHub Actions](https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/)

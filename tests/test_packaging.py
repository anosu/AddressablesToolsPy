from pathlib import Path


def test_json_accelerator_dependency_is_removed_from_project_files() -> None:
    root = Path(__file__).parents[1]
    searchable = [
        root / "pyproject.toml",
        root / "src" / "addressablestools",
        root / "src" / "AddressablesTools.py",
    ]
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for item in searchable
        for path in ([item] if item.is_file() else item.rglob("*.py"))
    )

    assert "or" + "json" not in text


def test_readme_documents_new_package_first() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "from addressablestools import parse" in readme
    assert "Legacy compatibility" in readme
    assert "Deprecated API" in readme
    assert "## Parse JSON catalogs" in readme
    assert "## Parse binary catalogs" in readme
    assert "## Query resource locations" in readme
    assert "## Custom binary object handling" in readme


def test_project_version_is_100() -> None:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert 'version = "1.0.0"' in pyproject


def test_changelog_documents_current_release() -> None:
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    manifest = Path("MANIFEST.in").read_text(encoding="utf-8")

    assert "## [1.0.0] - 2026-08-10" in changelog
    assert "Binary catalog versions 1 through 3" in changelog
    assert "include CHANGELOG.md" in manifest


def test_pypi_workflow_uses_trusted_publishing() -> None:
    workflow = Path(".github/workflows/publish.yml").read_text(encoding="utf-8")
    publishing_guide = Path("PUBLISHING.md").read_text(encoding="utf-8")

    assert "pypa/gh-action-pypi-publish@release/v1" in workflow
    assert "actions/upload-artifact@v7" in workflow
    assert "actions/download-artifact@v8" in workflow
    assert "id-token: write" in workflow
    assert "environment:" in workflow
    assert "name: pypi" in workflow
    assert "uv sync --locked" in workflow
    assert "PYPI_TOKEN" not in workflow
    assert "password:" not in workflow
    assert "Trusted Publishing" in publishing_guide


def test_project_declares_reproducible_build_backend_and_modern_license() -> None:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert "[build-system]" in pyproject
    assert 'build-backend = "setuptools.build_meta"' in pyproject
    assert 'license = "MIT"' in pyproject
    assert 'license-files = ["LICENSE"]' in pyproject

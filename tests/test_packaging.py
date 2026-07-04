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


def test_project_version_is_020() -> None:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert 'version = "0.2.0"' in pyproject

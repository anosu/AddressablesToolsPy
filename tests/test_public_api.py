import pytest
from typing import Any, cast

import addressablestools
from addressablestools import parse, parse_binary, parse_json
from addressablestools.exceptions import CatalogParseError
from addressablestools.models import ContentCatalogData


def test_new_package_exports_parse_functions() -> None:
    assert addressablestools.parse is parse
    assert addressablestools.parse_json is parse_json
    assert addressablestools.parse_binary is parse_binary


def test_new_package_version_is_020() -> None:
    assert addressablestools.__version__ == "0.2.0"


def test_parse_dispatches_json_text(catalog_json_text: str) -> None:
    catalog = parse(catalog_json_text)

    assert isinstance(catalog, ContentCatalogData)
    assert catalog.resources


def test_parse_dispatches_binary_bytes(catalog_binary_bytes: bytes) -> None:
    catalog = parse(catalog_binary_bytes)

    assert isinstance(catalog, ContentCatalogData)
    assert catalog.resources


def test_parse_rejects_unsupported_input_type() -> None:
    with pytest.raises(CatalogParseError, match="str or bytes"):
        parse(cast(Any, {"not": "supported"}))

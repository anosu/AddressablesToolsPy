from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from addressablestools.exceptions import CatalogParseError

if TYPE_CHECKING:
    from addressablestools.binary import CatalogBinaryReader
    from addressablestools.models import ContentCatalogData

type Patcher = Callable[[str], str | None]
type Handler = Callable[["CatalogBinaryReader", int, bool], object]


def parse(
    data: str | bytes,
    patcher: Patcher | None = None,
    handler: Handler | None = None,
) -> ContentCatalogData:
    if isinstance(data, str):
        return parse_json(data)
    if isinstance(data, bytes):
        return parse_binary(data, patcher=patcher, handler=handler)
    raise CatalogParseError(f"catalog input must be str or bytes, got {type(data).__name__}")


def parse_json(data: str) -> ContentCatalogData:
    from addressablestools.catalog import parse_json_catalog

    return parse_json_catalog(data)


def parse_binary(
    data: bytes,
    patcher: Patcher | None = None,
    handler: Handler | None = None,
) -> ContentCatalogData:
    from addressablestools.catalog import parse_binary_catalog

    return parse_binary_catalog(data, patcher=patcher, handler=handler)

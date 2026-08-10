from __future__ import annotations

from typing import TYPE_CHECKING

from addressablestools.exceptions import CatalogParseError

if TYPE_CHECKING:
    from addressablestools.decoder import DecoderRegistry
    from addressablestools.models import ContentCatalogData


def parse(
    data: str | bytes,
    registry: DecoderRegistry | None = None,
) -> ContentCatalogData:
    """Parse JSON text or binary bytes into catalog data.

    Args:
        data: JSON catalog text or binary catalog bytes.
        registry: Custom decoder registry used for binary input.

    Raises:
        CatalogParseError: If the input or catalog data is invalid.
    """

    if isinstance(data, str):
        return parse_json(data)
    if isinstance(data, bytes):
        return parse_binary(data, registry=registry)
    raise CatalogParseError(f"catalog input must be str or bytes, got {type(data).__name__}")


def parse_json(data: str) -> ContentCatalogData:
    """Parse Unity Addressables JSON catalog text."""

    from addressablestools.catalog import parse_json_catalog

    return parse_json_catalog(data)


def parse_binary(
    data: bytes,
    registry: DecoderRegistry | None = None,
) -> ContentCatalogData:
    """Parse Unity Addressables binary catalog bytes.

    Args:
        data: Complete binary catalog payload.
        registry: Optional per-parse custom decoder registry.
    """

    from addressablestools.catalog import parse_binary_catalog

    return parse_binary_catalog(data, registry=registry)

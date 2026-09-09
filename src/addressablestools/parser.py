from __future__ import annotations

from typing import TYPE_CHECKING

from addressablestools._native import Backend
from addressablestools.exceptions import CatalogParseError

if TYPE_CHECKING:
    from addressablestools.decoder import DecoderRegistry
    from addressablestools.models import ContentCatalogData


def parse(
    data: str | bytes,
    registry: DecoderRegistry | None = None,
    *,
    backend: Backend = "auto",
) -> ContentCatalogData:
    """Parse JSON text or binary bytes into catalog data.

    Args:
        data: JSON catalog text or binary catalog bytes.
        registry: Custom decoder registry used for binary input.
        backend: Auto selection, pure Python, or an explicitly required Rust backend.

    Raises:
        CatalogParseError: If the input or catalog data is invalid.
    """

    if isinstance(data, str):
        return parse_json(data, backend=backend)
    if isinstance(data, bytes):
        return parse_binary(data, registry=registry, backend=backend)
    raise CatalogParseError(f"catalog input must be str or bytes, got {type(data).__name__}")


def parse_json(data: str, *, backend: Backend = "auto") -> ContentCatalogData:
    """Parse JSON catalog text using the requested resource decoding backend."""

    from addressablestools.catalog import parse_json_catalog

    return parse_json_catalog(data, backend=backend)


def parse_binary(
    data: bytes,
    registry: DecoderRegistry | None = None,
    *,
    backend: Backend = "auto",
) -> ContentCatalogData:
    """Parse Unity Addressables binary catalog bytes.

    Args:
        data: Complete binary catalog payload.
        registry: Optional per-parse custom decoder registry. Native API 3 uses
            Python object callbacks with Rust resource traversal.
        backend: Auto selection, pure Python, or an explicitly required Rust backend.
    """

    from addressablestools.catalog import parse_binary_catalog

    return parse_binary_catalog(data, registry=registry, backend=backend)

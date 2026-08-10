from io import BytesIO

import pytest

from addressablestools import DecoderRegistry, parse_binary
from addressablestools.binary import CatalogBinaryHeader, CatalogBinaryReader
from addressablestools.catalog import _decode_binary_resources
from addressablestools.exceptions import BinaryReadError
from addressablestools.models import ContentCatalogData


def test_parse_binary_returns_pythonic_catalog(catalog_binary_bytes: bytes) -> None:
    catalog = parse_binary(catalog_binary_bytes)

    assert isinstance(catalog, ContentCatalogData)
    assert catalog.version in {1, 2, 3}
    assert catalog.resources


def test_parse_binary_decodes_resource_location(catalog_binary_bytes: bytes) -> None:
    catalog = parse_binary(catalog_binary_bytes)
    location = catalog.resources["Anim/Network"][0]

    assert location.primary_key == "Anim/Network"
    assert location.internal_id == "Anim/Network"
    assert (
        location.provider_id
        == "UnityEngine.ResourceManagement.ResourceProviders.LegacyResourcesProvider"
    )
    assert location.type is not None
    assert location.type.class_name == "UnityEngine.AnimationClip"
    assert location.data is None
    assert location.dependencies == []


def test_parse_binary_accepts_decoder_registry(catalog_binary_bytes: bytes) -> None:
    catalog = parse_binary(catalog_binary_bytes, registry=DecoderRegistry())

    assert catalog.resources


def test_binary_resources_reject_odd_key_location_offset_count() -> None:
    reader = CatalogBinaryReader(BytesIO(b""))
    setattr(reader, "read_offset_array", lambda _offset: [1])
    header = CatalogBinaryHeader(0, 3, 0, 0, 0, 0, 0, 0)

    with pytest.raises(BinaryReadError, match="key/location offset array"):
        _decode_binary_resources(reader, header)

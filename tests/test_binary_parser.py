from io import BytesIO
import struct

import pytest

from addressablestools import DecoderRegistry, parse_binary
from addressablestools.binary import CatalogBinaryHeader, CatalogBinaryReader
from addressablestools.catalog import _decode_binary_resources
from addressablestools.exceptions import BinaryReadError
from addressablestools.models import ContentCatalogData, ResourceLocation


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


def test_custom_registry_does_not_use_registry_unaware_decoder(
    catalog_binary_bytes: bytes, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from addressablestools import catalog as catalog_module

    def unexpected_native_call(*args: object) -> None:
        raise AssertionError("custom registry must use the registry-aware decoder")

    monkeypatch.setattr(catalog_module, "_native_decode", unexpected_native_call)
    assert parse_binary(catalog_binary_bytes, registry=DecoderRegistry()).resources


def test_binary_resources_reject_odd_key_location_offset_count() -> None:
    reader = CatalogBinaryReader(BytesIO(b""))
    setattr(reader, "read_offset_array", lambda _offset: [1])
    header = CatalogBinaryHeader(0, 3, 0, 0, 0, 0, 0, 0)

    with pytest.raises(BinaryReadError, match="key/location offset array"):
        _decode_binary_resources(reader, header)


def test_buffer_and_stream_parsers_produce_equal_resources(catalog_binary_bytes: bytes) -> None:
    reader = CatalogBinaryReader(BytesIO(catalog_binary_bytes))
    header = CatalogBinaryHeader.read(reader)
    expected = _decode_binary_resources(reader, header)
    actual = parse_binary(catalog_binary_bytes).resources
    assert actual == expected
    for key, locations in actual.items():
        for location, expected_location in zip(locations, expected[key]):
            assert location._data_type == expected_location._data_type


def test_keys_share_locations_but_have_independent_lists(catalog_binary_bytes: bytes) -> None:
    catalog = parse_binary(catalog_binary_bytes)
    seen: dict[int, list[ResourceLocation]] = {}
    shared = 0
    for locations in catalog.resources.values():
        for location in locations:
            previous = seen.get(id(location))
            if previous is not None:
                assert previous is not locations
                assert any(item is location for item in previous)
                shared += 1
            seen[id(location)] = locations
    assert shared > 0


@pytest.mark.parametrize(
    ("byte_size", "payload", "message"),
    [
        (-4, b"", "non-negative"),
        (3, b"abc", "multiple of 4"),
        (4, b"\x00" * 4, "contain pairs"),
        (8, b"\x00" * 4, "truncated"),
    ],
)
def test_buffer_key_index_rejects_invalid_arrays(
    byte_size: int, payload: bytes, message: str
) -> None:
    data = struct.pack("<i", byte_size) + payload
    reader = CatalogBinaryReader(BytesIO(data), _buffer=data)
    header = CatalogBinaryHeader(0, 3, 4, 0, 0, 0, 0, 0)
    with pytest.raises(BinaryReadError, match=message):
        _decode_binary_resources(reader, header)


@pytest.mark.parametrize("use_buffer", [False, True])
@pytest.mark.parametrize("keys_offset", [4, 0xFFFFFFFF])
def test_empty_binary_key_index(use_buffer: bool, keys_offset: int) -> None:
    data = struct.pack("<i", 0)
    reader = CatalogBinaryReader(BytesIO(data), _buffer=data if use_buffer else None)
    header = CatalogBinaryHeader(0, 3, keys_offset, 0, 0, 0, 0, 0)
    assert _decode_binary_resources(reader, header) == {}

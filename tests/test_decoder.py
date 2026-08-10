from io import BytesIO
import json
import struct
import pytest

from addressablestools.binary import UINT32_MAX, BinaryReader, CatalogBinaryReader
from addressablestools.decoder import BinaryDecodeContext, DecoderRegistry, SerializedObjectDecoder
from addressablestools.exceptions import UnsupportedSerializedObjectError
from addressablestools.models import (
    AssetBundleRequestOptions,
    Hash128,
    SerializedType,
    TypeReference,
)


def test_decode_v1_ascii_string() -> None:
    payload = bytes([SerializedObjectDecoder.ObjectType.ASCII_STRING.value])
    payload += struct.pack("<i", 5) + b"hello"

    assert SerializedObjectDecoder.decode_v1(BinaryReader(BytesIO(payload))) == "hello"


def test_decode_v1_hash128() -> None:
    payload = bytes([SerializedObjectDecoder.ObjectType.HASH128.value])
    payload += bytes([4]) + b"abcd"

    assert SerializedObjectDecoder.decode_v1(BinaryReader(BytesIO(payload))) == Hash128("abcd")


def test_decode_v1_type_reference() -> None:
    payload = bytes([SerializedObjectDecoder.ObjectType.TYPE.value])
    payload += bytes([5]) + b"clsid"

    assert SerializedObjectDecoder.decode_v1(BinaryReader(BytesIO(payload))) == TypeReference(
        "clsid"
    )


def test_asset_bundle_request_options_json_decodes_standard_library_json() -> None:
    options_json = json.dumps(
        {
            "m_Hash": "hash",
            "m_Crc": 123,
            "m_BundleName": "bundle",
            "m_BundleSize": 456,
            "m_Timeout": 1,
            "m_RedirectLimit": 2,
            "m_RetryCount": 3,
            "m_ChunkedTransfer": False,
            "m_AssetLoadMode": 1,
            "m_UseCrcForCachedBundle": True,
            "m_UseUWRForLocalBundles": False,
            "m_ClearOtherCachedVersionsWhenLoaded": True,
        }
    )

    options = SerializedObjectDecoder.decode_asset_bundle_request_options_json(options_json)

    assert isinstance(options, AssetBundleRequestOptions)
    assert options.hash == "hash"
    assert options.crc == 123
    assert options.bundle_name == "bundle"
    assert options.bundle_size == 456
    assert options.common_info is not None
    assert options.common_info.version == 3


def test_decode_v2_raises_for_unsupported_type() -> None:
    reader = CatalogBinaryReader(BytesIO(b"\x00" * 32))
    setattr(reader, "seek", lambda _offset, _whence=0: None)
    setattr(reader, "read_uint32", iter([8, UINT32_MAX]).__next__)
    setattr(
        reader,
        "read_serialized_type",
        lambda _offset: SerializedType("Custom", "Unsupported"),
    )

    with pytest.raises(UnsupportedSerializedObjectError, match="Custom; Unsupported"):
        SerializedObjectDecoder.decode_v2(reader, 0)


@pytest.mark.parametrize(
    ("class_name", "expected"),
    [
        ("System.Int32", 0),
        ("System.Int64", 0),
        ("System.Boolean", False),
        ("System.String", None),
    ],
)
def test_decode_v2_supports_version_3_primitive_types(
    class_name: str,
    expected: object,
) -> None:
    reader = CatalogBinaryReader(BytesIO(b"\x00" * 32))
    reader.version = 3
    setattr(reader, "seek", lambda _offset, _whence=0: None)
    setattr(reader, "read_struct_from", lambda _parser, _offset: (8, UINT32_MAX))
    setattr(
        reader,
        "read_serialized_type",
        lambda _offset: SerializedType(None, class_name),
    )

    assert SerializedObjectDecoder.decode_v2(reader, 0) == expected


def test_decode_v2_uses_registered_custom_decoder() -> None:
    reader = CatalogBinaryReader(BytesIO(b"\x00" * 32))
    reader.version = 3
    setattr(reader, "seek", lambda _offset, _whence=0: None)
    setattr(reader, "read_struct_from", lambda _parser, _offset: (8, 12))
    setattr(
        reader,
        "read_serialized_type",
        lambda _offset: SerializedType("Custom.Assembly", "Custom.Metadata"),
    )
    registry = DecoderRegistry()

    @registry.register("Custom.Assembly; Custom.Metadata")
    def decode_custom(context: BinaryDecodeContext) -> tuple[str | None, int, bool]:
        return (
            context.serialized_type.class_name,
            context.offset,
            context.is_default,
        )

    assert SerializedObjectDecoder.decode_v2(reader, 0, registry=registry) == (
        "Custom.Metadata",
        12,
        False,
    )


def test_decoder_registry_aliases_custom_type_to_builtin() -> None:
    reader = CatalogBinaryReader(BytesIO(b"\x00" * 32))
    reader.version = 3
    setattr(reader, "seek", lambda _offset, _whence=0: None)
    setattr(reader, "read_uint32", iter([8, UINT32_MAX]).__next__)
    setattr(
        reader,
        "read_serialized_type",
        lambda _offset: SerializedType("Custom.Assembly", "Custom.Int32"),
    )
    registry = DecoderRegistry()
    registry.alias("Custom.Assembly; Custom.Int32", SerializedObjectDecoder.INT_V3_MATCH_NAME)

    assert SerializedObjectDecoder.decode_v2(reader, 0, registry=registry) == 0

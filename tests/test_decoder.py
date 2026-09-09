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


def test_cached_type_does_not_freeze_registry_decoders_or_aliases() -> None:
    reader = CatalogBinaryReader(BytesIO(struct.pack("<II", 8, UINT32_MAX)))
    serialized_type = SerializedType("Custom", "Value")
    setattr(reader, "read_serialized_type", lambda _offset: serialized_type)
    registry = DecoderRegistry()
    registry.alias("Custom; Value", SerializedObjectDecoder.INT_MATCH_NAME)
    assert SerializedObjectDecoder.decode_v2(reader, 0, registry) == 0

    contexts: list[BinaryDecodeContext] = []

    def custom(context: BinaryDecodeContext) -> str:
        contexts.append(context)
        return "custom"

    registry.register(SerializedObjectDecoder.INT_MATCH_NAME, custom)
    assert SerializedObjectDecoder.decode_v2(reader, 0, registry) == "custom"
    assert contexts[0].serialized_type is serialized_type
    assert contexts[0].is_default
    registry.alias("Custom; Value", SerializedObjectDecoder.BOOL_MATCH_NAME)
    assert SerializedObjectDecoder.decode_v2(reader, 0, registry) is False
    with pytest.raises(UnsupportedSerializedObjectError):
        SerializedObjectDecoder.decode_v2(reader, 0, DecoderRegistry())


def test_cached_type_match_name_accounts_for_reader_version() -> None:
    reader = CatalogBinaryReader(BytesIO(struct.pack("<II", 8, UINT32_MAX)))
    setattr(
        reader, "read_serialized_type",
        lambda _offset: SerializedType("mscorlib, Version=4.0.0.0", "System.Int32"),
    )
    assert SerializedObjectDecoder.decode_v2(reader, 0) == 0
    reader.version = 3
    with pytest.raises(UnsupportedSerializedObjectError, match="Version=4.0.0.0"):
        SerializedObjectDecoder.decode_v2(reader, 0)


@pytest.mark.parametrize("use_buffer", [False, True])
def test_binary_bundle_hash_byte_order_and_shared_common_info(use_buffer: bool) -> None:
    data = struct.pack(
        "<5I16shBBi", 20, UINT32_MAX, 123, 456, 36, bytes(range(16)), 5, 2, 3, 0,
    )
    reader = CatalogBinaryReader(BytesIO(data), _buffer=data if use_buffer else None)
    first = SerializedObjectDecoder.decode_asset_bundle_request_options_binary(reader, 0)
    second = SerializedObjectDecoder.decode_asset_bundle_request_options_binary(reader, 0)
    assert first.hash == "000102030405060708090a0b0c0d0e0f"
    assert first.crc == 123
    assert first.bundle_size == 456
    assert first.bundle_name is None
    assert first.common_info is second.common_info
    assert first.common_info is not None
    assert first.common_info.timeout == 5
    assert first.common_info.version == 3

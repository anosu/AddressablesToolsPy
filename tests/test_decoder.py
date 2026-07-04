from io import BytesIO
import json
import struct

import pytest

from addressablestools.binary import UINT32_MAX, BinaryReader, CatalogBinaryReader
from addressablestools.decoder import SerializedObjectDecoder
from addressablestools.exceptions import UnsupportedSerializedObjectError
from addressablestools.models import AssetBundleRequestOptions, Hash128, TypeReference


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

    assert SerializedObjectDecoder.decode_v1(BinaryReader(BytesIO(payload))) == TypeReference("clsid")


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


def test_decode_v2_calls_handler_when_patcher_returns_none() -> None:
    reader = CatalogBinaryReader(
        BytesIO(b"\x00" * 32),
        patcher=lambda _: None,
        handler=lambda _reader, offset, is_default: (offset, is_default),
    )
    reader.seek = lambda _offset, _whence=0: None  # type: ignore[method-assign]
    reader.read_uint32 = iter([8, UINT32_MAX]).__next__  # type: ignore[method-assign]
    reader.read_serialized_type = lambda _offset: type(  # type: ignore[method-assign]
        "FakeType",
        (),
        {"match_name": "Custom; System.Int32"},
    )()

    assert SerializedObjectDecoder.decode_v2(reader, 0) == (UINT32_MAX, True)


def test_decode_v2_raises_for_unsupported_type() -> None:
    reader = CatalogBinaryReader(BytesIO(b"\x00" * 32))
    reader.seek = lambda _offset, _whence=0: None  # type: ignore[method-assign]
    reader.read_uint32 = iter([8, UINT32_MAX]).__next__  # type: ignore[method-assign]
    reader.read_serialized_type = lambda _offset: type(  # type: ignore[method-assign]
        "FakeType",
        (),
        {"match_name": "Custom; Unsupported"},
    )()

    with pytest.raises(UnsupportedSerializedObjectError, match="Custom; Unsupported"):
        SerializedObjectDecoder.decode_v2(reader, 0)

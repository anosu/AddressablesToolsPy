from io import BytesIO
import struct

import pytest

from addressablestools.binary import (
    UINT32_MAX,
    BinaryReader,
    CatalogBinaryHeader,
    CatalogBinaryReader,
)
from addressablestools.exceptions import BinaryReadError, UnsupportedCatalogVersionError


def test_binary_reader_raises_binary_read_error_on_short_read() -> None:
    reader = BinaryReader(BytesIO(b"\x01\x02"))

    with pytest.raises(BinaryReadError, match="expected 4 bytes"):
        reader.read_int32()


def test_catalog_reader_rejects_invalid_offset_array_byte_size() -> None:
    data = struct.pack("<i", 3) + b"abc"
    reader = CatalogBinaryReader(BytesIO(data))

    with pytest.raises(BinaryReadError, match="multiple of 4"):
        reader.read_offset_array(4)


def test_catalog_reader_returns_empty_offset_array_for_uint32_max() -> None:
    reader = CatalogBinaryReader(BytesIO(b""))

    assert reader.read_offset_array(UINT32_MAX) == []


def test_binary_header_rejects_unsupported_version() -> None:
    header_bytes = struct.pack("<ii", 0, 99) + b"\x00" * 20
    reader = CatalogBinaryReader(BytesIO(header_bytes))

    with pytest.raises(UnsupportedCatalogVersionError, match="Only versions 1 and 2"):
        CatalogBinaryHeader.read(reader)

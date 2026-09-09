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


def test_binary_reader_rejects_negative_read_size() -> None:
    reader = BinaryReader(BytesIO(b"data"))

    with pytest.raises(BinaryReadError, match="non-negative"):
        reader.read_exact(-1)


@pytest.mark.parametrize("use_buffer", [False, True])
def test_binary_reader_reads_at_offset_without_changing_cursor(use_buffer: bool) -> None:
    data = b"xx" + struct.pack("<I", 0x12345678) + b"yy"
    stream = BytesIO(data)
    stream.seek(1)
    reader = BinaryReader(stream, _buffer=data if use_buffer else None)

    assert reader.read_struct_at(struct.Struct("<I"), 2) == (0x12345678,)
    assert reader.read_bytes_at(2, 4) == struct.pack("<I", 0x12345678)
    assert reader.tell() == 1


def test_binary_reader_rejects_out_of_range_offset_read() -> None:
    data = b"data"
    reader = BinaryReader(BytesIO(data), _buffer=data)

    with pytest.raises(BinaryReadError, match="position 2"):
        reader.read_struct_at(struct.Struct("<I"), 2)
    with pytest.raises(BinaryReadError, match="expected 4 bytes"):
        reader.read_bytes_at(2, 4)


@pytest.mark.parametrize("use_buffer", [False, True])
def test_catalog_reader_rejects_invalid_offset_array_byte_size(use_buffer: bool) -> None:
    data = struct.pack("<i", 3) + b"abc"
    reader = CatalogBinaryReader(BytesIO(data), _buffer=data if use_buffer else None)

    with pytest.raises(BinaryReadError, match="multiple of 4"):
        reader.read_offset_array(4)


@pytest.mark.parametrize("use_buffer", [False, True])
def test_catalog_reader_rejects_negative_offset_array_byte_size(use_buffer: bool) -> None:
    data = struct.pack("<i", -4)
    reader = CatalogBinaryReader(BytesIO(data), _buffer=data if use_buffer else None)

    with pytest.raises(BinaryReadError, match="non-negative"):
        reader.read_offset_array(4)


def test_catalog_reader_returns_empty_offset_array_for_uint32_max() -> None:
    reader = CatalogBinaryReader(BytesIO(b""))

    assert reader.read_offset_array(UINT32_MAX) == []


def test_binary_header_rejects_unsupported_version() -> None:
    header_bytes = struct.pack("<ii", 0, 99) + b"\x00" * 20
    reader = CatalogBinaryReader(BytesIO(header_bytes))

    with pytest.raises(UnsupportedCatalogVersionError, match="Only versions 1-3"):
        CatalogBinaryHeader.read(reader)


def test_binary_header_accepts_version_3() -> None:
    header_bytes = struct.pack("<ii6I", 0, 3, 32, 40, 48, 56, 64, 72)
    reader = CatalogBinaryReader(BytesIO(header_bytes))

    header = CatalogBinaryHeader.read(reader)

    assert header.version == 3
    assert reader.version == 3


def test_dynamic_string_cache_accounts_for_separator() -> None:
    data = (
        struct.pack("<IIIIi", 20, 8, 28, UINT32_MAX, 1)
        + b"a\x00\x00\x00"
        + struct.pack("<i", 1)
        + b"b"
    )
    reader = CatalogBinaryReader(BytesIO(data))
    encoded_offset = 0x40000000

    assert reader.read_encoded_string(encoded_offset, "/") == "a/b"
    assert reader.read_encoded_string(encoded_offset, ".") == "a.b"


def test_dynamic_string_rejects_cyclic_part_chain() -> None:
    data = struct.pack("<II", 12, 0) + struct.pack("<i", 0)
    reader = CatalogBinaryReader(BytesIO(data))

    with pytest.raises(BinaryReadError, match="cycle"):
        reader.read_encoded_string(0x40000000, "/")


@pytest.mark.parametrize("use_buffer", [False, True])
@pytest.mark.parametrize("version", [1, 2, 3])
@pytest.mark.parametrize("tail", [[], [None], [""], ["a", None, "", "b"]])
def test_dynamic_strings_share_tails_across_separators(
    use_buffer: bool, version: int, tail: list[str | None]
) -> None:
    data = bytearray()

    def node(value: str | None, next_offset: int) -> int:
        string_offset = UINT32_MAX
        if value is not None:
            encoded = value.encode("ascii")
            data.extend(struct.pack("<i", len(encoded)))
            string_offset = len(data)
            data.extend(encoded)
        offset = len(data)
        data.extend(struct.pack("<II", string_offset, next_offset))
        return offset

    tail_offset = UINT32_MAX
    for part in reversed(tail):
        tail_offset = node(part, tail_offset)
    roots = [node(part, tail_offset) for part in ("first", "second", None)]
    raw = bytes(data)
    reader = CatalogBinaryReader(BytesIO(raw), _buffer=raw if use_buffer else None)
    reader.version = version

    for separator in ("/", "."):
        for root, first in zip(roots, ("first", "second", None)):
            parts = [part for part in [first, *tail] if part is not None]
            if version > 1:
                parts.reverse()
            assert reader.read_encoded_string(root | 0x40000000, separator) == separator.join(parts)


@pytest.mark.parametrize("use_buffer", [False, True])
@pytest.mark.parametrize("length", [-1, 8])
def test_basic_string_rejects_invalid_length(use_buffer: bool, length: int) -> None:
    data = struct.pack("<i", length) + b"abc"
    reader = CatalogBinaryReader(BytesIO(data), _buffer=data if use_buffer else None)
    with pytest.raises(BinaryReadError):
        reader.read_encoded_string(4)


@pytest.mark.parametrize("offset", [0, 3, 9])
def test_buffer_reads_reject_invalid_length_prefix_offsets(offset: int) -> None:
    data = b"\x00" * 8
    reader = CatalogBinaryReader(BytesIO(data), _buffer=data)
    with pytest.raises(BinaryReadError):
        reader.read_encoded_string(offset)
    with pytest.raises(BinaryReadError):
        reader.read_offset_array(offset)


@pytest.mark.parametrize("use_buffer", [False, True])
def test_offset_array_rejects_truncated_payload(use_buffer: bool) -> None:
    data = struct.pack("<iI", 8, 123)
    reader = CatalogBinaryReader(BytesIO(data), _buffer=data if use_buffer else None)
    with pytest.raises(BinaryReadError):
        reader.read_offset_array(4)


@pytest.mark.parametrize("use_buffer", [False, True])
def test_buffer_string_decoding_preserves_utf16_and_empty_strings(use_buffer: bool) -> None:
    raw = "资源/🎮".encode("utf-16-le")
    data = struct.pack("<i", len(raw)) + raw + struct.pack("<i", 0)
    reader = CatalogBinaryReader(BytesIO(data), _buffer=data if use_buffer else None)
    assert reader.read_encoded_string(4 | 0x80000000) == "资源/🎮"
    assert reader.read_encoded_string(len(data)) == ""
    assert reader.read_encoded_string(len(data), "/") == ""

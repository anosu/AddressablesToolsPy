from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO
from struct import Struct, calcsize, error as StructError, unpack, unpack_from
from typing import TypeVar, cast

from addressablestools.exceptions import BinaryReadError, UnsupportedCatalogVersionError
from addressablestools.models import SerializedType

UINT32_MAX = 4_294_967_295
UINT32_MAX_MINUS_ONE = UINT32_MAX - 1

_INT16 = Struct("<h")
_UINT16 = Struct("<H")
_INT32 = Struct("<i")
_UINT32 = Struct("<I")
_INT64 = Struct("<q")
_UINT64 = Struct("<Q")
_BOOL = Struct("<?")
_TWO_UINT32 = Struct("<2I")
_FOUR_UINT32 = Struct("<4I")

T = TypeVar("T")


class BinaryReader:
    def __init__(self, stream: BytesIO, *, _buffer: bytes | None = None) -> None:
        self.stream = stream
        self._buffer = _buffer

    def seek(self, position: int, whence: int = 0) -> None:
        try:
            self.stream.seek(position, whence)
        except (OSError, ValueError) as exc:
            raise BinaryReadError(f"invalid seek to position {position}") from exc

    def tell(self) -> int:
        return self.stream.tell()

    def read_exact(self, count: int) -> bytes:
        if count < 0:
            raise BinaryReadError("read byte count must be non-negative")
        data = self.stream.read(count)
        if len(data) != count:
            raise BinaryReadError(f"expected {count} bytes, got {len(data)}")
        return data

    def read_byte(self) -> int:
        return self.read_exact(1)[0]

    def read_bytes(self, count: int) -> bytes:
        return self.read_exact(count)

    def read_int16(self) -> int:
        return cast(int, _INT16.unpack(self.read_exact(2))[0])

    def read_uint16(self) -> int:
        return cast(int, _UINT16.unpack(self.read_exact(2))[0])

    def read_int32(self) -> int:
        return cast(int, _INT32.unpack(self.read_exact(4))[0])

    def read_uint32(self) -> int:
        return cast(int, _UINT32.unpack(self.read_exact(4))[0])

    def read_int64(self) -> int:
        return cast(int, _INT64.unpack(self.read_exact(8))[0])

    def read_uint64(self) -> int:
        return cast(int, _UINT64.unpack(self.read_exact(8))[0])

    def read_boolean(self) -> bool:
        return cast(bool, _BOOL.unpack(self.read_exact(1))[0])

    def read_char(self) -> str:
        return self.read_exact(1).decode()

    def read_struct(self, parser: Struct) -> tuple[object, ...]:
        """Read one precompiled ``struct.Struct`` value."""

        return parser.unpack(self.read_exact(parser.size))

    def read_struct_at(self, parser: Struct, position: int) -> tuple[object, ...]:
        """Read a precompiled structure at an absolute position without changing the cursor."""

        if self._buffer is None:
            current_position = self.tell()
            self.seek(position)
            try:
                return self.read_struct(parser)
            finally:
                self.seek(current_position)
        if position < 0 or position + parser.size > len(self._buffer):
            raise BinaryReadError(
                f"expected {parser.size} bytes at position {position}, "
                f"buffer has {len(self._buffer)} bytes"
            )
        return parser.unpack_from(self._buffer, position)

    def read_struct_from(self, parser: Struct, position: int) -> tuple[object, ...]:
        """Read a structure at an absolute position, using the fast buffer when available."""

        if self._buffer is None:
            self.seek(position)
            return self.read_struct(parser)
        if position < 0 or position + parser.size > len(self._buffer):
            raise BinaryReadError(
                f"expected {parser.size} bytes at position {position}, "
                f"buffer has {len(self._buffer)} bytes"
            )
        return parser.unpack_from(self._buffer, position)

    def read_bytes_at(self, position: int, count: int) -> bytes:
        """Read bytes at an absolute position without changing the cursor."""

        if count < 0:
            raise BinaryReadError("read byte count must be non-negative")
        if self._buffer is None:
            current_position = self.tell()
            self.seek(position)
            try:
                return self.read_exact(count)
            finally:
                self.seek(current_position)
        end = position + count
        if position < 0 or end > len(self._buffer):
            available = max(0, len(self._buffer) - max(0, position))
            raise BinaryReadError(f"expected {count} bytes, got {available}")
        return self._buffer[position:end]

    def read_two_uint32(self) -> tuple[int, int]:
        return _TWO_UINT32.unpack(self.read_exact(_TWO_UINT32.size))

    def read_two_uint32_at(self, position: int) -> tuple[int, int]:
        return cast("tuple[int, int]", self.read_struct_at(_TWO_UINT32, position))

    def read_two_uint32_from(self, position: int) -> tuple[int, int]:
        return cast("tuple[int, int]", self.read_struct_from(_TWO_UINT32, position))

    def read_four_uint32(self) -> tuple[int, int, int, int]:
        return _FOUR_UINT32.unpack(self.read_exact(_FOUR_UINT32.size))

    def read_format(self, fmt: str) -> tuple[object, ...]:
        try:
            size = calcsize(fmt)
        except StructError as exc:
            raise BinaryReadError(f"invalid binary format {fmt!r}") from exc
        return unpack(fmt, self.read_exact(size))


class CatalogBinaryReader(BinaryReader):
    def __init__(self, stream: BytesIO, *, _buffer: bytes | None = None) -> None:
        super().__init__(stream, _buffer=_buffer)
        self.version = 1
        self._object_cache: dict[int, object] = {}
        self._string_cache: dict[int | tuple[int, str], str] = {}
        self._dynamic_tail_cache: dict[int, tuple[str, ...]] = {}
        self._type_name_cache: dict[int, tuple[int, SerializedType, str]] = {}

    def cache_and_return(self, offset: int, value: T) -> T:
        self._object_cache[offset] = value
        return value

    def try_get_cached_object(self, offset: int, expected_type: type[T]) -> T | None:
        cached = self._object_cache.get(offset)
        if isinstance(cached, expected_type):
            return cached
        return None

    def read_custom(self, offset: int, fetch: Callable[[], T]) -> T:
        if offset in self._object_cache:
            return cast(T, self._object_cache[offset])
        value = fetch()
        self._object_cache[offset] = value
        return value

    def _read_basic_string(self, offset: int, unicode: bool) -> str:
        buffer = self._buffer
        if buffer is None:
            self.seek(offset - _INT32.size)
            length = self.read_int32()
        else:
            if offset < _INT32.size or offset > len(buffer):
                raise BinaryReadError(f"invalid string offset {offset}")
            length = _INT32.unpack_from(buffer, offset - _INT32.size)[0]
        if length < 0:
            raise BinaryReadError("string byte length must be non-negative")
        if buffer is None:
            data = self.read_bytes(length)
        else:
            end = offset + length
            if end > len(buffer):
                raise BinaryReadError(f"expected {length} bytes, got {len(buffer) - offset}")
            data = buffer[offset:end]
        return data.decode("utf-16-le" if unicode else "ascii")

    def _read_dynamic_string(self, offset: int, separator: str) -> str:
        part_string_offset, next_part_offset = self.read_two_uint32_from(offset)
        first = self.read_encoded_string(part_string_offset)
        if next_part_offset == UINT32_MAX:
            return "" if first is None else first

        parts = [] if first is None else [first]
        visited_offsets = {offset}
        tail_offset = next_part_offset
        tail_start = len(parts)
        while next_part_offset != UINT32_MAX:
            cached_tail = self._dynamic_tail_cache.get(next_part_offset)
            if cached_tail is not None:
                parts.extend(cached_tail)
                break
            if next_part_offset in visited_offsets:
                raise BinaryReadError(
                    f"dynamic string part chain contains a cycle at offset {next_part_offset}"
                )
            visited_offsets.add(next_part_offset)
            part_string_offset, next_part_offset = self.read_two_uint32_from(next_part_offset)
            part = self.read_encoded_string(part_string_offset)
            if part is not None:
                parts.append(part)
        # Unity paths share linked tails. Cache the first tail, in wire order,
        # so later paths can skip it regardless of separator or catalog version.
        # Caching every suffix here would use quadratic space for a long chain.
        if tail_offset not in self._dynamic_tail_cache:
            self._dynamic_tail_cache[tail_offset] = tuple(parts[tail_start:])
        if len(parts) == 1:
            return parts[0]
        if self.version > 1:
            parts.reverse()
        return separator.join(parts)

    def read_encoded_string(
        self,
        encoded_offset: int,
        dynamic_separator: str = "\0",
    ) -> str | None:
        if encoded_offset == UINT32_MAX or encoded_offset == UINT32_MAX_MINUS_ONE:
            return None

        is_dynamic = (encoded_offset & 0x40000000) != 0 and dynamic_separator != "\0"
        cache_key = (encoded_offset, dynamic_separator) if is_dynamic else encoded_offset
        cached = self._string_cache.get(cache_key)
        if cached is not None:
            return cached

        is_unicode = (encoded_offset & 0x80000000) != 0
        offset = encoded_offset & 0x3FFFFFFF
        result = (
            self._read_dynamic_string(offset, dynamic_separator)
            if is_dynamic
            else self._read_basic_string(offset, is_unicode)
        )
        self._string_cache[cache_key] = result
        return result

    def read_offset_array(self, encoded_offset: int) -> list[int]:
        if encoded_offset == UINT32_MAX:
            return []
        cached = self._object_cache.get(encoded_offset)
        if isinstance(cached, list):
            return cached

        buffer = self._buffer
        if buffer is None:
            self.seek(encoded_offset - _INT32.size)
            byte_size = self.read_int32()
        else:
            if encoded_offset < _INT32.size or encoded_offset > len(buffer):
                raise BinaryReadError(f"invalid offset array position {encoded_offset}")
            byte_size = _INT32.unpack_from(buffer, encoded_offset - _INT32.size)[0]
        if byte_size < 0:
            raise BinaryReadError("offset array byte size must be non-negative")
        if byte_size % 4 != 0:
            raise BinaryReadError("offset array byte size must be a multiple of 4")
        fmt = f"<{byte_size // 4}I"
        if buffer is None:
            offsets = unpack(fmt, self.read_exact(byte_size))
        else:
            if encoded_offset + byte_size > len(buffer):
                raise BinaryReadError(
                    f"expected {byte_size} bytes at position {encoded_offset}, "
                    f"buffer has {len(buffer)} bytes"
                )
            offsets = unpack_from(fmt, buffer, encoded_offset)
        result = list(offsets)
        self._object_cache[encoded_offset] = result
        return result

    def read_serialized_type(self, offset: int) -> SerializedType:
        cached = self._object_cache.get(offset)
        if cached is not None:
            return cast(SerializedType, cached)
        value = _read_serialized_type(self, offset)
        self._object_cache[offset] = value
        return value


def _read_serialized_type(reader: CatalogBinaryReader, offset: int) -> SerializedType:
    assembly_name_offset, class_name_offset = reader.read_two_uint32_from(offset)
    return SerializedType(
        assembly_name=reader.read_encoded_string(assembly_name_offset, "."),
        class_name=reader.read_encoded_string(class_name_offset, "."),
    )


@dataclass(frozen=True, slots=True)
class CatalogBinaryHeader:
    magic: int
    version: int
    keys_offset: int
    id_offset: int
    instance_provider_offset: int
    scene_provider_offset: int
    init_objects_array_offset: int
    build_result_hash_offset: int

    @classmethod
    def read(cls, reader: CatalogBinaryReader) -> CatalogBinaryHeader:
        magic = reader.read_int32()
        version = reader.read_int32()
        if not 1 <= version <= 3:
            raise UnsupportedCatalogVersionError("Only versions 1-3 are supported")
        reader.version = version
        keys_offset = reader.read_uint32()
        id_offset = reader.read_uint32()
        instance_provider_offset = reader.read_uint32()
        scene_provider_offset = reader.read_uint32()
        init_objects_array_offset = reader.read_uint32()
        build_result_hash_offset = (
            UINT32_MAX if version == 1 and keys_offset == 0x20 else reader.read_uint32()
        )
        return cls(
            magic=magic,
            version=version,
            keys_offset=keys_offset,
            id_offset=id_offset,
            instance_provider_offset=instance_provider_offset,
            scene_provider_offset=scene_provider_offset,
            init_objects_array_offset=init_objects_array_offset,
            build_result_hash_offset=build_result_hash_offset,
        )


__all__ = [
    "BinaryReader",
    "CatalogBinaryHeader",
    "CatalogBinaryReader",
    "UINT32_MAX",
    "UINT32_MAX_MINUS_ONE",
]

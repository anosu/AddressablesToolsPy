from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO
from struct import Struct, calcsize, error as StructError, unpack
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
_FOUR_UINT32 = Struct("<4I")

T = TypeVar("T")


class BinaryReader:
    def __init__(self, stream: BytesIO) -> None:
        self.stream = stream

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

    def read_four_uint32(self) -> tuple[int, int, int, int]:
        return _FOUR_UINT32.unpack(self.read_exact(16))

    def read_format(self, fmt: str) -> tuple[object, ...]:
        try:
            size = calcsize(fmt)
        except StructError as exc:
            raise BinaryReadError(f"invalid binary format {fmt!r}") from exc
        return unpack(fmt, self.read_exact(size))


class CatalogBinaryReader(BinaryReader):
    def __init__(self, stream: BytesIO) -> None:
        super().__init__(stream)
        self.version = 1
        self._object_cache: dict[int, object] = {}
        self._string_cache: dict[tuple[int, str], str] = {}

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
        self.seek(offset - 4)
        length = self.read_int32()
        if length < 0:
            raise BinaryReadError("string byte length must be non-negative")
        data = self.read_bytes(length)
        return data.decode("utf-16-le" if unicode else "ascii")

    def _read_dynamic_string(self, offset: int, separator: str) -> str:
        parts: list[str] = []
        next_part_offset = offset
        visited_offsets: set[int] = set()
        while True:
            if next_part_offset in visited_offsets:
                raise BinaryReadError(
                    f"dynamic string part chain contains a cycle at offset {next_part_offset}"
                )
            visited_offsets.add(next_part_offset)
            self.seek(next_part_offset)
            part_string_offset = self.read_uint32()
            next_part_offset = self.read_uint32()
            part = self.read_encoded_string(part_string_offset)
            if part is not None:
                parts.append(part)
            if next_part_offset == UINT32_MAX:
                break
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
        if encoded_offset in {UINT32_MAX, UINT32_MAX_MINUS_ONE}:
            return None

        is_dynamic = (encoded_offset & 0x40000000) != 0 and dynamic_separator != "\0"
        cache_separator = dynamic_separator if is_dynamic else "\0"
        cache_key = (encoded_offset, cache_separator)
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
        cached = self.try_get_cached_object(encoded_offset, list)
        if cached is not None:
            return cached

        self.seek(encoded_offset - 4)
        byte_size = self.read_int32()
        if byte_size < 0:
            raise BinaryReadError("offset array byte size must be non-negative")
        if byte_size % 4 != 0:
            raise BinaryReadError("offset array byte size must be a multiple of 4")
        offsets = cast(tuple[int, ...], self.read_format(f"<{byte_size // 4}I"))
        return self.cache_and_return(encoded_offset, list(offsets))

    def read_serialized_type(self, offset: int) -> SerializedType:
        return self.read_custom(offset, lambda: _read_serialized_type(self, offset))


def _read_serialized_type(reader: CatalogBinaryReader, offset: int) -> SerializedType:
    reader.seek(offset)
    assembly_name_offset = reader.read_uint32()
    class_name_offset = reader.read_uint32()
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

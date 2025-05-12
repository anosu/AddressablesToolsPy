from io import BytesIO
from typing import TypeVar, Type, Callable, Any

from ..constants import uint
from .BinaryReader import BinaryReader

type Patcher = Callable[[str], str | None]
type Handler = Callable[[CatalogBinaryReader, int, bool], Any]

T = TypeVar("T")


class CatalogBinaryReader(BinaryReader):
    Version: int
    _objCache: dict[int, object]

    _patcher: Patcher
    _handler: Handler

    def __init__(
        self,
        stream: BytesIO,
        patcher: Patcher | None = None,
        handler: Handler | None = None,
    ):
        super().__init__(stream)
        self.Version = 1
        self._objCache = {}

        self._patcher = patcher if patcher else lambda s: s
        self._handler = handler if handler else lambda reader, offset, is_default: None

    def cache_and_return(self, offset: int, obj: T) -> T:
        self._objCache[offset] = obj
        return obj

    def try_get_cached_object(self, offset: int, objType: Type[T]) -> T | None:
        return self._objCache.get(offset, None)  # type: ignore

    def _read_basic_string(self, offset: int, unicode: bool) -> str:
        self.seek(offset - 4)
        length = self.read_int32()
        data = self.read_bytes(length)
        return data.decode("utf-16-le" if unicode else "ascii")

    def _read_dynamic_string(self, offset: int, sep: str) -> str:
        self.seek(offset)
        partStrs: list[str] = []
        while True:
            partStringOffset = self.read_uint32()
            nextPartOffset = self.read_uint32()
            partStrs.append(self.read_encoded_string(partStringOffset))  # type: ignore
            if nextPartOffset == uint.MaxValue:
                break
            self.seek(nextPartOffset)
        if len(partStrs) == 1:
            return partStrs[0]

        if self.Version > 1:
            partStrs.reverse()
        return sep.join(partStrs)

    def read_encoded_string(self, encodedOffset: int, dynSep: str = "\0") -> str | None:
        if encodedOffset == uint.MaxValue or encodedOffset == uint.MaxValue_:
            return None
        if (cachedStr := self.try_get_cached_object(encodedOffset, str)) is not None:
            return cachedStr

        unicode = (encodedOffset & 0x80000000) != 0
        dynamic = (encodedOffset & 0x40000000) != 0 and dynSep != "\0"
        offset = encodedOffset & 0x3FFFFFFF

        result = (
            self._read_dynamic_string(offset, dynSep)
            if dynamic
            else self._read_basic_string(offset, unicode)
        )
        return self.cache_and_return(encodedOffset, result)

    def read_offset_array(self, encodedOffset: int) -> list[int]:
        if encodedOffset == uint.MaxValue:
            return []
        if (
            cachedArr := self.try_get_cached_object(encodedOffset, list[int])
        ) is not None:
            return cachedArr

        self.seek(encodedOffset - 4)
        byteSize = self.read_int32()
        if byteSize % 4 != 0:
            raise Exception("Array size must be a multiple of 4")
        return self.cache_and_return(
            encodedOffset,
            list(self.read_format(f"<{byteSize // 4}I")),
        )

    def read_custom(self, offset: int, fetchFunc: Callable[[], T]) -> T:
        if offset in self._objCache:
            return self._objCache[offset]  # type: ignore
        return self._objCache.setdefault(offset, fetchFunc())  # type: ignore

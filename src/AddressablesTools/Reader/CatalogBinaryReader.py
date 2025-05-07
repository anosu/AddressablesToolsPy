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

    def CacheAndReturn(self, offset: int, obj: T) -> T:
        self._objCache[offset] = obj
        return obj

    def TryGetCachedObject(self, offset: int, objType: Type[T]) -> T | None:
        return self._objCache.get(offset, None)

    def _ReadBasicString(self, offset: int, unicode: bool) -> str:
        self.Seek(offset - 4)
        length = self.ReadInt32()
        data = self.ReadBytes(length)
        return data.decode("utf-16-le" if unicode else "ascii")

    def _ReadDynamicString(self, offset: int, sep: str) -> str:
        self.Seek(offset)
        partStrs: list[str] = []
        while True:
            partStringOffset = self.ReadUInt32()
            nextPartOffset = self.ReadUInt32()
            partStrs.append(self.ReadEncodedString(partStringOffset))
            if nextPartOffset == uint.MaxValue:
                break
            self.Seek(nextPartOffset)
        if len(partStrs) == 1:
            return partStrs[0]

        if self.Version > 1:
            partStrs.reverse()
        return sep.join(partStrs)

    def ReadEncodedString(self, encodedOffset: int, dynSep: str = "\0") -> str | None:
        if encodedOffset == uint.MaxValue or encodedOffset == uint.MaxValue_:
            return None
        if (cachedStr := self.TryGetCachedObject(encodedOffset, str)) is not None:
            return cachedStr

        unicode = (encodedOffset & 0x80000000) != 0
        dynamic = (encodedOffset & 0x40000000) != 0 and dynSep != "\0"
        offset = encodedOffset & 0x3FFFFFFF

        result = (
            self._ReadDynamicString(offset, dynSep)
            if dynamic
            else self._ReadBasicString(offset, unicode)
        )
        return self.CacheAndReturn(encodedOffset, result)

    def ReadOffsetArray(self, encodedOffset: int) -> list[int]:
        if encodedOffset == uint.MaxValue:
            return []
        if (cachedArr := self.TryGetCachedObject(encodedOffset, list[int])) is not None:
            return cachedArr

        self.Seek(encodedOffset - 4)
        byteSize = self.ReadInt32()
        if byteSize % 4 != 0:
            raise Exception("Array size must be a multiple of 4")
        return self.CacheAndReturn(
            encodedOffset,
            list(self.ReadFormat(f"<{byteSize // 4}I")),
        )

    def ReadCustom(self, offset: int, fetchFunc: Callable[[], T]) -> T:
        if offset in self._objCache:
            return self._objCache[offset]
        return self._objCache.setdefault(offset, fetchFunc())

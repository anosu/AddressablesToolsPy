from io import BytesIO
from struct import unpack
from typing import TypeVar, Type, Callable

from ..constants import uint
from .BinaryReader import BinaryReader

T = TypeVar("T")


class CatalogBinaryReader(BinaryReader):
    Version: int
    _objCache: dict[int, object]

    def __init__(self, stream: BytesIO):
        super().__init__(stream)
        self.Version = 1
        self._objCache = {}

    def CacheAndReturn(self, offset: int, obj: T) -> T:
        self._objCache[offset] = obj
        return obj

    def TryGetCachedObject(self, offset: int, objType: Type[T]) -> T | None:
        return self._objCache.get(offset, None)

    def _ReadBasicString(self, offset: int, unicode: bool) -> str:
        self.Seek(offset - 4)
        length = self.ReadInt32()
        data = self.ReadBytes(length)
        if unicode:
            # return data.decode('utf-8')
            return data.decode("utf-16-le")
        return data.decode("ascii")

    def _ReadDynamicString(self, offset: int, unicode: bool, sep: str) -> str:
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
            return sep.join(reversed(partStrs))
        return sep.join(partStrs)

    def ReadEncodedString(
        self, encodedOffset: int, dynstrSep: str = "\0"
    ) -> str | None:
        if encodedOffset == uint.MaxValue:
            return None
        if (cachedStr := self.TryGetCachedObject(encodedOffset, str)) is not None:
            return cachedStr

        unicode = (encodedOffset & 0x80000000) != 0
        dynamicString = (encodedOffset & 0x40000000) != 0 and dynstrSep != "\0"
        offset = encodedOffset & 0x3FFFFFFF

        if not dynamicString:
            return self.CacheAndReturn(offset, self._ReadBasicString(offset, unicode))
        return self.CacheAndReturn(
            offset, self._ReadDynamicString(offset, unicode, dynstrSep)
        )

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
            list(unpack(f"<{byteSize // 4}I", self.ReadBytes(byteSize))),
            # encodedOffset, [self.ReadUInt32() for _ in range(elemCount)]
        )

    def ReadCustom(self, offset: int, fetchFunc: Callable[[], T]) -> T:
        return self._objCache.setdefault(offset, fetchFunc())

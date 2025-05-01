from io import BytesIO
from struct import Struct

_INT16 = Struct("<h")
_UINT16 = Struct("<H")
_INT32 = Struct("<i")
_UINT32 = Struct("<I")
_INT64 = Struct("<q")
_UINT64 = Struct("<Q")
_BOOL = Struct("<?")


class BinaryReader:
    BaseStream: BytesIO

    def __init__(self, stream: BytesIO):
        self.BaseStream = stream

    def Seek(self, pos: int, whence: int = 0):
        self.BaseStream.seek(pos, whence)

    def Tell(self) -> int:
        return self.BaseStream.tell()

    def ReadByte(self) -> int:
        return self.BaseStream.read(1)[0]

    def ReadBytes(self, count: int) -> bytes:
        return self.BaseStream.read(count)

    def ReadInt16(self) -> int:
        return _INT16.unpack(self.BaseStream.read(2))[0]

    def ReadUInt16(self) -> int:
        return _UINT16.unpack(self.BaseStream.read(2))[0]

    def ReadInt32(self) -> int:
        return _INT32.unpack(self.BaseStream.read(4))[0]

    def ReadUInt32(self) -> int:
        return _UINT32.unpack(self.BaseStream.read(4))[0]

    def ReadInt64(self) -> int:
        return _INT64.unpack(self.BaseStream.read(8))[0]

    def ReadUInt64(self) -> int:
        return _UINT64.unpack(self.BaseStream.read(8))[0]

    def ReadBoolean(self) -> bool:
        return _BOOL.unpack(self.BaseStream.read(1))[0]

    def ReadChar(self) -> str:
        return self.BaseStream.read(1).decode()

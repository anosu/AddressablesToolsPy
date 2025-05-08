from io import BytesIO
from struct import Struct, unpack, calcsize

_INT16 = Struct("<h")
_UINT16 = Struct("<H")
_INT32 = Struct("<i")
_UINT32 = Struct("<I")
_INT64 = Struct("<q")
_UINT64 = Struct("<Q")
_BOOL = Struct("<?")

_4UINT32 = Struct("<4I")


class BinaryReader:
    BaseStream: BytesIO

    def __init__(self, stream: BytesIO):
        self.BaseStream = stream

    def seek(self, pos: int, whence: int = 0):
        self.BaseStream.seek(pos, whence)

    def tell(self) -> int:
        return self.BaseStream.tell()

    def read_byte(self) -> int:
        return self.BaseStream.read(1)[0]

    def read_bytes(self, count: int) -> bytes:
        return self.BaseStream.read(count)

    def read_int16(self) -> int:
        return _INT16.unpack(self.BaseStream.read(2))[0]

    def read_uint16(self) -> int:
        return _UINT16.unpack(self.BaseStream.read(2))[0]

    def read_int32(self) -> int:
        return _INT32.unpack(self.BaseStream.read(4))[0]

    def read_uint32(self) -> int:
        return _UINT32.unpack(self.BaseStream.read(4))[0]

    def read_int64(self) -> int:
        return _INT64.unpack(self.BaseStream.read(8))[0]

    def read_uint64(self) -> int:
        return _UINT64.unpack(self.BaseStream.read(8))[0]

    def read_boolean(self) -> bool:
        return _BOOL.unpack(self.BaseStream.read(1))[0]

    def read_char(self) -> str:
        return self.BaseStream.read(1).decode()

    def read_4uint32(self) -> tuple:
        return _4UINT32.unpack(self.BaseStream.read(16))

    def read_format(self, fmt: str) -> tuple:
        return unpack(fmt, self.BaseStream.read(calcsize(fmt)))

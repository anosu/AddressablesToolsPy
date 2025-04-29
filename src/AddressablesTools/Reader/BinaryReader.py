from io import BytesIO
from struct import unpack


class BinaryReader:
    BaseStream: BytesIO

    def __init__(self, stream: BytesIO):
        self.BaseStream = stream

    def ReadByte(self) -> int:
        return self.BaseStream.read(1)[0]

    def ReadBytes(self, count: int) -> bytes:
        return self.BaseStream.read(count)

    def ReadInt16(self) -> int:
        return unpack("<h", self.BaseStream.read(2))[0]

    def ReadUInt16(self) -> int:
        return unpack("<H", self.BaseStream.read(2))[0]

    def ReadInt32(self) -> int:
        return unpack("<i", self.BaseStream.read(4))[0]

    def ReadUInt32(self) -> int:
        return unpack("<I", self.BaseStream.read(4))[0]

    def ReadInt64(self) -> int:
        return unpack("<q", self.BaseStream.read(8))[0]

    def ReadUInt64(self) -> int:
        return unpack("<Q", self.BaseStream.read(8))[0]

    def ReadBoolean(self) -> bool:
        return unpack("<?", self.BaseStream.read(1))[0]

    def ReadChar(self) -> str:
        # return unpack('<c', self.BaseStream.read(1))[0].decode()
        return self.BaseStream.read(1).decode()

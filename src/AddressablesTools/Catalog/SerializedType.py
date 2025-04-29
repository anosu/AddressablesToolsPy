from ..Reader.CatalogBinaryReader import CatalogBinaryReader
from ..JSON.SerializedTypeJson import SerializedTypeJson


class SerializedType:
    AssemblyName: str | None
    ClassName: str | None

    def __repr__(self):
        return f"<{self.__class__.__name__}(AssemblyName={self.AssemblyName}, ClassName={self.ClassName})>"

    def __init__(self):
        self.AssemblyName = None
        self.ClassName = None

    def Equals(self, obj: object):
        return (
            isinstance(obj, SerializedType)
            and obj.AssemblyName == self.AssemblyName
            and obj.ClassName == self.ClassName
        )

    def GetHashCode(self):
        return hash((self.AssemblyName, self.ClassName))

    def ReadJson(self, type: SerializedTypeJson):
        self.AssemblyName = type.m_AssemblyName
        self.ClassName = type.m_ClassName

    def ReadBinary(self, reader: CatalogBinaryReader, offset: int):
        reader.BaseStream.seek(offset)
        assemblyNameOffset = reader.ReadUInt32()
        classNameOffset = reader.ReadUInt32()
        self.AssemblyName = reader.ReadEncodedString(assemblyNameOffset, ".")
        self.ClassName = reader.ReadEncodedString(classNameOffset, ".")

    def GetMatchName(self):
        return self.GetAssemblyShortName() + "; " + self.ClassName

    def GetAssemblyShortName(self):
        if "," not in self.AssemblyName:
            raise Exception("AssemblyName must have commas")
        return self.AssemblyName.split(",")[0]


__all__ = ["SerializedType"]

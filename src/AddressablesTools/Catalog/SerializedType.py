from ..Reader.CatalogBinaryReader import CatalogBinaryReader
from ..JSON.SerializedTypeJson import SerializedTypeJson


class SerializedType:
    __slots__ = ("AssemblyName", "ClassName")

    AssemblyName: str | None
    ClassName: str | None

    @classmethod
    def FromJson(cls, type: SerializedTypeJson):
        return cls(type.m_AssemblyName, type.m_ClassName)

    @classmethod
    def FromBinary(cls, reader: CatalogBinaryReader, offset: int):
        reader.Seek(offset)
        assemblyNameOffset = reader.ReadUInt32()
        classNameOffset = reader.ReadUInt32()
        return cls(
            reader.ReadEncodedString(assemblyNameOffset, "."),
            reader.ReadEncodedString(classNameOffset, "."),
        )

    def __repr__(self):
        return f"{self.__class__.__name__}(AssemblyName={self.AssemblyName}, ClassName={self.ClassName})"

    def __init__(self, assemblyName: str | None = None, className: str | None = None):
        self.AssemblyName = assemblyName
        self.ClassName = className

    def __eq__(self, obj: object):
        return (
            isinstance(obj, SerializedType)
            and obj.AssemblyName == self.AssemblyName
            and obj.ClassName == self.ClassName
        )

    def __hash__(self):
        return hash((self.AssemblyName, self.ClassName))

    def ReadJson(self, type: SerializedTypeJson):
        self.AssemblyName = type.m_AssemblyName
        self.ClassName = type.m_ClassName

    def ReadBinary(self, reader: CatalogBinaryReader, offset: int):
        reader.Seek(offset)
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

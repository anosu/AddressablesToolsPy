from ..Reader.CatalogBinaryReader import CatalogBinaryReader
from ..JSON.SerializedTypeJson import SerializedTypeJson


class SerializedType:
    __slots__ = ("AssemblyName", "ClassName")

    AssemblyName: str | None
    ClassName: str | None

    @classmethod
    def _from_json(cls, type: SerializedTypeJson):
        return cls(type.m_AssemblyName, type.m_ClassName)

    @classmethod
    def _from_binary(cls, reader: CatalogBinaryReader, offset: int):
        reader.seek(offset)
        assemblyNameOffset = reader.read_uint32()
        classNameOffset = reader.read_uint32()
        return cls(
            reader.read_encoded_string(assemblyNameOffset, "."),
            reader.read_encoded_string(classNameOffset, "."),
        )

    def __repr__(self):
        return f"{self.__class__.__name__}(AssemblyName={self.AssemblyName}, ClassName={self.ClassName})"

    def __init__(self, assemblyName: str | None, className: str | None):
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

    def _read_json(self, type: SerializedTypeJson):
        self.AssemblyName = type.m_AssemblyName
        self.ClassName = type.m_ClassName

    def _read_binary(self, reader: CatalogBinaryReader, offset: int):
        reader.seek(offset)
        assemblyNameOffset = reader.read_uint32()
        classNameOffset = reader.read_uint32()
        self.AssemblyName = reader.read_encoded_string(assemblyNameOffset, ".")
        self.ClassName = reader.read_encoded_string(classNameOffset, ".")

    def get_match_name(self):
        return self.get_assembly_short_name() + "; " + self.ClassName

    def get_assembly_short_name(self):
        if "," not in self.AssemblyName:
            raise Exception("AssemblyName must have commas")
        return self.AssemblyName.split(",")[0]


__all__ = ["SerializedType"]

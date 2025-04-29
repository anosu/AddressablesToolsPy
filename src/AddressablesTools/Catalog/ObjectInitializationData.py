from .SerializedType import SerializedType
from ..JSON.ObjectInitializationDataJson import ObjectInitializationDataJson
from ..Reader.CatalogBinaryReader import CatalogBinaryReader


class ObjectInitializationData:
    Id: str | None
    ObjectType: SerializedType | None
    Data: str | None

    def __repr__(self):
        return (
            f"<{self.__class__.__name__}(Id={self.Id}, ObjectType={self.ObjectType})>"
        )

    def __init__(self):
        self.Id = None
        self.ObjectType = None
        self.Data = None

    def ReadJson(self, obj: ObjectInitializationDataJson):
        self.Id = obj.m_Id
        self.ObjectType = SerializedType()
        self.ObjectType.ReadJson(obj.m_ObjectType)
        self.Data = obj.m_Data

    def ReadBinary(self, reader: CatalogBinaryReader, offset: int):
        reader.BaseStream.seek(offset)
        idOffset = reader.ReadUInt32()
        objectTypeOffset = reader.ReadUInt32()
        dataOffset = reader.ReadUInt32()

        self.Id = reader.ReadEncodedString(idOffset)
        self.ObjectType = SerializedType()
        self.ObjectType.ReadBinary(reader, objectTypeOffset)
        self.Data = reader.ReadEncodedString(dataOffset)


__all__ = ["ObjectInitializationData"]

from .SerializedType import SerializedType
from ..JSON.ObjectInitializationDataJson import ObjectInitializationDataJson
from ..Reader.CatalogBinaryReader import CatalogBinaryReader


class ObjectInitializationData:
    __slots__ = ("Id", "ObjectType", "Data")

    Id: str | None
    ObjectType: SerializedType | None
    Data: str | None

    @classmethod
    def FromJson(cls, obj: ObjectInitializationDataJson):
        return cls(obj.m_Id, SerializedType.FromJson(obj.m_ObjectType), obj.m_Data)

    @classmethod
    def FromBinary(cls, reader: CatalogBinaryReader, offset: int):
        reader.Seek(offset)
        idOffset = reader.ReadUInt32()
        objectTypeOffset = reader.ReadUInt32()
        dataOffset = reader.ReadUInt32()
        return cls(
            reader.ReadEncodedString(idOffset),
            SerializedType.FromBinary(reader, objectTypeOffset),
            reader.ReadEncodedString(dataOffset),
        )

    def __repr__(self):
        return f"{self.__class__.__name__}(Id={self.Id}, ObjectType={self.ObjectType}, Data={self.Data})"

    def __init__(
        self,
        id: str | None = None,
        objectType: SerializedType | None = None,
        data: str | None = None,
    ):
        self.Id = id
        self.ObjectType = objectType
        self.Data = data

    def ReadJson(self, obj: ObjectInitializationDataJson):
        self.Id = obj.m_Id
        self.ObjectType = SerializedType.FromJson(obj.m_ObjectType)
        self.Data = obj.m_Data

    def ReadBinary(self, reader: CatalogBinaryReader, offset: int):
        reader.Seek(offset)
        idOffset = reader.ReadUInt32()
        objectTypeOffset = reader.ReadUInt32()
        dataOffset = reader.ReadUInt32()

        self.Id = reader.ReadEncodedString(idOffset)
        self.ObjectType = SerializedType.FromBinary(reader, objectTypeOffset)
        self.Data = reader.ReadEncodedString(dataOffset)


__all__ = ["ObjectInitializationData"]

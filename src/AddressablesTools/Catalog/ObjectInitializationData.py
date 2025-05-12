from .SerializedType import SerializedType
from ..JSON.ObjectInitializationDataJson import ObjectInitializationDataJson
from ..Reader.CatalogBinaryReader import CatalogBinaryReader


class ObjectInitializationData:
    __slots__ = ("Id", "ObjectType", "Data")

    Id: str | None
    ObjectType: SerializedType
    Data: str | None

    @classmethod
    def _from_json(cls, obj: ObjectInitializationDataJson):
        return cls(obj.m_Id, SerializedType._from_json(obj.m_ObjectType), obj.m_Data)

    @classmethod
    def _from_binary(cls, reader: CatalogBinaryReader, offset: int):
        reader.seek(offset)
        idOffset = reader.read_uint32()
        objectTypeOffset = reader.read_uint32()
        dataOffset = reader.read_uint32()
        return cls(
            reader.read_encoded_string(idOffset),
            SerializedType._from_binary(reader, objectTypeOffset),
            reader.read_encoded_string(dataOffset),
        )

    def __repr__(self):
        return f"{self.__class__.__name__}(Id={self.Id}, ObjectType={self.ObjectType}, Data={self.Data})"

    def __init__(
        self,
        id: str | None,
        objectType: SerializedType,
        data: str | None,
    ):
        self.Id = id
        self.ObjectType = objectType
        self.Data = data

    def _read_json(self, obj: ObjectInitializationDataJson):
        self.Id = obj.m_Id
        self.ObjectType = SerializedType._from_json(obj.m_ObjectType)
        self.Data = obj.m_Data

    def _read_binary(self, reader: CatalogBinaryReader, offset: int):
        reader.seek(offset)
        idOffset = reader.read_uint32()
        objectTypeOffset = reader.read_uint32()
        dataOffset = reader.read_uint32()

        self.Id = reader.read_encoded_string(idOffset)
        self.ObjectType = SerializedType._from_binary(reader, objectTypeOffset)
        self.Data = reader.read_encoded_string(dataOffset)


__all__ = ["ObjectInitializationData"]

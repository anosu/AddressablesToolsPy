from __future__ import annotations

from .SerializedType import SerializedType
from .ClassJsonObject import ClassJsonObject
from .SerializedObjectDecoder import SerializedObjectDecoder
from ..Reader.CatalogBinaryReader import CatalogBinaryReader
from ..Classes.TypeReference import TypeReference
from ..Classes.Hash128 import Hash128
from ..Classes.AssetBundleRequestOptions import AssetBundleRequestOptions
from ..Catalog.WrappedSerializedObject import WrappedSerializedObject


class ResourceLocation:
    __slots__ = (
        "InternalId",
        "ProviderId",
        "DependencyKey",
        "Dependencies",
        "Data",
        "HashCode",
        "DependencyHashCode",
        "PrimaryKey",
        "Type",
    )

    InternalId: str | None
    ProviderId: str | None
    DependencyKey: object
    Dependencies: list[ResourceLocation] | None
    Data: (
        ClassJsonObject
        | TypeReference
        | Hash128
        | int
        | str
        | bool
        | WrappedSerializedObject[AssetBundleRequestOptions]
        | None
    )
    HashCode: int
    DependencyHashCode: int
    PrimaryKey: str | None
    Type: SerializedType | None

    @classmethod
    def _from_binary(cls, reader: CatalogBinaryReader, offset: int):
        obj = cls()
        obj._read_binary(reader, offset)
        return obj

    def __repr__(self):
        return (
            f"{self.__class__.__name__}("
            f"InternalId={self.InternalId}, "
            f"ProviderId={self.ProviderId}, "
            f"DependencyKey={self.DependencyKey}, "
            f"Dependencies={self.Dependencies}, "
            f"Data={self.Data}, "
            f"HashCode={self.HashCode}, "
            f"DependencyHashCode={self.DependencyHashCode}, "
            f"PrimaryKey={self.PrimaryKey}, "
            f"Type={self.Type}"
            f")"
        )

    def __init__(self):
        self.InternalId = None
        self.ProviderId = None
        self.DependencyKey = None
        self.Dependencies = None
        self.Data = None
        self.HashCode = 0
        self.DependencyHashCode = 0
        self.PrimaryKey = None
        self.Type = None

    def _read_json(
        self,
        internalId: str | None,
        providerId: str | None,
        dependencyKey: object,
        objData: (
            ClassJsonObject
            | TypeReference
            | Hash128
            | int
            | str
            | bool
            | WrappedSerializedObject[AssetBundleRequestOptions]
            | None
        ),
        depHash: int,
        primaryKey: object,
        resourceType: SerializedType | None,
    ):
        self.InternalId = internalId
        self.ProviderId = providerId
        self.DependencyKey = dependencyKey
        self.Dependencies = None
        self.Data = objData
        self.HashCode = hash(self.InternalId) * 31 + hash(self.ProviderId)
        self.DependencyHashCode = depHash
        self.PrimaryKey = str(primaryKey)
        self.Type = resourceType

    def _read_binary(self, reader: CatalogBinaryReader, offset: int):
        reader.seek(offset)
        primaryKeyOffset = reader.read_uint32()
        internalIdOffset = reader.read_uint32()
        providerIdOffset = reader.read_uint32()
        dependenciesOffset = reader.read_uint32()
        dependencyHashCode = reader.read_int32()
        dataOffset = reader.read_uint32()
        typeOffset = reader.read_uint32()

        self.PrimaryKey = reader.read_encoded_string(primaryKeyOffset, "/")
        self.InternalId = reader.read_encoded_string(internalIdOffset, "/")
        self.ProviderId = reader.read_encoded_string(providerIdOffset, ".")

        dependenciesOffsets = reader.read_offset_array(dependenciesOffset)
        dependencies: list[ResourceLocation] = []
        for objectOffset in dependenciesOffsets:
            dependencyLocation = reader.read_custom(
                objectOffset,
                lambda: ResourceLocation._from_binary(reader, objectOffset),
            )
            dependencies.append(dependencyLocation)

        self.DependencyKey = None
        self.Dependencies = dependencies

        self.DependencyHashCode = dependencyHashCode
        self.Data = SerializedObjectDecoder.decode_v2(
            reader, dataOffset, reader._patcher, reader._handler
        )
        # self.Type = SerializedType.FromBinary(reader, typeOffset)
        self.Type = reader.read_custom(
            typeOffset, lambda: SerializedType._from_binary(reader, typeOffset)
        )


__all__ = ["ResourceLocation"]

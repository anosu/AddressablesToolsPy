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

    def __repr__(self):
        return (
            f"<{self.__class__.__name__}("
            f"InternalId={self.InternalId}, "
            f"ProviderId={self.ProviderId}, "
            f"DependencyKey={self.DependencyKey}, "
            f"Dependencies={self.Dependencies}, "
            f"Data={self.Data}, "
            f"HashCode={self.HashCode}, "
            f"DependencyHashCode={self.DependencyHashCode}, "
            f"PrimaryKey={self.PrimaryKey}, "
            f"Type={self.Type}"
            f")>"
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

    def ReadJson(
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

    def ReadBinary(self, reader: CatalogBinaryReader, offset: int):
        reader.BaseStream.seek(offset)
        primaryKeyOffset = reader.ReadUInt32()
        internalIdOffset = reader.ReadUInt32()
        providerIdOffset = reader.ReadUInt32()
        dependenciesOffset = reader.ReadUInt32()
        dependencyHashCode = reader.ReadInt32()
        dataOffset = reader.ReadUInt32()
        typeOffset = reader.ReadUInt32()

        self.PrimaryKey = reader.ReadEncodedString(primaryKeyOffset, "/")
        self.InternalId = reader.ReadEncodedString(internalIdOffset, "/")
        self.ProviderId = reader.ReadEncodedString(providerIdOffset, ".")

        dependenciesOffsets = reader.ReadOffsetArray(dependenciesOffset)
        dependencies: list[ResourceLocation] = []
        for i in range(len(dependenciesOffsets)):
            objectOffset = dependenciesOffsets[i]
            dependencyLocation = reader.ReadCustom(
                objectOffset,
                lambda: (x := ResourceLocation()).ReadBinary(reader, objectOffset) or x,
            )
            dependencies.append(dependencyLocation)

        self.DependencyKey = None
        self.Dependencies = dependencies

        self.DependencyHashCode = dependencyHashCode
        self.Data = SerializedObjectDecoder.DecodeV2(reader, dataOffset)
        self.Type = SerializedType()
        self.Type.ReadBinary(reader, typeOffset)


__all__ = ["ResourceLocation"]

from io import BytesIO
from base64 import b64decode

from .ObjectInitializationData import ObjectInitializationData
from .ResourceLocation import ResourceLocation
from .SerializedObjectDecoder import SerializedObjectDecoder
from .SerializedType import SerializedType
from ..Binary.ContentCatalogDataBinaryHeader import ContentCatalogDataBinaryHeader
from ..JSON.ContentCatalogDataJson import ContentCatalogDataJson
from ..Reader.CatalogBinaryReader import CatalogBinaryReader
from ..Reader.BinaryReader import BinaryReader
from ..Catalog.ClassJsonObject import ClassJsonObject
from ..Classes.TypeReference import TypeReference
from ..Classes.Hash128 import Hash128
from ..Catalog.WrappedSerializedObject import WrappedSerializedObject
from ..Classes.AssetBundleRequestOptions import AssetBundleRequestOptions


class ContentCatalogData:
    Version: int

    LocatorId: str | None
    BuildResultHash: str | None
    InstanceProviderData: ObjectInitializationData | None
    SceneProviderData: ObjectInitializationData | None
    ResourceProviderData: list[ObjectInitializationData] | None
    ProviderIds: list[str] | None
    InternalIds: list[str] | None
    Keys: list[str] | None
    ResourceTypes: list[SerializedType] | None
    InternalIdPrefixes: list[str] | None
    Resources: dict[object, list[ResourceLocation]] | None

    class Bucket:
        __slots__ = ("offset", "entries")

        offset: int
        entries: list[int]

        def __repr__(self):
            return f"{self.__class__.__name__}(offset={self.offset}, entries={self.entries})"

        def __init__(self, offset: int, entries: list[int]):
            self.offset = offset
            self.entries = entries

    @classmethod
    def _from_json(cls, data: ContentCatalogDataJson):
        ccd = cls()
        ccd._ReadJson(data)
        return ccd

    @classmethod
    def _from_binary(cls, reader: CatalogBinaryReader):
        ccd = cls()
        ccd._read_binary(reader)
        return ccd

    def __repr__(self):
        return (
            f"{self.__class__.__name__}("
            f"LocatorId={self.LocatorId}, "
            f"BuildResultHash={self.BuildResultHash}, "
            f"InstanceProviderData={self.InstanceProviderData}, "
            f"SceneProviderData={self.SceneProviderData}, "
            f"ResourceProviderData={self.ResourceProviderData}, "
            f"ProviderIds={self.ProviderIds}, "
            f"InternalIds={self.InternalIds}, "
            f"Keys={self.Keys}, "
            f"ResourceTypes={self.ResourceTypes}, "
            f"InternalIdPrefixes={self.InternalIdPrefixes}, "
            f"Resources={self.Resources}"
            f")"
        )

    def __init__(self):
        self.Version = 0
        self.LocatorId = None
        self.BuildResultHash = None
        self.InstanceProviderData = None
        self.SceneProviderData = None
        self.ResourceProviderData = None
        self.ProviderIds = None
        self.InternalIds = None
        self.Keys = None
        self.ResourceTypes = None
        self.InternalIdPrefixes = None
        self.Resources = None

    def _ReadJson(self, data: ContentCatalogDataJson):
        self.LocatorId = data.m_LocatorId
        self.BuildResultHash = data.m_BuildResultHash

        self.InstanceProviderData = ObjectInitializationData._from_json(
            data.m_InstanceProviderData
        )

        self.SceneProviderData = ObjectInitializationData._from_json(
            data.m_SceneProviderData
        )

        self.ResourceProviderData = [
            ObjectInitializationData._from_json(data)
            for data in data.m_ResourceProviderData
        ]

        self.ProviderIds = list(data.m_ProviderIds)
        self.InternalIds = list(data.m_InternalIds)
        self.Keys = list(data.m_Keys) if data.m_Keys is not None else None

        self.ResourceTypes = [
            SerializedType._from_json(type) for type in data.m_resourceTypes
        ]

        self.InternalIdPrefixes = (
            list(data.m_InternalIdPrefixes)
            if data.m_InternalIdPrefixes is not None
            else None
        )

        self._read_resources_json(data)

    def _read_binary(self, reader: CatalogBinaryReader):
        header = ContentCatalogDataBinaryHeader()
        header._read(reader)

        self.Version = reader.Version

        self.LocatorId = reader.read_encoded_string(header.IdOffset)
        self.BuildResultHash = reader.read_encoded_string(header.BuildResultHashOffset)

        self.InstanceProviderData = ObjectInitializationData._from_binary(
            reader, header.InstanceProviderOffset
        )

        self.SceneProviderData = ObjectInitializationData._from_binary(
            reader, header.SceneProviderOffset
        )

        resourceProviderDataOffsets = reader.read_offset_array(
            header.InitObjectsArrayOffset
        )
        self.ResourceProviderData = [
            ObjectInitializationData._from_binary(reader, offset)
            for offset in resourceProviderDataOffsets
        ]

        self._read_resources_binary(reader, header)

    def _read_resources_json(self, data: ContentCatalogDataJson):
        buckets: list[ContentCatalogData.Bucket] = []

        bucketStream = BytesIO(b64decode(data.m_BucketDataString))
        bucketReader = BinaryReader(bucketStream)
        bucketCount = bucketReader.read_int32()
        for i in range(bucketCount):
            offset = bucketReader.read_int32()
            entryCount = bucketReader.read_int32()
            entries = list(bucketReader.read_format(f"<{entryCount}i"))
            buckets.append(ContentCatalogData.Bucket(offset, entries))

        keys: list[
            ClassJsonObject
            | TypeReference
            | Hash128
            | int
            | str
            | WrappedSerializedObject[AssetBundleRequestOptions]
        ] = []

        keyDataStream = BytesIO(b64decode(data.m_KeyDataString))
        keyReader = BinaryReader(keyDataStream)
        keyCount = keyReader.read_int32()
        for i in range(keyCount):
            keyDataStream.seek(buckets[i].offset)
            keys.append(SerializedObjectDecoder.decode_v1(keyReader))

        locations: list[ResourceLocation] = []

        entryDataStream = BytesIO(b64decode(data.m_EntryDataString))
        extraDataStream = BytesIO(b64decode(data.m_ExtraDataString))
        entryReader = BinaryReader(entryDataStream)
        extraReader = BinaryReader(extraDataStream)
        entryCount = entryReader.read_int32()
        for i in range(entryCount):
            internalIdIndex = entryReader.read_int32()
            providerIndex = entryReader.read_int32()
            dependencyKeyIndex = entryReader.read_int32()
            depHash = entryReader.read_int32()
            dataIndex = entryReader.read_int32()
            primaryKeyIndex = entryReader.read_int32()
            resourceTypeIndex = entryReader.read_int32()

            internalId = self.InternalIds[internalIdIndex]
            splitIndex = internalId.find("#")
            if splitIndex != -1:
                try:
                    prefixIndex = int(internalId[:splitIndex])
                    internalId = (
                        self.InternalIdPrefixes[prefixIndex]
                        + internalId[splitIndex + 1 :]
                    )
                except ValueError:
                    pass

            providerId = self.ProviderIds[providerIndex]

            dependencyKey = (
                keys[dependencyKeyIndex] if dependencyKeyIndex >= 0 else None
            )

            if dataIndex >= 0:
                extraDataStream.seek(dataIndex)
                objData = SerializedObjectDecoder.decode_v1(extraReader)
            else:
                objData = None

            primaryKey = (
                keys[primaryKeyIndex]
                if self.Keys is None
                else self.Keys[primaryKeyIndex]
            )

            resourceType = self.ResourceTypes[resourceTypeIndex]

            loc = ResourceLocation()
            loc._read_json(
                internalId,
                providerId,
                dependencyKey,
                objData,
                depHash,
                primaryKey,
                resourceType,
            )
            locations.append(loc)

        self.Resources = {
            keys[i]: [locations[entry] for entry in bucket.entries]
            for i, bucket in enumerate(buckets)
        }

    def _read_resources_binary(
        self, reader: CatalogBinaryReader, header: ContentCatalogDataBinaryHeader
    ):
        keyLocationOffsets = reader.read_offset_array(header.KeysOffset)
        self.Resources = {}
        for i in range(0, len(keyLocationOffsets), 2):
            keyOffset = keyLocationOffsets[i]
            locationListOffset = keyLocationOffsets[i + 1]
            key = SerializedObjectDecoder.decode_v2(
                reader, keyOffset, reader._patcher, reader._handler
            )

            locationOffsets = reader.read_offset_array(locationListOffset)
            self.Resources[key] = [
                reader.read_custom(
                    offset, lambda: ResourceLocation._from_binary(reader, offset)
                )
                for offset in locationOffsets
            ]


__all__ = ["ContentCatalogData"]

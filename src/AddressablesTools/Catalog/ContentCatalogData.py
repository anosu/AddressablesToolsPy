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

    Header: ContentCatalogDataBinaryHeader | None

    class Bucket:
        offset: int
        entries: list[int]

        def __repr__(self):
            return f"<{self.__class__.__name__}>"

        def __init__(self, offset: int, entries: list[int]):
            self.offset = offset
            self.entries = entries

    def __repr__(self):
        return f"<{self.__class__.__name__}(LocatorId={self.LocatorId}, BuildResultHash={self.BuildResultHash})>"

    def __init__(self):
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

        self.Header = None

    def ReadJson(self, data: ContentCatalogDataJson):
        self.LocatorId = data.m_LocatorId
        self.BuildResultHash = data.m_BuildResultHash

        self.InstanceProviderData = ObjectInitializationData()
        self.InstanceProviderData.ReadJson(data.m_InstanceProviderData)

        self.SceneProviderData = ObjectInitializationData()
        self.SceneProviderData.ReadJson(data.m_SceneProviderData)

        self.ResourceProviderData = []
        for i in range(len(data.m_ResourceProviderData)):
            o = ObjectInitializationData()
            o.ReadJson(data.m_ResourceProviderData[i])
            self.ResourceProviderData.append(o)

        self.ProviderIds = []
        for i in range(len(data.m_ProviderIds)):
            self.ProviderIds.append(data.m_ProviderIds[i])

        self.InternalIds = []
        for i in range(len(data.m_InternalIds)):
            self.InternalIds.append(data.m_InternalIds[i])

        if data.m_Keys is not None:
            self.Keys = []
            for i in range(len(data.m_Keys)):
                self.Keys.append(data.m_Keys[i])
        else:
            self.Keys = None

        self.ResourceTypes = []
        for i in range(len(data.m_resourceTypes)):
            o = SerializedType()
            o.ReadJson(data.m_resourceTypes[i])
            self.ResourceTypes.append(o)

        if data.m_InternalIdPrefixes is not None:
            self.InternalIdPrefixes = []
            for i in range(len(data.m_InternalIdPrefixes)):
                self.InternalIdPrefixes.append(data.m_InternalIdPrefixes[i])
        else:
            self.InternalIdPrefixes = None

        self.ReadResourcesJson(data)

    def ReadBinary(self, reader: CatalogBinaryReader):
        header = ContentCatalogDataBinaryHeader()
        header.Read(reader)

        self.Version = reader.Version
        self.Header = header

        self.LocatorId = reader.ReadEncodedString(header.IdOffset)
        self.BuildResultHash = reader.ReadEncodedString(header.BuildResultHashOffset)

        self.InstanceProviderData = ObjectInitializationData()
        self.InstanceProviderData.ReadBinary(reader, header.InstanceProviderOffset)

        self.SceneProviderData = ObjectInitializationData()
        self.SceneProviderData.ReadBinary(reader, header.SceneProviderOffset)

        resourceProviderDataOffsets = reader.ReadOffsetArray(
            header.InitObjectsArrayOffset
        )
        self.ResourceProviderData = []
        for i in range(len(resourceProviderDataOffsets)):
            o = ObjectInitializationData()
            o.ReadBinary(reader, resourceProviderDataOffsets[i])
            self.ResourceProviderData.append(o)

        self.ReadResourcesBinary(reader, header)

    def ReadResourcesJson(self, data: ContentCatalogDataJson):
        buckets: list[ContentCatalogData.Bucket] = []

        bucketStream = BytesIO(b64decode(data.m_BucketDataString))
        bucketReader = BinaryReader(bucketStream)
        bucketCount = bucketReader.ReadInt32()
        for i in range(bucketCount):
            offset = bucketReader.ReadInt32()
            entryCount = bucketReader.ReadInt32()
            entries: list[int] = []
            for j in range(entryCount):
                entries.append(bucketReader.ReadInt32())
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
        keyCount = keyReader.ReadInt32()
        for i in range(keyCount):
            keyDataStream.seek(buckets[i].offset)
            keys.append(SerializedObjectDecoder.DecodeV1(keyReader))

        locations: list[ResourceLocation] = []

        entryDataStream = BytesIO(b64decode(data.m_EntryDataString))
        extraDataStream = BytesIO(b64decode(data.m_ExtraDataString))
        entryReader = BinaryReader(entryDataStream)
        extraReader = BinaryReader(extraDataStream)
        entryCount = entryReader.ReadInt32()
        for i in range(entryCount):
            internalIdIndex = entryReader.ReadInt32()
            providerIndex = entryReader.ReadInt32()
            dependencyKeyIndex = entryReader.ReadInt32()
            depHash = entryReader.ReadInt32()
            dataIndex = entryReader.ReadInt32()
            primaryKeyIndex = entryReader.ReadInt32()
            resourceTypeIndex = entryReader.ReadInt32()

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
                objData = SerializedObjectDecoder.DecodeV1(extraReader)
            else:
                objData = None

            if self.Keys is None:
                primaryKey = keys[primaryKeyIndex]
            else:
                primaryKey = self.Keys[primaryKeyIndex]

            resourceType = self.ResourceTypes[resourceTypeIndex]

            loc = ResourceLocation()
            loc.ReadJson(
                internalId,
                providerId,
                dependencyKey,
                objData,
                depHash,
                primaryKey,
                resourceType,
            )
            locations.append(loc)

        self.Resources = {}
        for i in range(len(buckets)):
            bucketEntries = buckets[i].entries
            locs = []
            for j in range(len(bucketEntries)):
                locs.append(locations[bucketEntries[j]])
            self.Resources[keys[i]] = locs

    def ReadResourcesBinary(
        self, reader: CatalogBinaryReader, header: ContentCatalogDataBinaryHeader
    ):
        keyLocationOffsets = reader.ReadOffsetArray(header.KeysOffset)
        self.Resources = {}
        for i in range(0, len(keyLocationOffsets), 2):
            keyOffset = keyLocationOffsets[i]
            locationListOffset = keyLocationOffsets[i + 1]
            key = SerializedObjectDecoder.DecodeV2(reader, keyOffset)

            locationOffsets = reader.ReadOffsetArray(locationListOffset)
            locations = []
            for j in range(len(locationOffsets)):
                location = ResourceLocation()
                location.ReadBinary(reader, locationOffsets[j])
                locations.append(location)

            self.Resources[key] = locations


__all__ = ["ContentCatalogData"]

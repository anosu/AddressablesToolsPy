import json
from io import BytesIO

from .CatalogFileType import CatalogFileType
from .JSON.ContentCatalogDataJson import ContentCatalogDataJson
from .JSON.ObjectInitializationDataJson import ObjectInitializationDataJson
from .JSON.SerializedTypeJson import SerializedTypeJson
from .Catalog.ContentCatalogData import ContentCatalogData
from .Reader.CatalogBinaryReader import CatalogBinaryReader


def serializedTypeDecoder(obj: dict):
    return SerializedTypeJson.New(obj["m_AssemblyName"], obj["m_ClassName"])


def objectInitializationDataDecoder(obj: dict):
    _m_ObjectType = obj["m_ObjectType"]
    m_ObjectType = SerializedTypeJson.New(
        _m_ObjectType["m_AssemblyName"], _m_ObjectType["m_ClassName"]
    )
    return ObjectInitializationDataJson.New(obj["m_Id"], m_ObjectType, obj["m_Data"])


def contentCatalogDataDecoder(obj: dict):
    _m_InstanceProviderData = obj["m_InstanceProviderData"]
    _m_SceneProviderData = obj["m_SceneProviderData"]
    _m_ResourceProviderData = obj["m_ResourceProviderData"]

    m_InstanceProviderData = ObjectInitializationDataJson.New(
        _m_InstanceProviderData["m_Id"],
        SerializedTypeJson.New(
            _m_InstanceProviderData["m_ObjectType"]["m_AssemblyName"],
            _m_InstanceProviderData["m_ObjectType"]["m_ClassName"],
        ),
        _m_InstanceProviderData["m_Data"],
    )

    m_SceneProviderData = ObjectInitializationDataJson.New(
        _m_SceneProviderData["m_Id"],
        SerializedTypeJson.New(
            _m_SceneProviderData["m_ObjectType"]["m_AssemblyName"],
            _m_SceneProviderData["m_ObjectType"]["m_ClassName"],
        ),
        _m_SceneProviderData["m_Data"],
    )

    m_ResourceProviderData = [
        ObjectInitializationDataJson.New(
            o["m_Id"],
            SerializedTypeJson.New(
                o["m_ObjectType"]["m_AssemblyName"], o["m_ObjectType"]["m_ClassName"]
            ),
            o["m_Data"],
        )
        for o in _m_ResourceProviderData
    ]

    return ContentCatalogDataJson.New(
        obj["m_LocatorId"],
        obj.get("m_BuildResultHash"),
        m_InstanceProviderData,
        m_SceneProviderData,
        m_ResourceProviderData,
        obj["m_ProviderIds"],
        obj["m_InternalIds"],
        obj["m_KeyDataString"],
        obj["m_BucketDataString"],
        obj["m_EntryDataString"],
        obj["m_ExtraDataString"],
        obj.get("m_Keys"),
        [
            SerializedTypeJson.New(o["m_AssemblyName"], o["m_ClassName"])
            for o in obj["m_resourceTypes"]
        ],
        obj.get("m_InternalIdPrefixes"),
    )


class AddressablesCatalogFileParser:
    @staticmethod
    def CCDJsonFromString(data: str) -> ContentCatalogDataJson:
        return contentCatalogDataDecoder(json.loads(data))

    @staticmethod
    def FromBinaryData(data: bytes) -> ContentCatalogData:
        ms = BytesIO(data)
        reader = CatalogBinaryReader(ms)
        catalogData = ContentCatalogData()
        catalogData.ReadBinary(reader)
        return catalogData

    @staticmethod
    def FromJsonString(data: str) -> ContentCatalogData:
        ccdJson = AddressablesCatalogFileParser.CCDJsonFromString(data)
        catalogData = ContentCatalogData()
        catalogData.ReadJson(ccdJson)
        return catalogData

    @staticmethod
    def GetCatalogFileType() -> CatalogFileType:
        return CatalogFileType.Null


__all__ = ["AddressablesCatalogFileParser"]

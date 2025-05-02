import orjson as json
from io import BytesIO

from .JSON.ContentCatalogDataJson import ContentCatalogDataJson
from .JSON.ObjectInitializationDataJson import ObjectInitializationDataJson
from .JSON.SerializedTypeJson import SerializedTypeJson
from .Catalog.ContentCatalogData import ContentCatalogData
from .Reader.CatalogBinaryReader import CatalogBinaryReader


def serializedTypeDecoder(obj: dict):
    return SerializedTypeJson(obj["m_AssemblyName"], obj["m_ClassName"])


def objectInitializationDataDecoder(obj: dict):
    _m_ObjectType = obj["m_ObjectType"]
    m_ObjectType = SerializedTypeJson(
        _m_ObjectType["m_AssemblyName"], _m_ObjectType["m_ClassName"]
    )
    return ObjectInitializationDataJson(obj["m_Id"], m_ObjectType, obj["m_Data"])


def contentCatalogDataDecoder(obj: dict):
    _m_InstanceProviderData = obj["m_InstanceProviderData"]
    _m_SceneProviderData = obj["m_SceneProviderData"]
    _m_ResourceProviderData = obj["m_ResourceProviderData"]

    m_InstanceProviderData = ObjectInitializationDataJson(
        _m_InstanceProviderData["m_Id"],
        SerializedTypeJson(
            _m_InstanceProviderData["m_ObjectType"]["m_AssemblyName"],
            _m_InstanceProviderData["m_ObjectType"]["m_ClassName"],
        ),
        _m_InstanceProviderData["m_Data"],
    )

    m_SceneProviderData = ObjectInitializationDataJson(
        _m_SceneProviderData["m_Id"],
        SerializedTypeJson(
            _m_SceneProviderData["m_ObjectType"]["m_AssemblyName"],
            _m_SceneProviderData["m_ObjectType"]["m_ClassName"],
        ),
        _m_SceneProviderData["m_Data"],
    )

    m_ResourceProviderData = [
        ObjectInitializationDataJson(
            o["m_Id"],
            SerializedTypeJson(
                o["m_ObjectType"]["m_AssemblyName"], o["m_ObjectType"]["m_ClassName"]
            ),
            o["m_Data"],
        )
        for o in _m_ResourceProviderData
    ]

    return ContentCatalogDataJson(
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
            SerializedTypeJson(o["m_AssemblyName"], o["m_ClassName"])
            for o in obj["m_resourceTypes"]
        ],
        obj.get("m_InternalIdPrefixes"),
    )


class AddressablesCatalogFileParser:
    @staticmethod
    def FromBinaryData(data: bytes) -> ContentCatalogData:
        ms = BytesIO(data)
        reader = CatalogBinaryReader(ms)
        return ContentCatalogData.FromBinary(reader)

    @staticmethod
    def FromJsonString(data: str) -> ContentCatalogData:
        data = json.loads(data)
        ccdJson = contentCatalogDataDecoder(data)
        return ContentCatalogData.FromJson(ccdJson)


__all__ = ["AddressablesCatalogFileParser"]

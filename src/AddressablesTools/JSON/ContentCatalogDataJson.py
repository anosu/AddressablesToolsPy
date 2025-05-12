from dataclasses import dataclass

from .SerializedTypeJson import SerializedTypeJson
from .ObjectInitializationDataJson import ObjectInitializationDataJson


@dataclass
class ContentCatalogDataJson:
    m_LocatorId: str | None
    m_BuildResultHash: str | None
    m_InstanceProviderData: ObjectInitializationDataJson
    m_SceneProviderData: ObjectInitializationDataJson
    m_ResourceProviderData: list[ObjectInitializationDataJson]
    m_ProviderIds: list[str]
    m_InternalIds: list[str]
    m_KeyDataString: str
    m_BucketDataString: str
    m_EntryDataString: str
    m_ExtraDataString: str
    m_Keys: list[str] | None
    m_resourceTypes: list[SerializedTypeJson]
    m_InternalIdPrefixes: list[str]

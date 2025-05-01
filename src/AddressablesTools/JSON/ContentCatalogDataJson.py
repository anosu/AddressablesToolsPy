from dataclasses import dataclass

from .SerializedTypeJson import SerializedTypeJson
from .ObjectInitializationDataJson import ObjectInitializationDataJson


@dataclass
class ContentCatalogDataJson:
    m_LocatorId: str | None
    m_BuildResultHash: str | None
    m_InstanceProviderData: ObjectInitializationDataJson | None
    m_SceneProviderData: ObjectInitializationDataJson | None
    m_ResourceProviderData: list[ObjectInitializationDataJson] | None
    m_ProviderIds: list[str] | None
    m_InternalIds: list[str] | None
    m_KeyDataString: str | None
    m_BucketDataString: str | None
    m_EntryDataString: str | None
    m_ExtraDataString: str | None
    m_Keys: list[str] | None
    m_resourceTypes: list[SerializedTypeJson] | None
    m_InternalIdPrefixes: list[str] | None

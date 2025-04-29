from .SerializedTypeJson import SerializedTypeJson
from .ObjectInitializationDataJson import ObjectInitializationDataJson


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

    def __init__(self):
        self.m_LocatorId = None
        self.m_BuildResultHash = None
        self.m_InstanceProviderData = None
        self.m_SceneProviderData = None
        self.m_ResourceProviderData = None
        self.m_ProviderIds = None
        self.m_InternalIds = None
        self.m_KeyDataString = None
        self.m_BucketDataString = None
        self.m_EntryDataString = None
        self.m_ExtraDataString = None
        self.m_Keys = None
        self.m_resourceTypes = None
        self.m_InternalIdPrefixes = None

    @staticmethod
    def New(
        m_LocatorId: str,
        m_BuildResultHash: str,
        m_InstanceProviderData: ObjectInitializationDataJson,
        m_SceneProviderData: ObjectInitializationDataJson,
        m_ResourceProviderData: list[ObjectInitializationDataJson],
        m_ProviderIds: list[str],
        m_InternalIds: list[str],
        m_KeyDataString: str,
        m_BucketDataString: str,
        m_EntryDataString: str,
        m_ExtraDataString: str,
        m_Keys: list[str],
        m_resourceTypes: list[SerializedTypeJson],
        m_InternalIdPrefixes: list[str],
    ):
        o = ContentCatalogDataJson()
        o.m_LocatorId = m_LocatorId
        o.m_BuildResultHash = m_BuildResultHash
        o.m_InstanceProviderData = m_InstanceProviderData
        o.m_SceneProviderData = m_SceneProviderData
        o.m_ResourceProviderData = m_ResourceProviderData
        o.m_ProviderIds = m_ProviderIds
        o.m_InternalIds = m_InternalIds
        o.m_KeyDataString = m_KeyDataString
        o.m_BucketDataString = m_BucketDataString
        o.m_EntryDataString = m_EntryDataString
        o.m_ExtraDataString = m_ExtraDataString
        o.m_Keys = m_Keys
        o.m_resourceTypes = m_resourceTypes
        o.m_InternalIdPrefixes = m_InternalIdPrefixes
        return o

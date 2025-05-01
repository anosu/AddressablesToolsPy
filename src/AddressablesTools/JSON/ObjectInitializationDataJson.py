from dataclasses import dataclass

from .SerializedTypeJson import SerializedTypeJson


@dataclass
class ObjectInitializationDataJson:
    m_Id: str | None
    m_ObjectType: SerializedTypeJson | None
    m_Data: str | None

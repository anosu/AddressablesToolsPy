from .SerializedTypeJson import SerializedTypeJson


class ObjectInitializationDataJson:
    m_Id: str | None
    m_ObjectType: SerializedTypeJson | None
    m_Data: str | None

    def __init__(self):
        self.m_Id = None
        self.m_ObjectType = None
        self.m_Data = None

    @staticmethod
    def New(m_Id: str, m_ObjectType: SerializedTypeJson, m_Data: str):
        o = ObjectInitializationDataJson()
        o.m_Id = m_Id
        o.m_ObjectType = m_ObjectType
        o.m_Data = m_Data
        return o

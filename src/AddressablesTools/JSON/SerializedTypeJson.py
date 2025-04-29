class SerializedTypeJson:
    m_AssemblyName: str | None
    m_ClassName: str | None

    def __init__(self):
        self.m_AssemblyName = None
        self.m_ClassName = None

    @staticmethod
    def New(m_AssemblyName: str, m_ClassName: str):
        o = SerializedTypeJson()
        o.m_AssemblyName = m_AssemblyName
        o.m_ClassName = m_ClassName
        return o

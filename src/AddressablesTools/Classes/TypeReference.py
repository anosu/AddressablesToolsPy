class TypeReference:
    __slots__ = ["Clsid"]

    Clsid: str

    def __repr__(self):
        return f"{self.__class__.__name__}(Clsid={self.Clsid})"

    def __init__(self, clsid: str):
        self.Clsid = clsid


__all__ = ["TypeReference"]

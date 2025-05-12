from .SerializedType import SerializedType


class ClassJsonObject:
    __slots__ = ("Type", "JsonText")

    Type: SerializedType
    JsonText: str

    def __repr__(self):
        return f"{self.__class__.__name__}(Type={self.Type})"

    def __init__(self, assemblyName: str, className: str, jsonText: str):
        self.Type = SerializedType(assemblyName, className)
        self.JsonText = jsonText


__all__ = ["ClassJsonObject"]

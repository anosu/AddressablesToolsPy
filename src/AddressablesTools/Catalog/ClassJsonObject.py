from .SerializedType import SerializedType


class ClassJsonObject:
    Type: SerializedType
    JsonText: str | None

    def __repr__(self):
        return f"<{self.__class__.__name__}(Type={self.Type})>"

    def __init__(self, assemblyName: str, className: str, jsonText: str):
        self.Type = SerializedType()
        self.Type.AssemblyName = assemblyName
        self.Type.ClassName = className
        self.JsonText = className


__all__ = ["ClassJsonObject"]

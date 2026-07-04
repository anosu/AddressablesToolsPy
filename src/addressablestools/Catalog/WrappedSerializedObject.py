from typing import Generic, TypeVar

from .SerializedType import SerializedType

T = TypeVar("T")


class WrappedSerializedObject(Generic[T]):
    __slots__ = ("Type", "Object")

    Type: SerializedType
    Object: T

    def __repr__(self):
        return f"{self.__class__.__name__}[{self.Object.__class__.__name__}](Type={self.Type}, Object={self.Object})"

    def __init__(self, type: SerializedType, obj: T):
        self.Type = type
        self.Object = obj


__all__ = ["WrappedSerializedObject"]

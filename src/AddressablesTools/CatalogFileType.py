from enum import Enum


class CatalogFileType(Enum):
    Null = 0
    Json = 1
    Binary = 2


__all__ = ["CatalogFileType"]

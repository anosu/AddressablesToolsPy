__version__ = "0.1.0"

from .classes import ContentCatalogData
from .AddressablesCatalogFileParser import AddressablesCatalogFileParser as Parser


def parse(data: str | bytes) -> ContentCatalogData:
    return (
        Parser.FromJsonString(data)
        if isinstance(data, str)
        else Parser.FromBinaryData(data)
    )


def parse_json(data: str) -> ContentCatalogData:
    return Parser.FromJsonString(data)


def parse_binary(data: bytes) -> ContentCatalogData:
    return Parser.FromBinaryData(data)


__all__ = ["classes", "parse", "parse_json", "parse_binary", "Parser"]

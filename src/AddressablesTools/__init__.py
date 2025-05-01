__version__ = "0.1.1"

from .parser import AddressablesCatalogFileParser as Parser


def parse(data: str | bytes):
    return (
        Parser.FromJsonString(data)
        if isinstance(data, str)
        else Parser.FromBinaryData(data)
    )


def parse_json(data: str):
    return Parser.FromJsonString(data)


def parse_binary(data: bytes):
    return Parser.FromBinaryData(data)


__all__ = ["classes", "parse", "parse_json", "parse_binary", "Parser"]

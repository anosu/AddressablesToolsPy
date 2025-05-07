__version__ = "0.1.3"
__doc__ = "A Python library for parsing Unity Addressables catalog files."

from .parser import AddressablesCatalogFileParser as Parser, Patcher, Handler


def parse(
    data: str | bytes, patcher: Patcher | None = None, handler: Handler | None = None
):
    return (
        Parser.FromJsonString(data)
        if isinstance(data, str)
        else Parser.FromBinaryData(data, patcher, handler)
    )


def parse_json(data: str):
    return Parser.FromJsonString(data)


def parse_binary(
    data: bytes, patcher: Patcher | None = None, handler: Handler | None = None
):
    return Parser.FromBinaryData(data, patcher, handler)


__all__ = ["classes", "parse", "parse_json", "parse_binary", "Parser"]

__version__ = "0.1.7"
__doc__ = "A Python library for parsing Unity Addressables catalog files."

from .parser import AddressablesCatalogFileParser as Parser, Patcher, Handler


def parse(
    data: str | bytes, patcher: Patcher | None = None, handler: Handler | None = None
):
    return (
        Parser.from_json(data)
        if isinstance(data, str)
        else Parser.from_binary(data, patcher, handler)
    )


def parse_json(data: str):
    return Parser.from_json(data)


def parse_binary(
    data: bytes, patcher: Patcher | None = None, handler: Handler | None = None
):
    return Parser.from_binary(data, patcher, handler)


__all__ = ["classes", "parse", "parse_json", "parse_binary", "Parser"]

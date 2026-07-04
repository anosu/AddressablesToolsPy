from addressablestools.models import ContentCatalogData
from addressablestools.parser import Handler, Patcher


def parse_json_catalog(data: str) -> ContentCatalogData:
    return ContentCatalogData(resources={"json": []})


def parse_binary_catalog(
    data: bytes,
    patcher: Patcher | None = None,
    handler: Handler | None = None,
) -> ContentCatalogData:
    return ContentCatalogData(resources={"binary": []})

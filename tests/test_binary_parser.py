from addressablestools import parse_binary
from addressablestools.models import ContentCatalogData


def test_parse_binary_returns_pythonic_catalog(catalog_binary_bytes: bytes) -> None:
    catalog = parse_binary(catalog_binary_bytes)

    assert isinstance(catalog, ContentCatalogData)
    assert catalog.version in {1, 2}
    assert catalog.resources


def test_parse_binary_decodes_resource_location(catalog_binary_bytes: bytes) -> None:
    catalog = parse_binary(catalog_binary_bytes)
    location = catalog.resources["Anim/Network"][0]

    assert location.primary_key == "Anim/Network"
    assert location.internal_id == "Anim/Network"
    assert location.provider_id == "UnityEngine.ResourceManagement.ResourceProviders.LegacyResourcesProvider"
    assert location.type is not None
    assert location.type.class_name == "UnityEngine.AnimationClip"
    assert location.data is None
    assert location.dependencies == []


def test_parse_binary_accepts_custom_patcher_and_handler(catalog_binary_bytes: bytes) -> None:
    calls: list[str] = []

    def patcher(match_name: str) -> str | None:
        calls.append(match_name)
        return match_name

    catalog = parse_binary(catalog_binary_bytes, patcher=patcher)

    assert catalog.resources
    assert calls

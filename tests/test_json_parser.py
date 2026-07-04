from addressablestools import parse_json
from addressablestools.models import (
    AssetBundleRequestOptions,
    ContentCatalogData,
    WrappedSerializedObject,
)


def first_bundle(
    catalog: ContentCatalogData,
) -> tuple[str, WrappedSerializedObject[AssetBundleRequestOptions]]:
    for key, locations in catalog.resources.items():
        if isinstance(key, str) and key.endswith(".bundle"):
            data = locations[0].data
            assert isinstance(data, WrappedSerializedObject)
            assert isinstance(data.object, AssetBundleRequestOptions)
            return key, data
    raise AssertionError("sample catalog must contain at least one bundle")


def test_parse_json_returns_pythonic_catalog(catalog_json_text: str) -> None:
    catalog = parse_json(catalog_json_text)

    assert isinstance(catalog, ContentCatalogData)
    assert catalog.locator_id
    assert catalog.provider_ids
    assert catalog.internal_ids
    assert catalog.resource_types
    assert catalog.resources


def test_parse_json_decodes_bundle_request_options(catalog_json_text: str) -> None:
    key, wrapped = first_bundle(parse_json(catalog_json_text))

    assert key.endswith(".bundle")
    assert wrapped.object.crc > 0
    assert wrapped.object.hash
    assert wrapped.object.bundle_name
    assert wrapped.object.bundle_size > 0


def test_parse_json_expands_internal_id_prefixes(catalog_json_text: str) -> None:
    catalog = parse_json(catalog_json_text)
    key, _wrapped = first_bundle(catalog)
    location = catalog.resources[key][0]

    assert location.internal_id is not None
    assert "#" not in location.internal_id[:3]
    assert location.provider_id is not None
    assert location.primary_key is not None

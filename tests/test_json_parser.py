import json

import pytest

from addressablestools import parse_json
from addressablestools.catalog import _apply_internal_id_prefix
from addressablestools.exceptions import CatalogParseError
from addressablestools.models import (
    AssetBundleRequestOptions,
    ContentCatalogData,
)


def first_bundle(
    catalog: ContentCatalogData,
) -> tuple[str, AssetBundleRequestOptions]:
    for key, locations in catalog.resources.items():
        if isinstance(key, str) and key.endswith(".bundle"):
            data = locations[0].data
            assert isinstance(data, AssetBundleRequestOptions)
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
    assert wrapped.crc > 0
    assert wrapped.hash
    assert wrapped.bundle_name
    assert wrapped.bundle_size > 0


def test_parse_json_expands_internal_id_prefixes(catalog_json_text: str) -> None:
    catalog = parse_json(catalog_json_text)
    key, _wrapped = first_bundle(catalog)
    location = catalog.resources[key][0]

    assert location.internal_id is not None
    assert "#" not in location.internal_id[:3]
    assert location.provider_id is not None
    assert location.primary_key is not None


def test_parse_json_wraps_missing_fields_in_catalog_parse_error() -> None:
    with pytest.raises(CatalogParseError, match="m_InstanceProviderData"):
        parse_json("{}")


def test_parse_json_reports_out_of_range_catalog_indexes(catalog_json_text: str) -> None:
    raw = json.loads(catalog_json_text)
    raw["m_InternalIds"] = []

    with pytest.raises(CatalogParseError, match="internal ID index"):
        parse_json(json.dumps(raw))


def test_internal_id_prefix_does_not_accept_negative_index() -> None:
    assert _apply_internal_id_prefix("-1#/bundle", ["first", "last"]) == "-1#/bundle"


def test_resource_location_exposes_typed_data_extension(catalog_json_text: str) -> None:
    catalog = parse_json(catalog_json_text)
    key, options = first_bundle(catalog)
    location = catalog.resources[key][0]

    assert location.data_is(AssetBundleRequestOptions)
    assert location.data_as(AssetBundleRequestOptions) is options
    assert location._data_type is not None
    assert not hasattr(location, "data_type")
    with pytest.raises(TypeError, match="expected str"):
        location.data_as(str)


def test_catalog_exposes_query_extensions(catalog_json_text: str) -> None:
    catalog = parse_json(catalog_json_text)
    key, _options = first_bundle(catalog)

    assert catalog.locate(key) == tuple(catalog.resources[key])
    assert catalog.locate(object()) == ()

    locations = list(catalog.iter_locations())
    assert len(locations) == len({id(location) for location in locations})
    assert {id(location) for location in locations} == {
        id(location)
        for keyed_locations in catalog.resources.values()
        for location in keyed_locations
    }

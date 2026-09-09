from base64 import b64encode
import json
import struct
from functools import partial

import pytest

from addressablestools import available_backends, parse_json
from addressablestools.catalog import _apply_internal_id_prefix
from addressablestools.exceptions import CatalogParseError
from addressablestools.models import (
    AssetBundleRequestOptions,
    ClassJsonObject,
    ContentCatalogData,
)


@pytest.fixture(autouse=True, params=available_backends("json"))
def json_backend(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(globals(), "parse_json", partial(parse_json, backend=request.param))


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


def _b64(data: bytes) -> str:
    return b64encode(data).decode("ascii")


def _minimal_json_catalog() -> dict[str, object]:
    resource_type = {"m_AssemblyName": "Example", "m_ClassName": "Example.Asset"}
    init = {"m_Id": "provider", "m_ObjectType": resource_type, "m_Data": ""}
    return {
        "m_InstanceProviderData": init, "m_SceneProviderData": init,
        "m_ResourceProviderData": [], "m_ProviderIds": ["provider"],
        "m_InternalIds": ["asset"], "m_resourceTypes": [resource_type],
        "m_InternalIdPrefixes": [], "m_BucketDataString": _b64(struct.pack("<4i", 1, 4, 1, 0)),
        "m_KeyDataString": _b64(struct.pack("<iBi5s", 1, 0, 5, b"asset")),
        "m_EntryDataString": _b64(struct.pack("<8i", 1, 0, 0, -1, 7, -1, 0, 0)),
        "m_ExtraDataString": "",
    }


@pytest.mark.parametrize(
    ("field", "name"), [(0, "internal ID"), (1, "provider ID"), (5, "primary key"), (6, "resource type")],
)
@pytest.mark.parametrize("invalid", [-1, 1, 2147483647])
def test_json_location_rejects_invalid_required_indexes(field: int, name: str, invalid: int) -> None:
    raw = _minimal_json_catalog()
    entry = [0, 0, -1, 7, -1, 0, 0]
    entry[field] = invalid
    raw["m_EntryDataString"] = _b64(struct.pack("<8i", 1, *entry))
    with pytest.raises(CatalogParseError, match=f"{name} index {invalid}"):
        parse_json(json.dumps(raw))


@pytest.mark.parametrize("dependency", [-100, -1, 0, 1])
def test_json_dependency_index_sentinels_and_bounds(dependency: int) -> None:
    raw = _minimal_json_catalog()
    raw["m_EntryDataString"] = _b64(struct.pack("<8i", 1, 0, 0, dependency, 7, -1, 0, 0))
    if dependency == 1:
        with pytest.raises(CatalogParseError, match="dependency key index 1"):
            parse_json(json.dumps(raw))
    else:
        location = parse_json(json.dumps(raw)).resources["asset"][0]
        assert location.dependency_key == (None if dependency < 0 else "asset")


@pytest.mark.parametrize("entries", [[-1], [1], [0, -1], [1, -1], []])
def test_json_bucket_entry_bounds_and_empty_buckets(entries: list[int]) -> None:
    raw = _minimal_json_catalog()
    raw["m_BucketDataString"] = _b64(struct.pack(f"<{3 + len(entries)}i", 1, 4, len(entries), *entries))
    if entries:
        invalid = next(entry for entry in entries if entry != 0)
        with pytest.raises(CatalogParseError, match=f"bucket resource location index {invalid}"):
            parse_json(json.dumps(raw))
    else:
        assert parse_json(json.dumps(raw)).resources == {"asset": []}


@pytest.mark.parametrize("keys", [None, [], ["display"]])
def test_json_primary_key_override(keys: list[str] | None) -> None:
    raw = _minimal_json_catalog()
    raw["m_Keys"] = keys
    if keys == []:
        with pytest.raises(CatalogParseError, match="primary key index"):
            parse_json(json.dumps(raw))
    else:
        location = parse_json(json.dumps(raw)).resources["asset"][0]
        assert location.primary_key == ("asset" if keys is None else "display")


@pytest.mark.parametrize("prefixes", [[], ["root/"]])
def test_json_internal_ids_preserve_literals_and_expand_valid_prefixes(prefixes: list[str]) -> None:
    raw = _minimal_json_catalog()
    ids = ["0#asset", "-1#asset", "2#asset", "text#asset"]
    raw["m_InternalIds"] = ids
    raw["m_InternalIdPrefixes"] = prefixes
    records = [struct.pack("<7i", index, 0, -1, 7, -1, 0, 0) for index in range(len(ids))]
    raw["m_EntryDataString"] = _b64(struct.pack("<i", len(ids)) + b"".join(records))
    raw["m_BucketDataString"] = _b64(struct.pack("<7i", 1, 4, 4, 0, 1, 2, 3))
    catalog = parse_json(json.dumps(raw))
    expected = ["root/asset", *ids[1:]] if prefixes else ids
    assert [location.internal_id for location in catalog.resources["asset"]] == expected
    assert catalog.internal_ids == ids


@pytest.mark.parametrize("builtin", [False, True])
def test_json_extra_data_preserves_exact_types_and_independent_values(builtin: bool) -> None:
    raw = _minimal_json_catalog()
    assembly = "Unity.ResourceManager, Version=1.2.3.4" if builtin else "Custom, Version=1.2.3.4"
    name = (
        "UnityEngine.ResourceManagement.ResourceProviders.AssetBundleRequestOptions"
        if builtin else "Custom.Metadata"
    )
    payload = json.dumps({"m_Crc": 123, "m_BundleName": "资源"}, ensure_ascii=False)
    encoded_payload = payload.encode("utf-16-le")
    extra = bytearray([7])
    for value in (assembly, name):
        encoded = value.encode("ascii")
        extra.extend(bytes([len(encoded)]) + encoded)
    extra.extend(struct.pack("<i", len(encoded_payload)) + encoded_payload)
    raw["m_ExtraDataString"] = _b64(bytes(extra))
    record = struct.pack("<7i", 0, 0, -1, 7, 0, 0, 0)
    raw["m_EntryDataString"] = _b64(struct.pack("<i", 2) + record * 2)
    raw["m_BucketDataString"] = _b64(struct.pack("<5i", 1, 4, 2, 0, 1))
    first, second = parse_json(json.dumps(raw)).resources["asset"]
    assert first.data == second.data
    assert first.data is not second.data
    assert first._data_type is not None
    assert first._data_type.assembly_name == assembly
    assert first._data_type.class_name == name
    if builtin:
        assert isinstance(first.data, AssetBundleRequestOptions)
        assert isinstance(second.data, AssetBundleRequestOptions)
        assert first.data.common_info is not second.data.common_info
        assert first.data.bundle_name == "资源"
        first.data.crc = 456
        assert second.data.crc == 123
    else:
        assert isinstance(first.data, ClassJsonObject)
        assert first.data.json_text == payload
        assert first.data.type is first._data_type

import AddressablesTools
import pytest
from addressablestools.models import ContentCatalogData as ModernCatalog, ResourceLocation
from addressablestools.models import (
    AssetBundleRequestOptions as ModernBundleOptions,
    CommonInfo,
    SerializedType,
)
from AddressablesTools.classes import (
    AssetBundleRequestOptions,
    CatalogBinaryReader,
    ContentCatalogData,
    WrappedSerializedObject,
)


def test_legacy_parse_json_returns_pascal_case_catalog(catalog_json_text: str) -> None:
    with pytest.deprecated_call(match="AddressablesTools.parse_json is deprecated"):
        catalog = AddressablesTools.parse_json(catalog_json_text)

    assert isinstance(catalog, ContentCatalogData)
    assert catalog.Resources
    assert catalog.ProviderIds
    assert catalog.InternalIds


def test_legacy_parse_json_returns_pascal_case_bundle_data(catalog_json_text: str) -> None:
    with pytest.deprecated_call(match="AddressablesTools.parse_json is deprecated"):
        catalog = AddressablesTools.parse_json(catalog_json_text)

    for key, locations in catalog.Resources.items():
        if isinstance(key, str) and key.endswith(".bundle"):
            location = locations[0]
            assert location.InternalId
            assert location.ProviderId
            assert isinstance(location.Data, WrappedSerializedObject)
            assert location.Data.Type.ClassName.endswith("AssetBundleRequestOptions")
            assert isinstance(location.Data.Object, AssetBundleRequestOptions)
            assert location.Data.Object.Crc > 0
            assert location.Data.Object.Hash
            return
    raise AssertionError("sample catalog must contain at least one bundle")


def test_legacy_parse_binary_returns_pascal_case_catalog(catalog_binary_bytes: bytes) -> None:
    with pytest.deprecated_call(match="AddressablesTools.parse_binary is deprecated"):
        catalog = AddressablesTools.parse_binary(catalog_binary_bytes)

    assert isinstance(catalog, ContentCatalogData)
    assert catalog.Resources["Anim/Network"][0].PrimaryKey == "Anim/Network"


def test_legacy_parse_binary_keeps_patcher_callback(catalog_binary_bytes: bytes) -> None:
    calls: list[str] = []

    def patcher(match_name: str) -> str:
        calls.append(match_name)
        return match_name

    with pytest.deprecated_call(match="AddressablesTools.parse_binary is deprecated"):
        catalog = AddressablesTools.parse_binary(catalog_binary_bytes, patcher=patcher)

    assert catalog.Resources
    assert calls


def test_legacy_parse_dispatches_to_new_parser(
    catalog_json_text: str,
    catalog_binary_bytes: bytes,
) -> None:
    with pytest.deprecated_call(match="AddressablesTools.parse is deprecated"):
        assert AddressablesTools.parse(catalog_json_text).Resources
    with pytest.deprecated_call(match="AddressablesTools.parse is deprecated"):
        assert AddressablesTools.parse(catalog_binary_bytes).Resources


def test_legacy_classes_exports_catalog_binary_reader() -> None:
    assert CatalogBinaryReader.__name__ == "CatalogBinaryReader"


def test_legacy_version_matches_new_package() -> None:
    assert AddressablesTools.__version__ == "1.1.1"


@pytest.mark.parametrize("format", ["binary", "json"])
@pytest.mark.parametrize("backend", ["python", "auto"])
def test_legacy_resource_loop_wraps_catalog_only_once(
    format: str,
    backend: str,
    catalog_binary_bytes: bytes,
    catalog_json_text: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.deprecated_call():
        if format == "binary":
            catalog = AddressablesTools.parse_binary(catalog_binary_bytes, backend=backend)
        else:
            catalog = AddressablesTools.parse_json(catalog_json_text, backend=backend)

    original = AddressablesTools.wrap_legacy
    calls = 0

    def counted(value: object) -> object:
        nonlocal calls
        calls += 1
        return original(value)

    monkeypatch.setattr(AddressablesTools, "wrap_legacy", counted)
    resources = catalog.Resources
    first_access_calls = calls
    assert first_access_calls > 0
    # Reproduce issue #1: repeatedly access the property inside the resource loop.
    keys = list(resources)[:4]
    actual = [catalog.Resources[key][0].InternalId for key in keys]
    assert actual == [resources[key][0].InternalId for key in keys]
    assert calls == first_access_calls
    assert catalog.Resources is resources


def test_legacy_resources_cache_is_lazy_and_per_catalog() -> None:
    source = ModernCatalog()
    first = AddressablesTools.CompatCatalog(source)
    second = AddressablesTools.CompatCatalog(source)
    source.resources["asset"] = [ResourceLocation(internal_id="asset.bundle")]

    assert first.Resources["asset"][0].InternalId == "asset.bundle"
    assert first.Resources is not second.Resources
    assert first.Resources["asset"] is not second.Resources["asset"]
    empty = AddressablesTools.CompatCatalog(ModernCatalog())
    assert empty.Resources == {}
    assert empty.Resources is empty.Resources


def test_legacy_resources_remain_mutable_dict_and_can_be_refreshed() -> None:
    location = ResourceLocation(internal_id="old.bundle")
    source = ModernCatalog(resources={"asset": [location], "empty": []})
    catalog = AddressablesTools.CompatCatalog(source)
    resources = catalog.Resources
    assert type(resources) is dict
    assert type(resources["asset"]) is list
    assert resources["empty"] == []
    assert resources.copy() == resources

    # Wrapped objects still read current fields from the underlying location.
    location.internal_id = "new.bundle"
    assert catalog.Resources["asset"][0].InternalId == "new.bundle"
    resources["alias"] = resources["asset"]
    resources["asset"].append(resources["asset"][0])
    del resources["empty"]
    assert "alias" in catalog.Resources
    assert len(catalog.Resources["asset"]) == 2
    assert "empty" not in catalog.Resources
    assert "alias" not in source.resources
    assert len(source.resources["asset"]) == 1

    source.resources = {"replacement": [location]}
    del catalog.Resources
    refreshed = catalog.Resources
    assert refreshed is not resources
    assert list(refreshed) == ["replacement"]
    assert refreshed["replacement"][0].InternalId == "new.bundle"
    assert catalog.Resources is refreshed


def test_legacy_resources_share_wrappers_for_aliases_only() -> None:
    location = ResourceLocation(internal_id="asset.bundle")
    equal_location = ResourceLocation(internal_id="asset.bundle")
    source = ModernCatalog(resources={
        "asset": [location], "alias": [location, location], "equal": [equal_location],
    })
    catalog = AddressablesTools.CompatCatalog(source)
    resources = catalog.Resources
    assert resources["asset"][0] is resources["alias"][0]
    assert resources["alias"][0] is resources["alias"][1]
    assert resources["asset"][0] is not resources["equal"][0]
    resources["alias"].clear()
    assert len(resources["asset"]) == 1
    del catalog.Resources
    assert catalog.Resources["asset"][0] is not resources["asset"][0]


def test_legacy_dependency_loop_wraps_list_once(monkeypatch: pytest.MonkeyPatch) -> None:
    source = ResourceLocation(dependencies=[ResourceLocation(internal_id=str(i)) for i in range(8)])
    location = AddressablesTools.CompatResourceLocation(source)
    original = AddressablesTools.wrap_legacy
    calls = 0

    def counted(value: object) -> object:
        nonlocal calls
        calls += 1
        return original(value)

    monkeypatch.setattr(AddressablesTools, "wrap_legacy", counted)
    dependencies = location.Dependencies
    initial_calls = calls
    assert initial_calls > 0
    assert [location.Dependencies[i].InternalId for i in range(8)] == list(map(str, range(8)))
    assert calls == initial_calls
    assert location.Dependencies is dependencies


def test_legacy_dependencies_refresh_on_replacement_and_explicit_deletion() -> None:
    source = ResourceLocation()
    location = AddressablesTools.CompatResourceLocation(source)
    assert location.Dependencies is None
    source.dependencies = []
    empty = location.Dependencies
    assert empty == []
    assert location.Dependencies is empty
    dependency = ResourceLocation(internal_id="first")
    source.dependencies = [dependency]
    snapshot = location.Dependencies
    dependency.internal_id = "changed"
    assert snapshot[0].InternalId == "changed"
    snapshot.clear()
    assert location.Dependencies == []
    assert source.dependencies == [dependency]
    source.dependencies.append(source)  # Cycles must remain lazily wrapped.
    del location.Dependencies
    assert len(location.Dependencies) == 2
    assert location.Dependencies[1].Dependencies[0].InternalId == "changed"
    source.dependencies = None
    assert location.Dependencies is None


def test_legacy_metadata_chain_reuses_wrappers_and_tracks_replacements() -> None:
    type_ = SerializedType("Assembly", "Bundle")
    options = ModernBundleOptions(crc=7, common_info=CommonInfo(timeout=3))
    source = ResourceLocation(data=options, type=type_)
    source._data_type = type_
    location = AddressablesTools.CompatResourceLocation(source)
    data = location.Data
    obj = data.Object
    wrapped_type = data.Type
    common = obj.ComInfo
    assert location.Data is data
    assert location.Data.Object is obj
    assert location.Data.Type is wrapped_type
    assert obj.ComInfo is common
    assert location.Type is location.Type
    options.crc = 8
    options.common_info.timeout = 4
    assert location.Data.Object.Crc == 8
    assert location.Data.Object.ComInfo.Timeout == 4
    options.common_info = CommonInfo(timeout=5)
    assert obj.ComInfo is not common
    assert obj.ComInfo.Timeout == 5
    replacement_type = SerializedType("Assembly", "Replacement")
    source.type = replacement_type
    source._data_type = replacement_type
    assert location.Type.ClassName == "Replacement"
    assert location.Data is not data
    assert location.Data.Type.ClassName == "Replacement"
    assert data.Type.ClassName == "Bundle"
    source.data = ModernBundleOptions(crc=9)
    assert location.Data.Object.Crc == 9
    source._data_type = None
    assert isinstance(location.Data, AssetBundleRequestOptions)
    assert location.Data.Crc == 9
    source.data = None
    assert location.Data is None
    source.type = None
    assert location.Type is None


def test_legacy_custom_container_data_stays_live() -> None:
    values = [ModernBundleOptions(crc=1)]
    source = ResourceLocation(data=values)
    location = AddressablesTools.CompatResourceLocation(source)
    before = location.Data
    values.append(ModernBundleOptions(crc=2))
    assert [obj.Crc for obj in location.Data] == [1, 2]
    assert len(before) == 1
    source.data = {"values": values}
    assert location.Data["values"][1].Crc == 2
    source.data["extra"] = 3
    assert location.Data["extra"] == 3
    wrapped = AddressablesTools.CompatWrappedSerializedObject(SerializedType("A", "T"), values)
    assert len(wrapped.Object) == 2
    values.clear()
    assert wrapped.Object == []

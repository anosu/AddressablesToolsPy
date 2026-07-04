import AddressablesTools
from AddressablesTools.classes import (
    AssetBundleRequestOptions,
    CatalogBinaryReader,
    ContentCatalogData,
)


def test_legacy_parse_json_returns_pascal_case_catalog(catalog_json_text: str) -> None:
    catalog = AddressablesTools.parse_json(catalog_json_text)

    assert isinstance(catalog, ContentCatalogData)
    assert catalog.Resources
    assert catalog.ProviderIds
    assert catalog.InternalIds


def test_legacy_parse_json_returns_pascal_case_bundle_data(catalog_json_text: str) -> None:
    catalog = AddressablesTools.parse_json(catalog_json_text)

    for key, locations in catalog.Resources.items():
        if isinstance(key, str) and key.endswith(".bundle"):
            location = locations[0]
            assert location.InternalId
            assert location.ProviderId
            assert isinstance(location.Data.Object, AssetBundleRequestOptions)
            assert location.Data.Object.Crc > 0
            assert location.Data.Object.Hash
            return
    raise AssertionError("sample catalog must contain at least one bundle")


def test_legacy_parse_binary_returns_pascal_case_catalog(catalog_binary_bytes: bytes) -> None:
    catalog = AddressablesTools.parse_binary(catalog_binary_bytes)

    assert isinstance(catalog, ContentCatalogData)
    assert catalog.Resources["Anim/Network"][0].PrimaryKey == "Anim/Network"


def test_legacy_parse_dispatches_to_new_parser(
    catalog_json_text: str,
    catalog_binary_bytes: bytes,
) -> None:
    assert AddressablesTools.parse(catalog_json_text).Resources
    assert AddressablesTools.parse(catalog_binary_bytes).Resources


def test_legacy_classes_exports_catalog_binary_reader() -> None:
    assert CatalogBinaryReader.__name__ == "CatalogBinaryReader"

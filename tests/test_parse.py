from pathlib import Path

import AddressablesTools
from AddressablesTools.classes import ContentCatalogData, AssetBundleRequestOptions


json_file = Path("tests/samples/catalog.json")
binary_file = Path("tests/samples/catalog.bin")


def test_parse():
    catalog = AddressablesTools.parse(json_file.read_text("utf-8"))
    assert isinstance(catalog, ContentCatalogData)
    for key, locs in catalog.Resources.items():
        if not isinstance(key, str):
            continue
        if key.endswith(".bundle"):
            loc = locs[0]
            print(key)
            assert isinstance(loc.Data.Object, AssetBundleRequestOptions)


def test_parse_binary():
    catalog = AddressablesTools.parse_binary(binary_file.read_bytes())
    for key, locs in catalog.Resources.items():
        if not isinstance(key, str):
            continue
        if key.endswith(".bundle"):
            loc = locs[0]
            print(key)
            assert isinstance(loc.Data.Object, AssetBundleRequestOptions)


def test_parse_json():
    catalog = AddressablesTools.parse_json(json_file.read_text("utf-8"))
    for key, locs in catalog.Resources.items():
        if not isinstance(key, str):
            continue
        if key.endswith(".bundle"):
            loc = locs[0]
            print(key)
            assert isinstance(loc.Data.Object, AssetBundleRequestOptions)

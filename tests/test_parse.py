import time
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


def test_parse_json_speed():
    data = json_file.read_text("utf-8")
    start = time.time()
    for i in range(10):
        AddressablesTools.parse_json(data)
    total = time.time() - start
    assert total < 0.5


def test_parse_binary_speed():
    data = binary_file.read_bytes()
    start = time.time()
    for i in range(10):
        AddressablesTools.parse_binary(data)
    total = time.time() - start
    assert total < 0.04

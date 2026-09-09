from base64 import b64decode
import json
import random
import struct

import pytest

from addressablestools import available_backends, parse_json
from addressablestools.exceptions import CatalogParseError
from tests.test_json_parser import _b64, _minimal_json_catalog

pytestmark = pytest.mark.skipif("rust" not in available_backends("json"), reason="requires Rust JSON")


def compare(raw: dict[str, object]) -> None:
    data = json.dumps(raw)
    results = []
    for backend in ("python", "rust"):
        try:
            results.append(parse_json(data, backend=backend))
        except CatalogParseError as exc:
            results.append(type(exc))
    assert results[0] == results[1]
    if not isinstance(results[0], type):
        for key, locations in results[0].resources.items():
            for left, right in zip(locations, results[1].resources[key]):
                assert left._data_type == right._data_type


@pytest.mark.parametrize("prefix", ["base/", "资源/🎮/", "\ud800/"])
@pytest.mark.parametrize("identifier", [
    "asset", "0#asset", "00#asset", "0#", "0#资源/🎮", "0#\ud800", "0#a#b",
    "1#outside", "9999999999999999999#outside", "0" * 50 + "#asset",
    "9" * 5000 + "#asset", "-1#asset", "-0#asset", "+0#asset", " 0 #asset",
    "٠#asset", "０#asset", "0_0#asset", "#asset", "x#asset",
])
def test_prefix_fast_path_preserves_python_integer_and_unicode_semantics(prefix, identifier):
    raw = _minimal_json_catalog()
    raw["m_InternalIdPrefixes"] = [prefix]
    raw["m_InternalIds"] = [identifier]
    compare(raw)


def test_ordinary_prefixes_do_not_call_python_helper(monkeypatch):
    from addressablestools import catalog

    native = pytest.importorskip("addressablestools._rust")
    if not hasattr(native, "decode_resources_with_registry_fast"):
        pytest.skip("requires native 0.3.1")
    monkeypatch.setattr(catalog, "_apply_internal_id_prefix", lambda *args: pytest.fail("Python prefix"))
    for identifier, expected in [("0#asset", "base/asset"), ("plain", "plain"), ("2#asset", "2#asset")]:
        raw = _minimal_json_catalog()
        raw["m_InternalIdPrefixes"] = ["base/"]
        raw["m_InternalIds"] = [identifier]
        result = parse_json(json.dumps(raw), backend="rust")
        assert result.resources["asset"][0].internal_id == expected


@pytest.mark.parametrize("decoration", ["whitespace", "punctuation", "padding", "nonzero_bits"])
def test_noncanonical_base64_matches_python(decoration: str) -> None:
    raw = _minimal_json_catalog()
    value = raw["m_KeyDataString"]
    if decoration == "whitespace":
        value = "\n \t" + value + "\n"
    elif decoration == "punctuation":
        value = "!!" + value + "??"
    elif decoration == "padding":
        value += "====ignored"
    else:
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
        value = value[:-2] + alphabet[alphabet.index(value[-2]) ^ 1] + value[-1]
    raw["m_KeyDataString"] = value
    compare(raw)


@pytest.mark.parametrize("field", ["m_InternalIds", "m_ProviderIds", "m_Keys", "m_InternalIdPrefixes"])
def test_json_strings_preserve_lone_surrogates(field: str) -> None:
    raw = _minimal_json_catalog()
    raw[field] = ["\ud800/value"]
    if field == "m_InternalIdPrefixes":
        raw["m_InternalIds"] = ["0#asset"]
    compare(raw)


@pytest.mark.parametrize("kind", range(8))
@pytest.mark.parametrize("extra", [False, True])
def test_serialized_key_and_extra_kinds(kind: int, extra: bool) -> None:
    raw = _minimal_json_catalog()
    payloads = [
        struct.pack("<i", 3) + b"key",
        struct.pack("<i", 4) + "资源".encode("utf-16-le"),
        struct.pack("<H", 65535), struct.pack("<I", 4294967295),
        struct.pack("<i", -123), b"\x04abcd", b"\x04type",
        b"\x06Custom\x08Metadata" + struct.pack("<i", 4) + "{}".encode("utf-16-le"),
    ]
    if extra:
        raw["m_ExtraDataString"] = _b64(bytes([kind]) + payloads[kind])
        raw["m_EntryDataString"] = _b64(struct.pack("<8i", 1, 0, 0, -1, 7, 0, 0, 0))
    else:
        raw["m_KeyDataString"] = _b64(struct.pack("<iB", 1, kind) + payloads[kind])
    compare(raw)


def test_mutated_tables_match_python_without_native_panics() -> None:
    rng = random.Random(2701)
    fields = ("m_BucketDataString", "m_KeyDataString", "m_EntryDataString")
    for _ in range(500):
        raw = _minimal_json_catalog()
        field = rng.choice(fields)
        data = bytearray(b64decode(raw[field]))
        if rng.randrange(4) == 0:
            del data[rng.randrange(len(data)):]
        else:
            data[rng.randrange(len(data))] ^= 1 << rng.randrange(8)
        raw[field] = _b64(bytes(data))
        compare(raw)


def test_mutated_extra_objects_match_python() -> None:
    rng = random.Random(2913)
    assembly = b"Unity.ResourceManager, Version=1.2.3.4"
    name = b"UnityEngine.ResourceManagement.ResourceProviders.AssetBundleRequestOptions"
    text = '{"m_Crc": 123, "m_BundleName": "资源"}'.encode("utf-16-le")
    original = bytes([7, len(assembly)]) + assembly + bytes([len(name)]) + name
    original += struct.pack("<i", len(text)) + text
    for _ in range(250):
        raw = _minimal_json_catalog()
        data = bytearray(original)
        if rng.randrange(4) == 0:
            del data[rng.randrange(len(data)):]
        else:
            data[rng.randrange(len(data))] ^= 1 << rng.randrange(8)
        raw["m_ExtraDataString"] = _b64(bytes(data))
        raw["m_EntryDataString"] = _b64(struct.pack("<8i", 1, 0, 0, -1, 7, 0, 0, 0))
        compare(raw)

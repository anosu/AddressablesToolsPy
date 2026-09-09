"""Differential tests run when the optional extension is installed."""

from __future__ import annotations

import struct

import pytest

from addressablestools import parse_binary
from addressablestools import catalog as catalog_module
from addressablestools.exceptions import BinaryReadError, UnsupportedSerializedObjectError
from addressablestools.models import ResourceLocation

native = pytest.importorskip("_addressablestools_rust")
NULL = 0xFFFFFFFF


class CatalogFixture:
    """Write small format fixtures with explicit offsets, including invalid variants."""

    def __init__(self, version: int = 2) -> None:
        self.data = bytearray(32)
        self.version = version
        self.resource_type = self.type("UnityEngine.CoreModule", "UnityEngine.Object")
        self.init = self.record("<3I", self.string("provider"), self.resource_type, NULL)
        self.provider = self.string("Example.Provider")

    def record(self, fmt: str, *values: object) -> int:
        offset = len(self.data)
        self.data.extend(struct.pack(fmt, *values))
        return offset

    def string(self, value: str, *, unicode: bool = False) -> int:
        raw = value.encode("utf-16-le" if unicode else "ascii")
        self.record("<i", len(raw))
        offset = len(self.data)
        self.data.extend(raw)
        return offset | (0x80000000 if unicode else 0)

    def array(self, values: list[int]) -> int:
        self.record("<i", len(values) * 4)
        return self.record(f"<{len(values)}I", *values)

    def type(self, assembly: str | None, name: str) -> int:
        assembly_offset = NULL if assembly is None else self.string(assembly)
        return self.record("<2I", assembly_offset, self.string(name))

    def object(self, assembly: str | None, name: str, payload: int = NULL) -> int:
        return self.record("<2I", self.type(assembly, name), payload)

    def location(self, data: int = NULL, dependencies: int = NULL) -> int:
        name = self.string("asset")
        return self.record(
            "<4Ii2I", name, name, self.provider, dependencies, -123, data, self.resource_type,
        )

    def finish(self, pairs: list[int]) -> bytes:
        keys = self.array(pairs)
        struct.pack_into(
            "<ii6I", self.data, 0, 0, self.version, keys, NULL, self.init, self.init, NULL, NULL,
        )
        return bytes(self.data)


def parse_both(data: bytes, monkeypatch: pytest.MonkeyPatch) -> tuple:
    with monkeypatch.context() as patch:
        patch.setattr(catalog_module, "_native_decode", None)
        expected = parse_binary(data)
    with monkeypatch.context() as patch:
        patch.setattr(catalog_module, "_native_decode", native.decode_resources)
        actual = parse_binary(data)
    assert actual == expected
    for key, locations in actual.resources.items():
        for location, other in zip(locations, expected.resources[key]):
            assert type(location) is ResourceLocation
            assert location._data_type == other._data_type
    return expected, actual


def test_native_matches_real_sample(catalog_binary_bytes: bytes, monkeypatch: pytest.MonkeyPatch) -> None:
    parse_both(catalog_binary_bytes, monkeypatch)


@pytest.mark.parametrize("part", [None, "", "ascii", "资源/🎮"])
def test_native_single_part_dynamic_string(part: str | None, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = CatalogFixture()
    offset = NULL if part is None else fixture.string(part, unicode=not part.isascii())
    dynamic = fixture.record("<2I", offset, NULL) | 0x40000000
    payload = fixture.record("<IB", dynamic, ord("/"))
    key = fixture.object("mscorlib", "System.String", payload)
    _, actual = parse_both(
        fixture.finish([key, fixture.array([fixture.location()])]), monkeypatch,
    )
    assert list(actual.resources) == [part or ""]


@pytest.mark.parametrize("version", [1, 2, 3])
@pytest.mark.parametrize(
    ("name", "fmt", "value"),
    [
        ("System.Int32", "<i", -2147483648),
        ("System.Int32", "<i", 2147483647),
        ("System.Int64", "<q", -9223372036854775808),
        ("System.Int64", "<q", 9223372036854775807),
        ("System.Boolean", "<B", 0),
        ("System.Boolean", "<B", 255),
        ("System.Int32", None, 0),
        ("System.Int64", None, 0),
        ("System.Boolean", None, False),
        ("System.String", None, None),
    ],
)
def test_native_primitive_values(
    version: int, name: str, fmt: str | None, value: object, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = CatalogFixture(version)
    payload = NULL if fmt is None else fixture.record(fmt, value)
    assembly = None if version == 3 else "mscorlib, Version=4.0.0.0"
    obj = fixture.object(assembly, name, payload)
    location = fixture.location(data=obj)
    expected, actual = parse_both(fixture.finish([obj, fixture.array([location])]), monkeypatch)
    decoded = bool(value) if name == "System.Boolean" else value
    assert list(actual.resources) == [decoded]
    assert type(next(iter(actual.resources))) is type(decoded)
    assert type(actual.resources[decoded][0].data) is type(decoded)
    assert actual.resources[decoded][0].data == expected.resources[decoded][0].data == decoded


@pytest.mark.parametrize("version", [1, 2, 3])
@pytest.mark.parametrize("separator", [0, ord("/"), 233])
def test_native_unicode_and_shared_dynamic_paths(
    version: int, separator: int, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = CatalogFixture(version)
    tail = fixture.record("<2I", fixture.string("资源/🎮", unicode=True), NULL)
    empty = fixture.record("<2I", fixture.string(""), tail)
    null_part = fixture.record("<2I", NULL, empty)
    paths = [
        fixture.record("<2I", fixture.string(prefix), null_part) | 0x40000000
        for prefix in ("first", "second")
    ] if separator else [fixture.string("资源/🎮", unicode=True), fixture.string("")]
    pairs = []
    shared = fixture.location()
    locations = fixture.array([shared])
    for path in paths:
        payload = fixture.record("<IB", path, separator)
        obj = fixture.object("mscorlib", "System.String", payload)
        pairs.extend((obj, locations))
    _, actual = parse_both(fixture.finish(pairs), monkeypatch)
    first, second = actual.resources.values()
    assert first is not second
    assert first[0] is second[0]
    assert first[0].type is actual.instance_provider_data.object_type


def test_native_bundle_metadata_sharing_and_hashes(monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = CatalogFixture()
    digest = fixture.record("<16s", bytes(range(16)))
    common = fixture.record("<hBBi", -7, 2, 3, 31)
    bundle = fixture.record("<5I", digest, fixture.string("bundle"), 0xFFFFFFFF, 123456, common)
    options = fixture.object(
        "Unity.ResourceManager",
        "UnityEngine.ResourceManagement.ResourceProviders.AssetBundleRequestOptions",
        bundle,
    )
    key = fixture.object("UnityEngine.CoreModule", "UnityEngine.Hash128", digest)
    dependency = fixture.location(options)
    location = fixture.location(options, fixture.array([dependency, dependency]))
    _, actual = parse_both(fixture.finish([key, fixture.array([location, dependency])]), monkeypatch)
    first, second = next(iter(actual.resources.values()))
    assert first.data is second.data
    assert first.data.hash == "000102030405060708090a0b0c0d0e0f"
    assert first.dependencies[0] is first.dependencies[1] is second


@pytest.mark.parametrize("kind", ["hash", "bundle"])
def test_native_default_metadata(kind: str, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = CatalogFixture()
    assembly, name = (
        ("UnityEngine.CoreModule", "UnityEngine.Hash128") if kind == "hash" else
        ("Unity.ResourceManager", "UnityEngine.ResourceManagement.ResourceProviders.AssetBundleRequestOptions")
    )
    obj = fixture.object(assembly, name)
    location = fixture.location(obj)
    parse_both(fixture.finish([obj, fixture.array([location])]), monkeypatch)


@pytest.mark.parametrize("problem", ["unsupported", "ascii", "utf16", "cycle"])
def test_native_rejects_invalid_objects_like_python(
    problem: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = CatalogFixture()
    if problem == "unsupported":
        obj = fixture.object("Custom", "Unsupported")
        exception = UnsupportedSerializedObjectError
    else:
        if problem == "cycle":
            offset = fixture.record("<2I", fixture.string("part"), 0)
            struct.pack_into("<I", fixture.data, offset + 4, offset)
            encoded = offset | 0x40000000
            exception = BinaryReadError
        else:
            fixture.record("<i", 1)
            offset = fixture.record("<B", 255)
            encoded = offset | (0x80000000 if problem == "utf16" else 0)
            exception = UnicodeDecodeError
        obj = fixture.object("mscorlib", "System.String", fixture.record("<IB", encoded, ord("/")))
    data = fixture.finish([obj, fixture.array([fixture.location()])])
    for decoder in (None, native.decode_resources):
        with monkeypatch.context() as patch:
            patch.setattr(catalog_module, "_native_decode", decoder)
            with pytest.raises(exception):
                parse_binary(data)


def test_native_handles_deep_dependencies_and_rejects_cycles() -> None:
    fixture = CatalogFixture()
    location = fixture.location()
    for _ in range(1500):
        location = fixture.location(dependencies=fixture.array([location]))
    key = fixture.object("mscorlib", "System.Int32")
    data = fixture.finish([key, fixture.array([location])])
    resources = native.decode_resources(data, 2, struct.unpack_from("<I", data, 8)[0], {})
    current = resources[0][0]
    depth = 0
    while current.dependencies:
        depth += 1
        current = current.dependencies[0]
    assert depth == 1500

    cycle = fixture.array([location])
    struct.pack_into("<I", fixture.data, location + 12, cycle)
    with pytest.raises(BinaryReadError, match="cycle"):
        native.decode_resources(bytes(fixture.data), 2, struct.unpack_from("<I", data, 8)[0], {})


@pytest.mark.parametrize("cut", [0, 8, 31, 32, 40, 100, 1000, -1])
def test_native_truncated_catalogs(
    cut: int, catalog_binary_bytes: bytes, monkeypatch: pytest.MonkeyPatch,
) -> None:
    for decoder in (None, native.decode_resources):
        with monkeypatch.context() as patch:
            patch.setattr(catalog_module, "_native_decode", decoder)
            with pytest.raises(BinaryReadError):
                parse_binary(catalog_binary_bytes[:cut])

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import runpy
from types import SimpleNamespace

import pytest

from addressablestools import (
    DecoderRegistry, NativeBackendUnavailableError, available_backends, parse, parse_binary, parse_json,
)


@pytest.mark.parametrize("parse_function", [parse, parse_binary])
def test_registry_requires_compatible_native_decoder(
    parse_function, catalog_binary_bytes: bytes, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("addressablestools.catalog._native_decode_registry", None)
    assert parse_function(catalog_binary_bytes, DecoderRegistry()).resources
    with pytest.raises(NativeBackendUnavailableError, match="Rust backend unavailable"):
        parse_function(catalog_binary_bytes, DecoderRegistry(), backend="rust")


@pytest.mark.parametrize("backend", ["unknown", "Rust", "", None])
def test_invalid_backend_is_reported(backend, catalog_json_text: str, catalog_binary_bytes: bytes) -> None:
    for data in (catalog_json_text, catalog_binary_bytes):
        with pytest.raises(ValueError, match="unknown backend"):
            parse(data, backend=backend)


@pytest.mark.parametrize("mode", ["missing", "load_failure", "bad_api", "api1", "api2", "api3", "api3_partial"])
def test_optional_extension_capabilities_and_fallback(mode: str, monkeypatch: pytest.MonkeyPatch) -> None:
    def load(_name: str):
        assert _name == "addressablestools._rust"
        if mode == "missing":
            raise ModuleNotFoundError("not installed")
        if mode == "load_failure":
            raise OSError("missing dependent library")
        return SimpleNamespace(
            API_VERSION={"bad_api": 99, "api1": 1, "api2": 2}.get(mode, 3),
            decode_resources=lambda *args: {}, decode_json_resources=lambda *args: {},
            decode_resources_with_registry=(lambda *args: {}) if mode == "api3" else None,
        )

    monkeypatch.setattr("importlib.import_module", load)
    module = runpy.run_path(str(Path(__file__).parents[1] / "src/addressablestools/_native.py"))
    assert module["available_backends"]("binary") == (
        ("python", "rust") if mode.startswith("api") else ("python",)
    )
    assert module["available_backends"]("json") == (
        ("python", "rust") if mode in ("api2", "api3", "api3_partial") else ("python",)
    )
    assert (module["decode_registry_resources"] is not None) == (mode == "api3")
    if mode not in ("api2", "api3", "api3_partial"):
        assert module["select_decoder"]("auto", module["decode_json_resources"]) is None
        with pytest.raises(NativeBackendUnavailableError, match="Rust backend unavailable"):
            module["select_decoder"]("rust", module["decode_json_resources"])


def test_backends_can_be_selected_concurrently(catalog_json_text: str, catalog_binary_bytes: bytes) -> None:
    if "rust" not in available_backends("json") or "rust" not in available_backends("binary"):
        pytest.skip("requires both native decoders")
    calls = [(catalog_json_text, "python"), (catalog_json_text, "rust"),
             (catalog_binary_bytes, "python"), (catalog_binary_bytes, "rust")]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda call: parse(call[0], backend=call[1]), calls))
    assert results[0] == results[1]
    assert results[2] == results[3]
    for first, second in ((results[0], results[1]), (results[2], results[3])):
        key = next(iter(first.resources))
        assert first.resources[key][0] is not second.resources[key][0]


def test_public_rust_selection_does_not_silently_fallback(
    catalog_json_text: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from addressablestools import catalog

    monkeypatch.setattr(catalog, "_native_decode_json", None)
    assert parse_json(catalog_json_text, backend="auto").resources
    with pytest.raises(NativeBackendUnavailableError):
        parse_json(catalog_json_text, backend="rust")


def test_mutable_binary_input_retains_python_behavior(catalog_binary_bytes: bytes) -> None:
    data = bytearray(catalog_binary_bytes)
    assert parse_binary(data) == parse_binary(catalog_binary_bytes, backend="python")
    with pytest.raises(NativeBackendUnavailableError, match="immutable bytes"):
        parse_binary(data, backend="rust")


@pytest.mark.parametrize("format", ["binary", "json"])
def test_legacy_default_calls_use_native_when_available(
    format: str, catalog_binary_bytes: bytes, catalog_json_text: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    if "rust" not in available_backends(format):
        pytest.skip("requires native decoder")
    import AddressablesTools as legacy
    from addressablestools import catalog

    name = "_native_decode" if format == "binary" else "_native_decode_json"
    decoder = getattr(catalog, name)
    calls = []

    def wrapped(*args):
        calls.append(True)
        return decoder(*args)

    monkeypatch.setattr(catalog, name, wrapped)
    data = catalog_binary_bytes if format == "binary" else catalog_json_text
    with pytest.warns(DeprecationWarning):
        result = legacy.parse(data)
    assert result.Resources
    assert calls == [True]


def test_falsey_legacy_patcher_is_preserved(catalog_binary_bytes: bytes, monkeypatch: pytest.MonkeyPatch) -> None:
    import AddressablesTools as legacy
    from addressablestools import catalog

    class Patcher:
        calls = 0

        def __bool__(self):
            return False

        def __call__(self, name):
            self.calls += 1
            return name

    def unexpected(*args):
        raise AssertionError("legacy callbacks must use the registry-aware decoder")

    monkeypatch.setattr(catalog, "_native_decode", unexpected)
    patcher = Patcher()
    with pytest.warns(DeprecationWarning):
        assert legacy.parse_binary(catalog_binary_bytes, patcher=patcher).Resources
    assert patcher.calls > 0

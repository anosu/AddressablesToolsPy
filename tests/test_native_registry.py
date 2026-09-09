"""Registry callbacks must behave identically during Python and native traversal."""

import pytest

from addressablestools import BinaryDecodeContext, DecoderRegistry, parse_binary
from addressablestools.binary import CatalogBinaryReader
from addressablestools.catalog import _resource_location_from_binary
from addressablestools.decoder import SerializedObjectDecoder
from addressablestools.exceptions import UnsupportedSerializedObjectError
from tests.test_native import CatalogFixture, NULL, native

pytestmark = pytest.mark.skipif(native.API_VERSION < 3, reason="requires native registry support")


@pytest.mark.parametrize("backend", ["python", "rust", "auto"])
@pytest.mark.parametrize("version", [1, 2, 3])
@pytest.mark.parametrize("default", [False, True])
def test_custom_keys_metadata_context_and_shared_locations(backend, version, default):
    fixture = CatalogFixture(version)
    payload = NULL if default else fixture.record("<i", 42)
    obj = fixture.object("Custom.Assembly", "Custom.Value", payload)
    location = fixture.location(obj)
    data = fixture.finish([obj, fixture.array([location, location])])
    registry = DecoderRegistry()
    contexts = []

    @registry.register("Custom.Assembly; Custom.Value")
    def decode(context: BinaryDecodeContext):
        contexts.append(context)
        assert type(context.reader) is CatalogBinaryReader
        assert context.reader.version == version
        assert context.offset == payload
        assert context.is_default is default
        assert context.serialized_type.class_name == "Custom.Value"
        if context.is_default:
            return -1
        context.reader.seek(context.offset)
        return context.reader.read_int32()

    result = parse_binary(data, registry, backend=backend)
    key = -1 if default else 42
    first, second = result.resources[key]
    assert first is second
    assert first.data == key
    assert len(contexts) == 2  # One key and one unique resource, no callback result memoization.
    assert contexts[0].reader is contexts[1].reader
    assert contexts[0].serialized_type is first._data_type
    assert contexts[1].serialized_type is first._data_type


@pytest.mark.parametrize("backend", ["python", "rust", "auto"])
@pytest.mark.parametrize("version", [1, 2, 3])
def test_alias_chains_and_builtin_override(backend, version):
    fixture = CatalogFixture(version)
    obj = fixture.object("Custom.Assembly", "Custom.Value", fixture.record("<i", 7))
    data = fixture.finish([obj, fixture.array([fixture.location(obj)])])
    registry = DecoderRegistry()
    builtin = "System.Int32" if version == 3 else "mscorlib; System.Int32"
    registry.alias("Custom.Assembly; Custom.Value", "Intermediate")
    registry.alias("Intermediate", builtin)
    assert parse_binary(data, registry, backend=backend).resources[7][0].data == 7
    registry.register(builtin, lambda context: 99)
    result = parse_binary(data, registry, backend=backend)
    assert result.resources[99][0].data == 99
    assert result.resources[99][0]._data_type.class_name == "Custom.Value"


@pytest.mark.parametrize("backend", ["python", "rust", "auto"])
def test_live_registry_mutation_and_nested_decode(backend):
    fixture = CatalogFixture()
    inner = fixture.object("mscorlib", "System.Int32", fixture.record("<i", 5))
    obj = fixture.object("Custom", "Value", inner)
    location = fixture.location(obj)
    data = fixture.finish([obj, fixture.array([location]), obj, fixture.array([location])])
    registry = DecoderRegistry()
    calls = []

    def later(context):
        calls.append("later")
        return SerializedObjectDecoder.decode_v2(context.reader, context.offset, registry) + 1

    @registry.register("Custom; Value")
    def first(context):
        calls.append("first")
        registry.alias("Custom; Value", "Replacement")
        registry.register("Replacement", later)
        return SerializedObjectDecoder.decode_v2(context.reader, context.offset, registry)

    result = parse_binary(data, registry, backend=backend)
    assert calls == ["first", "later", "later"]
    assert list(result.resources) == [5, 6]
    assert result.resources[5][0] is result.resources[6][0]
    assert result.resources[5][0].data == 6


@pytest.mark.parametrize("backend", ["python", "rust", "auto"])
def test_callback_and_traversal_share_reader_cache(backend):
    fixture = CatalogFixture()
    dependency = fixture.location()
    key = fixture.object("Custom", "Key")
    location = fixture.location(dependencies=fixture.array([dependency]))
    data = fixture.finish([key, fixture.array([location, dependency])])
    registry = DecoderRegistry()
    decoded = []

    @registry.register("Custom; Key")
    def decode(context):
        decoded.append(_resource_location_from_binary(context.reader, dependency, registry))
        return "key"

    result = parse_binary(data, registry, backend=backend)
    first, second = result.resources["key"]
    assert first.dependencies[0] is second is decoded[0]
    assert second.type is result.instance_provider_data.object_type


@pytest.mark.parametrize("backend", ["python", "rust", "auto"])
def test_callback_reads_native_cached_dependency_and_can_reenter(backend):
    fixture = CatalogFixture()
    dependency = fixture.location()
    obj = fixture.object("Custom", "Value", dependency)
    key = fixture.object("mscorlib", "System.Int32")
    data = fixture.finish([key, fixture.array([
        fixture.location(obj, fixture.array([dependency])), dependency,
    ])])
    registry = DecoderRegistry()
    calls = []

    @registry.register("Custom; Value")
    def decode(context):
        cached = context.reader.try_get_cached_object(dependency, object)
        assert cached is not None
        assert context.reader.read_custom(dependency, lambda: pytest.fail("cache miss")) is cached
        # An independent parse must not share callbacks, caches or partially constructed objects.
        nested = parse_binary(data, DecoderRegistryWithValue(), backend=backend)
        calls.append(nested.resources[0][1])
        return cached

    class DecoderRegistryWithValue(DecoderRegistry):
        def __init__(self):
            super().__init__()
            self.register("Custom; Value", lambda context: 123)

    result = parse_binary(data, registry, backend=backend)
    first, second = result.resources[0]
    assert first.data is second
    assert first.dependencies[0] is second
    assert len(calls) == 1
    assert calls[0] == second and calls[0] is not second


@pytest.mark.parametrize("backend", ["python", "rust", "auto"])
@pytest.mark.parametrize("problem", ["cycle", "unknown", "callback"])
def test_registry_errors_propagate_without_retry(backend, problem):
    fixture = CatalogFixture()
    key = fixture.object("Custom", "Key")
    data = fixture.finish([key, fixture.array([fixture.location()])])
    registry = DecoderRegistry()
    error = RuntimeError("custom failure")
    calls = []

    def fail(context):
        calls.append(context)
        raise error

    if problem == "cycle":
        registry.alias("Custom; Key", "Loop")
        registry.alias("Loop", "Custom; Key")
        expected = ValueError
    elif problem == "unknown":
        registry.alias("Custom; Key", "Unknown")
        expected = UnsupportedSerializedObjectError
    else:
        registry.register("Custom; Key", fail)
        expected = RuntimeError
    with pytest.raises(expected) as caught:
        parse_binary(data, registry, backend=backend)
    if problem == "callback":
        assert caught.value is error
        assert len(calls) == 1
    elif problem == "unknown":
        assert str(caught.value) == "Unsupported object type: Custom; Key"


def test_auto_registry_uses_rust_and_real_sample_matches(catalog_binary_bytes, monkeypatch):
    from addressablestools import catalog

    expected = parse_binary(catalog_binary_bytes, DecoderRegistry(), backend="python")

    def unexpected(*args):
        raise AssertionError("must use native traversal")

    monkeypatch.setattr(catalog, "_decode_binary_resources_python", unexpected)
    actual = parse_binary(catalog_binary_bytes, DecoderRegistry())
    assert actual == expected


@pytest.mark.parametrize("backend", ["python", "rust", "auto"])
def test_legacy_patcher_and_handler_use_same_bridge(backend):
    import AddressablesTools as legacy

    fixture = CatalogFixture()
    obj = fixture.object("Custom", "Value", fixture.record("<i", 17))
    data = fixture.finish([obj, fixture.array([fixture.location(obj)])])
    calls = []

    class Patcher:
        def __bool__(self):
            return False

        def __call__(self, name):
            calls.append(name)
            return None

    def handler(reader, offset, is_default):
        assert not is_default
        reader.seek(offset)
        return reader.read_int32()

    with pytest.warns(DeprecationWarning):
        result = legacy.parse_binary(data, Patcher(), handler, backend=backend)
    assert result.Resources[17][0].Data == 17
    assert calls == ["Custom; Value", "Custom; Value"]

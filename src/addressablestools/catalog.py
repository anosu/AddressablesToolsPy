from __future__ import annotations

from base64 import b64decode
from collections.abc import Iterator
from io import BytesIO
import json
from struct import Struct, error as StructError, unpack_from
from typing import Mapping, Sequence, TypeVar, cast

from addressablestools._native import decode_resources as _native_decode
from addressablestools._native import decode_json_resources as _native_decode_json
from addressablestools._native import decode_registry_resources as _native_decode_registry
from addressablestools._native import Backend, select_decoder, validate_backend
from addressablestools.binary import (
    UINT32_MAX,
    BinaryReader,
    CatalogBinaryHeader,
    CatalogBinaryReader,
)
from addressablestools.decoder import DecoderRegistry, SerializedObjectDecoder
from addressablestools.exceptions import BinaryReadError, CatalogParseError
from addressablestools.models import (
    ContentCatalogData,
    ObjectInitializationData,
    ResourceLocation,
    SerializedType,
)


_INT32 = Struct("<i")
_BUCKET_HEADER = Struct("<2i")
_JSON_LOCATION = Struct("<7i")
_BINARY_LOCATION = Struct("<4Ii2I")
_BINARY_KEY_PAIR = Struct("<2I")
_OBJECT_INITIALIZATION_DATA = Struct("<3I")
_ASCII_STRING_OBJECT_TYPE = SerializedObjectDecoder.ObjectType.ASCII_STRING.value
_UNICODE_STRING_OBJECT_TYPE = SerializedObjectDecoder.ObjectType.UNICODE_STRING.value


def parse_json_catalog(data: str, *, backend: Backend = "auto") -> ContentCatalogData:
    validate_backend(backend)
    try:
        raw = json.loads(data)
    except json.JSONDecodeError as exc:
        raise CatalogParseError(f"invalid catalog JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise CatalogParseError("catalog JSON root must be an object")

    try:
        catalog = ContentCatalogData(
            locator_id=_optional_str(raw.get("m_LocatorId")),
            build_result_hash=_optional_str(raw.get("m_BuildResultHash")),
            instance_provider_data=_object_initialization_data_from_json(
                _mapping(raw["m_InstanceProviderData"], "m_InstanceProviderData")
            ),
            scene_provider_data=_object_initialization_data_from_json(
                _mapping(raw["m_SceneProviderData"], "m_SceneProviderData")
            ),
            resource_provider_data=[
                _object_initialization_data_from_json(_mapping(item, "m_ResourceProviderData item"))
                for item in _list(raw["m_ResourceProviderData"], "m_ResourceProviderData")
            ],
            provider_ids=[str(item) for item in _list(raw["m_ProviderIds"], "m_ProviderIds")],
            internal_ids=[str(item) for item in _list(raw["m_InternalIds"], "m_InternalIds")],
            keys=(
                [str(item) for item in _list(raw["m_Keys"], "m_Keys")]
                if raw.get("m_Keys") is not None
                else None
            ),
            resource_types=[
                _serialized_type_from_json(_mapping(item, "m_resourceTypes item"))
                for item in _list(raw["m_resourceTypes"], "m_resourceTypes")
            ],
            internal_id_prefixes=[
                str(item)
                for item in _list(raw.get("m_InternalIdPrefixes", []), "m_InternalIdPrefixes")
            ],
        )
        decoder = select_decoder(backend, _native_decode_json)
        catalog.resources = (
            decoder(catalog, raw) if decoder is not None else _decode_json_resources(catalog, raw)
        )
        return catalog
    except CatalogParseError:
        raise
    except (KeyError, IndexError, TypeError, ValueError, OverflowError, StructError) as exc:
        raise CatalogParseError(f"invalid catalog JSON data: {exc}") from exc


def parse_binary_catalog(
    data: bytes,
    registry: DecoderRegistry | None = None,
    *,
    backend: Backend = "auto",
) -> ContentCatalogData:
    validate_backend(backend)
    reader = CatalogBinaryReader(BytesIO(data), _buffer=data)
    header = CatalogBinaryHeader.read(reader)

    resource_provider_offsets = reader.read_offset_array(header.init_objects_array_offset)
    catalog = ContentCatalogData(
        version=reader.version,
        locator_id=reader.read_encoded_string(header.id_offset),
        build_result_hash=reader.read_encoded_string(header.build_result_hash_offset),
        instance_provider_data=_object_initialization_data_from_binary(
            reader,
            header.instance_provider_offset,
        ),
        scene_provider_data=_object_initialization_data_from_binary(
            reader,
            header.scene_provider_offset,
        ),
        resource_provider_data=[
            _object_initialization_data_from_binary(reader, offset)
            for offset in resource_provider_offsets
        ],
    )
    catalog.resources = _decode_binary_resources(reader, header, registry, backend=backend)
    return catalog


def _decode_json_resources(
    catalog: ContentCatalogData,
    raw: Mapping[str, object],
) -> dict[object, list[ResourceLocation]]:
    key_offsets, bucket_entries = _read_buckets(str(raw["m_BucketDataString"]))
    keys = _read_keys(str(raw["m_KeyDataString"]), key_offsets)
    locations = _read_locations(catalog, raw, keys)

    resources: dict[object, list[ResourceLocation]] = {}
    location_count = len(locations)
    for key, entries in zip(keys, bucket_entries):
        if len(entries) == 1:
            entry = entries[0]
            if not 0 <= entry < location_count:
                _item_at(locations, entry, "bucket resource location")
            resources[key] = [locations[entry]]
        else:
            if entries and (min(entries) < 0 or max(entries) >= location_count):
                # Keep the original error for the first invalid index.
                for entry in entries:
                    _item_at(locations, entry, "bucket resource location")
            resources[key] = [locations[entry] for entry in entries]
    return resources


def _read_buckets(bucket_data_string: str) -> tuple[list[int], list[tuple[int, ...]]]:
    data = b64decode(bucket_data_string)
    bucket_count = cast(int, _INT32.unpack_from(data)[0])
    if bucket_count < 0:
        raise CatalogParseError("bucket count must be non-negative")

    # Parallel arrays avoid allocating a wrapper object for every bucket.
    key_offsets: list[int] = []
    bucket_entries: list[tuple[int, ...]] = []
    cursor = _INT32.size
    for _ in range(bucket_count):
        offset, entry_count = cast(
            "tuple[int, int]",
            _BUCKET_HEADER.unpack_from(data, cursor),
        )
        cursor += _BUCKET_HEADER.size
        if offset < 0:
            raise CatalogParseError("bucket key offset must be non-negative")
        if entry_count < 0:
            raise CatalogParseError("bucket entry count must be non-negative")
        entries = cast(
            "tuple[int, ...]",
            _INT32.unpack_from(data, cursor) if entry_count == 1
            else unpack_from(f"<{entry_count}i", data, cursor),
        )
        cursor += entry_count * _INT32.size
        key_offsets.append(offset)
        bucket_entries.append(entries)
    return key_offsets, bucket_entries


def _read_keys(key_data_string: str, key_offsets: list[int]) -> list[object]:
    key_data = b64decode(key_data_string)
    key_stream = BytesIO(key_data)
    key_reader = BinaryReader(key_stream, _buffer=key_data)
    key_count = key_reader.read_int32()
    if key_count < 0:
        raise CatalogParseError("key count must be non-negative")
    if key_count != len(key_offsets):
        raise CatalogParseError(f"key count {key_count} does not match bucket count {len(key_offsets)}")
    keys: list[object] = []
    for offset in key_offsets:
        object_type = key_data[offset]
        # String keys dominate real catalogs, so decode them without per-field reader calls.
        if object_type <= _UNICODE_STRING_OBJECT_TYPE:
            length = cast(int, _INT32.unpack_from(key_data, offset + 1)[0])
            if length < 0:
                raise CatalogParseError("key string byte length must be non-negative")
            start = offset + 1 + _INT32.size
            end = start + length
            if end > len(key_data):
                raise CatalogParseError(
                    f"key string data is truncated: expected end offset {end}, "
                    f"got {len(key_data)} bytes"
                )
            encoding = "ascii" if object_type == _ASCII_STRING_OBJECT_TYPE else "utf-16-le"
            keys.append(key_data[start:end].decode(encoding))
            continue

        key_stream.seek(offset)
        keys.append(SerializedObjectDecoder.decode_v1(key_reader))
    return keys


def _read_locations(
    catalog: ContentCatalogData,
    raw: Mapping[str, object],
    keys: list[object],
) -> list[ResourceLocation]:
    entry_data = b64decode(str(raw["m_EntryDataString"]))
    extra_data = b64decode(str(raw["m_ExtraDataString"]))
    extra_stream = BytesIO(extra_data)
    extra_reader = BinaryReader(extra_stream, _buffer=extra_data)
    entry_count = cast(int, _INT32.unpack_from(entry_data)[0])
    if entry_count < 0:
        raise CatalogParseError("resource location count must be non-negative")
    entry_data_end = _INT32.size + entry_count * _JSON_LOCATION.size
    if len(entry_data) < entry_data_end:
        raise CatalogParseError(
            f"resource location data is truncated: expected {entry_data_end} bytes, "
            f"got {len(entry_data)}"
        )
    locations: list[ResourceLocation] = []

    internal_ids = catalog.internal_ids
    if catalog.internal_id_prefixes:
        internal_ids = [
            _apply_internal_id_prefix(value, catalog.internal_id_prefixes) for value in internal_ids
        ]
    provider_ids = catalog.provider_ids
    provider_hashes = [hash(value) for value in provider_ids]
    resource_types = catalog.resource_types
    primary_keys = keys if catalog.keys is None else catalog.keys
    internal_id_count = len(internal_ids)
    provider_count = len(provider_ids)
    key_count = len(keys)
    primary_key_count = len(primary_keys)
    resource_type_count = len(resource_types)

    entry_records = _JSON_LOCATION.iter_unpack(memoryview(entry_data)[_INT32.size : entry_data_end])
    for record in entry_records:
        (
            internal_id_index,
            provider_index,
            dependency_key_index,
            dependency_hash,
            data_index,
            primary_key_index,
            resource_type_index,
        ) = record

        # Validate in the hot loop without a Python function call for every field.
        # The slow path retains field-specific errors, including negative indexes.
        if not (
            0 <= internal_id_index < internal_id_count
            and 0 <= provider_index < provider_count
            and dependency_key_index < key_count
            and 0 <= primary_key_index < primary_key_count
            and 0 <= resource_type_index < resource_type_count
        ):
            _item_at(internal_ids, internal_id_index, "internal ID")
            _item_at(provider_ids, provider_index, "provider ID")
            if dependency_key_index >= 0:
                _item_at(keys, dependency_key_index, "dependency key")
            _item_at(primary_keys, primary_key_index, "primary key")
            _item_at(resource_types, resource_type_index, "resource type")

        internal_id = internal_ids[internal_id_index]
        provider_id = provider_ids[provider_index]
        dependency_key = keys[dependency_key_index] if dependency_key_index >= 0 else None

        if data_index >= 0:
            extra_stream.seek(data_index)
            object_data, data_type = SerializedObjectDecoder._decode_v1(extra_reader)
        else:
            object_data = None
            data_type = None

        primary_key = primary_keys[primary_key_index]

        location = ResourceLocation(
            internal_id,
            provider_id,
            dependency_key,
            None,
            object_data,
            hash(internal_id) * 31 + provider_hashes[provider_index],
            dependency_hash,
            str(primary_key),
            resource_types[resource_type_index],
        )
        location._data_type = data_type
        locations.append(location)
    return locations


def _apply_internal_id_prefix(internal_id: str, prefixes: list[str]) -> str:
    split_index = internal_id.find("#")
    if split_index == -1:
        return internal_id
    try:
        prefix_index = int(internal_id[:split_index])
    except ValueError:
        return internal_id
    if not 0 <= prefix_index < len(prefixes):
        return internal_id
    return prefixes[prefix_index] + internal_id[split_index + 1 :]


def _object_initialization_data_from_json(
    raw: Mapping[str, object],
) -> ObjectInitializationData:
    return ObjectInitializationData(
        id=_optional_str(raw.get("m_Id")),
        object_type=_serialized_type_from_json(_mapping(raw["m_ObjectType"], "m_ObjectType")),
        data=_optional_str(raw.get("m_Data")),
    )


def _serialized_type_from_json(raw: Mapping[str, object]) -> SerializedType:
    return SerializedType(
        assembly_name=str(raw["m_AssemblyName"]),
        class_name=str(raw["m_ClassName"]),
    )


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CatalogParseError(f"{name} must be an object")
    return cast(Mapping[str, object], value)


def _list(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise CatalogParseError(f"{name} must be a list")
    return cast(list[object], value)


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


T = TypeVar("T")


def _item_at(values: Sequence[T], index: int, name: str) -> T:
    if not 0 <= index < len(values):
        raise CatalogParseError(f"{name} index {index} is out of range")
    return values[index]


def _object_initialization_data_from_binary(
    reader: CatalogBinaryReader,
    offset: int,
) -> ObjectInitializationData:
    id_offset, object_type_offset, data_offset = cast(
        "tuple[int, int, int]",
        reader.read_struct_from(_OBJECT_INITIALIZATION_DATA, offset),
    )
    return ObjectInitializationData(
        id=reader.read_encoded_string(id_offset),
        object_type=reader.read_serialized_type(object_type_offset),
        data=reader.read_encoded_string(data_offset),
    )


def _decode_binary_resources(
    reader: CatalogBinaryReader,
    header: CatalogBinaryHeader,
    registry: DecoderRegistry | None = None,
    *,
    backend: Backend = "auto",
) -> dict[object, list[ResourceLocation]]:
    restriction: str | None = None
    if reader._buffer is None:
        restriction = "stream readers require the Python backend"
    elif type(reader._buffer) is not bytes:
        restriction = "Rust binary decoding requires plain immutable bytes; select auto or python"
    if registry is not None:
        registry_decoder = select_decoder(backend, _native_decode_registry, restriction=restriction)
        if registry_decoder is not None and reader._buffer is not None:
            def decode_object(offset: int) -> tuple[object, SerializedType | None]:
                return SerializedObjectDecoder._decode_v2(reader, offset, registry)

            return registry_decoder(
                reader._buffer, reader.version, header.keys_offset, reader._object_cache, decode_object,
            )
        return _decode_binary_resources_python(reader, header, registry)
    decoder = select_decoder(backend, _native_decode, restriction=restriction)
    if decoder is not None and reader._buffer is not None:
        return decoder(reader._buffer, reader.version, header.keys_offset, reader._object_cache)
    return _decode_binary_resources_python(reader, header, registry)


def _decode_binary_resources_python(
    reader: CatalogBinaryReader,
    header: CatalogBinaryHeader,
    registry: DecoderRegistry | None = None,
) -> dict[object, list[ResourceLocation]]:
    pairs: Iterator[tuple[int, int]]
    if reader._buffer is None or header.keys_offset == UINT32_MAX:
        key_location_offsets = reader.read_offset_array(header.keys_offset)
        if len(key_location_offsets) % 2 != 0:
            raise BinaryReadError("key/location offset array must contain pairs")
        offsets = iter(key_location_offsets)
        pairs = zip(offsets, offsets)
    else:
        # This top-level index is consumed once. Iterating the byte view avoids
        # retaining two Python integers per key for the duration of the parse.
        byte_size = cast(int, reader.read_struct_at(_INT32, header.keys_offset - 4)[0])
        if byte_size < 0:
            raise BinaryReadError("offset array byte size must be non-negative")
        if byte_size % 4:
            raise BinaryReadError("offset array byte size must be a multiple of 4")
        if byte_size % _BINARY_KEY_PAIR.size:
            raise BinaryReadError("key/location offset array must contain pairs")
        end = header.keys_offset + byte_size
        if end > len(reader._buffer):
            raise BinaryReadError("key/location offset array is truncated")
        pairs = _BINARY_KEY_PAIR.iter_unpack(memoryview(reader._buffer)[header.keys_offset:end])
    resources: dict[object, list[ResourceLocation]] = {}
    for key_offset, location_list_offset in pairs:
        key = SerializedObjectDecoder.decode_v2(reader, key_offset, registry)
        location_offsets = reader.read_offset_array(location_list_offset)
        resources[key] = [
            _resource_location_from_binary(reader, offset, registry)
            for offset in location_offsets
        ]
    return resources


def _resource_location_from_binary(
    reader: CatalogBinaryReader,
    offset: int,
    registry: DecoderRegistry | None = None,
) -> ResourceLocation:
    cached = reader._object_cache.get(offset)
    if cached is not None:
        return cast(ResourceLocation, cached)
    (
        primary_key_offset,
        internal_id_offset,
        provider_id_offset,
        dependencies_offset,
        dependency_hash_code,
        data_offset,
        type_offset,
    ) = cast(
        "tuple[int, int, int, int, int, int, int]",
        reader.read_struct_from(_BINARY_LOCATION, offset),
    )

    primary_key = reader.read_encoded_string(primary_key_offset, "/")
    internal_id = reader.read_encoded_string(internal_id_offset, "/")
    provider_id = reader.read_encoded_string(provider_id_offset, ".")

    dependency_offsets = reader.read_offset_array(dependencies_offset)
    dependencies = [
        _resource_location_from_binary(reader, dependency_offset, registry)
        for dependency_offset in dependency_offsets
    ]

    object_data, data_type = SerializedObjectDecoder._decode_v2(reader, data_offset, registry)

    location = ResourceLocation(
        internal_id=internal_id,
        provider_id=provider_id,
        dependency_key=None,
        dependencies=dependencies,
        data=object_data,
        hash_code=hash(internal_id) * 31 + hash(provider_id),
        dependency_hash_code=dependency_hash_code,
        primary_key=primary_key,
        type=reader.read_serialized_type(type_offset),
    )
    location._data_type = data_type
    reader._object_cache[offset] = location
    return location

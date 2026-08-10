from __future__ import annotations

from base64 import b64decode
from dataclasses import dataclass
from functools import partial
from io import BytesIO
import json
from struct import Struct, error as StructError, unpack_from
from typing import Mapping, Sequence, TypeVar, cast

from addressablestools.binary import BinaryReader, CatalogBinaryHeader, CatalogBinaryReader
from addressablestools.decoder import DecoderRegistry, SerializedObjectDecoder
from addressablestools.exceptions import BinaryReadError, CatalogParseError
from addressablestools.models import (
    ContentCatalogData,
    ObjectInitializationData,
    ResourceLocation,
    SerializedType,
)


@dataclass(frozen=True, slots=True)
class _Bucket:
    offset: int
    entries: tuple[int, ...]


_INT32 = Struct("<i")
_BUCKET_HEADER = Struct("<2i")
_JSON_LOCATION = Struct("<7i")
_BINARY_LOCATION = Struct("<4Ii2I")
_OBJECT_INITIALIZATION_DATA = Struct("<3I")
_ASCII_STRING_OBJECT_TYPE = SerializedObjectDecoder.ObjectType.ASCII_STRING.value
_UNICODE_STRING_OBJECT_TYPE = SerializedObjectDecoder.ObjectType.UNICODE_STRING.value


def parse_json_catalog(data: str) -> ContentCatalogData:
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
        catalog.resources = _decode_json_resources(catalog, raw)
        return catalog
    except CatalogParseError:
        raise
    except (KeyError, IndexError, TypeError, ValueError, OverflowError, StructError) as exc:
        raise CatalogParseError(f"invalid catalog JSON data: {exc}") from exc


def parse_binary_catalog(
    data: bytes,
    registry: DecoderRegistry | None = None,
) -> ContentCatalogData:
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
    catalog.resources = _decode_binary_resources(reader, header, registry)
    return catalog


def _decode_json_resources(
    catalog: ContentCatalogData,
    raw: Mapping[str, object],
) -> dict[object, list[ResourceLocation]]:
    buckets = _read_buckets(str(raw["m_BucketDataString"]))
    keys = _read_keys(str(raw["m_KeyDataString"]), buckets)
    locations = _read_locations(catalog, raw, keys)

    resources: dict[object, list[ResourceLocation]] = {}
    for index, bucket in enumerate(buckets):
        key = _item_at(keys, index, "bucket key")
        resources[key] = [
            _item_at(locations, entry, "bucket resource location") for entry in bucket.entries
        ]
    return resources


def _read_buckets(bucket_data_string: str) -> list[_Bucket]:
    data = b64decode(bucket_data_string)
    bucket_count = cast(int, _INT32.unpack_from(data)[0])
    if bucket_count < 0:
        raise CatalogParseError("bucket count must be non-negative")

    buckets: list[_Bucket] = []
    cursor = _INT32.size
    for _ in range(bucket_count):
        offset, entry_count = cast(
            tuple[int, int],
            _BUCKET_HEADER.unpack_from(data, cursor),
        )
        cursor += _BUCKET_HEADER.size
        if offset < 0:
            raise CatalogParseError("bucket key offset must be non-negative")
        if entry_count < 0:
            raise CatalogParseError("bucket entry count must be non-negative")
        entries = cast(tuple[int, ...], unpack_from(f"<{entry_count}i", data, cursor))
        cursor += entry_count * _INT32.size
        buckets.append(_Bucket(offset=offset, entries=entries))
    return buckets


def _read_keys(key_data_string: str, buckets: list[_Bucket]) -> list[object]:
    key_data = b64decode(key_data_string)
    key_stream = BytesIO(key_data)
    key_reader = BinaryReader(key_stream, _buffer=key_data)
    key_count = key_reader.read_int32()
    if key_count < 0:
        raise CatalogParseError("key count must be non-negative")
    if key_count != len(buckets):
        raise CatalogParseError(f"key count {key_count} does not match bucket count {len(buckets)}")
    keys: list[object] = []
    for index in range(key_count):
        offset = buckets[index].offset
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

        internal_id = _apply_internal_id_prefix(
            _item_at(catalog.internal_ids, internal_id_index, "internal ID"),
            catalog.internal_id_prefixes,
        )
        provider_id = _item_at(catalog.provider_ids, provider_index, "provider ID")
        dependency_key = (
            _item_at(keys, dependency_key_index, "dependency key")
            if dependency_key_index >= 0
            else None
        )

        if data_index >= 0:
            extra_stream.seek(data_index)
            object_data, data_type = SerializedObjectDecoder._decode_v1(extra_reader)
        else:
            object_data = None
            data_type = None

        primary_key = (
            _item_at(keys, primary_key_index, "primary key")
            if catalog.keys is None
            else _item_at(catalog.keys, primary_key_index, "primary key")
        )

        location = ResourceLocation(
            internal_id=internal_id,
            provider_id=provider_id,
            dependency_key=dependency_key,
            dependencies=None,
            data=object_data,
            hash_code=hash(internal_id) * 31 + hash(provider_id),
            dependency_hash_code=dependency_hash,
            primary_key=str(primary_key),
            type=_item_at(catalog.resource_types, resource_type_index, "resource type"),
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
        tuple[int, int, int],
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
) -> dict[object, list[ResourceLocation]]:
    key_location_offsets = reader.read_offset_array(header.keys_offset)
    if len(key_location_offsets) % 2 != 0:
        raise BinaryReadError("key/location offset array must contain pairs")
    resources: dict[object, list[ResourceLocation]] = {}
    for index in range(0, len(key_location_offsets), 2):
        key_offset = key_location_offsets[index]
        location_list_offset = key_location_offsets[index + 1]
        key = SerializedObjectDecoder.decode_v2(reader, key_offset, registry)
        location_offsets = reader.read_offset_array(location_list_offset)
        resources[key] = [
            reader.read_custom(
                offset,
                partial(_resource_location_from_binary, reader, offset, registry),
            )
            for offset in location_offsets
        ]
    return resources


def _resource_location_from_binary(
    reader: CatalogBinaryReader,
    offset: int,
    registry: DecoderRegistry | None = None,
) -> ResourceLocation:
    (
        primary_key_offset,
        internal_id_offset,
        provider_id_offset,
        dependencies_offset,
        dependency_hash_code,
        data_offset,
        type_offset,
    ) = cast(
        tuple[int, int, int, int, int, int, int],
        reader.read_struct_from(_BINARY_LOCATION, offset),
    )

    primary_key = reader.read_encoded_string(primary_key_offset, "/")
    internal_id = reader.read_encoded_string(internal_id_offset, "/")
    provider_id = reader.read_encoded_string(provider_id_offset, ".")

    dependency_offsets = reader.read_offset_array(dependencies_offset)
    dependencies = [
        reader.read_custom(
            dependency_offset,
            partial(_resource_location_from_binary, reader, dependency_offset, registry),
        )
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
    return location

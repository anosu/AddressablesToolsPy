from __future__ import annotations

from base64 import b64decode
from dataclasses import dataclass
from io import BytesIO
import json
from typing import Mapping, cast

from addressablestools.binary import BinaryReader, CatalogBinaryHeader, CatalogBinaryReader
from addressablestools.decoder import SerializedObjectDecoder
from addressablestools.exceptions import CatalogParseError
from addressablestools.models import (
    ContentCatalogData,
    ObjectInitializationData,
    ResourceLocation,
    SerializedType,
)
from addressablestools.parser import Handler, Patcher


@dataclass(frozen=True, slots=True)
class _Bucket:
    offset: int
    entries: list[int]


def parse_json_catalog(data: str) -> ContentCatalogData:
    try:
        raw = json.loads(data)
    except json.JSONDecodeError as exc:
        raise CatalogParseError(f"invalid catalog JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise CatalogParseError("catalog JSON root must be an object")

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
            str(item) for item in _list(raw.get("m_InternalIdPrefixes", []), "m_InternalIdPrefixes")
        ],
    )
    catalog.resources = _decode_json_resources(catalog, raw)
    return catalog


def parse_binary_catalog(
    data: bytes,
    patcher: Patcher | None = None,
    handler: Handler | None = None,
) -> ContentCatalogData:
    reader = CatalogBinaryReader(BytesIO(data), patcher=patcher, handler=handler)
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
    catalog.resources = _decode_binary_resources(reader, header)
    return catalog


def _decode_json_resources(
    catalog: ContentCatalogData,
    raw: Mapping[str, object],
) -> dict[object, list[ResourceLocation]]:
    buckets = _read_buckets(str(raw["m_BucketDataString"]))
    keys = _read_keys(str(raw["m_KeyDataString"]), buckets)
    locations = _read_locations(catalog, raw, keys)

    return {
        keys[index]: [locations[entry] for entry in bucket.entries]
        for index, bucket in enumerate(buckets)
    }


def _read_buckets(bucket_data_string: str) -> list[_Bucket]:
    bucket_reader = BinaryReader(BytesIO(b64decode(bucket_data_string)))
    bucket_count = bucket_reader.read_int32()
    buckets: list[_Bucket] = []
    for _ in range(bucket_count):
        offset = bucket_reader.read_int32()
        entry_count = bucket_reader.read_int32()
        entries = [int(value) for value in bucket_reader.read_format(f"<{entry_count}i")]
        buckets.append(_Bucket(offset=offset, entries=entries))
    return buckets


def _read_keys(key_data_string: str, buckets: list[_Bucket]) -> list[object]:
    key_stream = BytesIO(b64decode(key_data_string))
    key_reader = BinaryReader(key_stream)
    key_count = key_reader.read_int32()
    keys: list[object] = []
    for index in range(key_count):
        key_stream.seek(buckets[index].offset)
        keys.append(SerializedObjectDecoder.decode_v1(key_reader))
    return keys


def _read_locations(
    catalog: ContentCatalogData,
    raw: Mapping[str, object],
    keys: list[object],
) -> list[ResourceLocation]:
    entry_reader = BinaryReader(BytesIO(b64decode(str(raw["m_EntryDataString"]))))
    extra_stream = BytesIO(b64decode(str(raw["m_ExtraDataString"])))
    extra_reader = BinaryReader(extra_stream)
    entry_count = entry_reader.read_int32()
    locations: list[ResourceLocation] = []

    for _ in range(entry_count):
        internal_id_index = entry_reader.read_int32()
        provider_index = entry_reader.read_int32()
        dependency_key_index = entry_reader.read_int32()
        dependency_hash = entry_reader.read_int32()
        data_index = entry_reader.read_int32()
        primary_key_index = entry_reader.read_int32()
        resource_type_index = entry_reader.read_int32()

        internal_id = _apply_internal_id_prefix(
            catalog.internal_ids[internal_id_index],
            catalog.internal_id_prefixes,
        )
        provider_id = catalog.provider_ids[provider_index]
        dependency_key = keys[dependency_key_index] if dependency_key_index >= 0 else None

        if data_index >= 0:
            extra_stream.seek(data_index)
            object_data = SerializedObjectDecoder.decode_v1(extra_reader)
        else:
            object_data = None

        primary_key = (
            keys[primary_key_index] if catalog.keys is None else catalog.keys[primary_key_index]
        )

        locations.append(
            ResourceLocation(
                internal_id=internal_id,
                provider_id=provider_id,
                dependency_key=dependency_key,
                dependencies=None,
                data=object_data,
                hash_code=hash(internal_id) * 31 + hash(provider_id),
                dependency_hash_code=dependency_hash,
                primary_key=str(primary_key),
                type=catalog.resource_types[resource_type_index],
            )
        )
    return locations


def _apply_internal_id_prefix(internal_id: str, prefixes: list[str]) -> str:
    split_index = internal_id.find("#")
    if split_index == -1:
        return internal_id
    try:
        prefix_index = int(internal_id[:split_index])
    except ValueError:
        return internal_id
    if prefix_index >= len(prefixes):
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


def _object_initialization_data_from_binary(
    reader: CatalogBinaryReader,
    offset: int,
) -> ObjectInitializationData:
    reader.seek(offset)
    id_offset = reader.read_uint32()
    object_type_offset = reader.read_uint32()
    data_offset = reader.read_uint32()
    return ObjectInitializationData(
        id=reader.read_encoded_string(id_offset),
        object_type=reader.read_serialized_type(object_type_offset),
        data=reader.read_encoded_string(data_offset),
    )


def _decode_binary_resources(
    reader: CatalogBinaryReader,
    header: CatalogBinaryHeader,
) -> dict[object, list[ResourceLocation]]:
    key_location_offsets = reader.read_offset_array(header.keys_offset)
    resources: dict[object, list[ResourceLocation]] = {}
    for index in range(0, len(key_location_offsets), 2):
        key_offset = key_location_offsets[index]
        location_list_offset = key_location_offsets[index + 1]
        key = SerializedObjectDecoder.decode_v2(reader, key_offset)
        location_offsets = reader.read_offset_array(location_list_offset)
        resources[key] = [
            reader.read_custom(
                offset,
                lambda resource_offset=offset: _resource_location_from_binary(
                    reader,
                    resource_offset,
                ),
            )
            for offset in location_offsets
        ]
    return resources


def _resource_location_from_binary(
    reader: CatalogBinaryReader,
    offset: int,
) -> ResourceLocation:
    reader.seek(offset)
    primary_key_offset = reader.read_uint32()
    internal_id_offset = reader.read_uint32()
    provider_id_offset = reader.read_uint32()
    dependencies_offset = reader.read_uint32()
    dependency_hash_code = reader.read_int32()
    data_offset = reader.read_uint32()
    type_offset = reader.read_uint32()

    primary_key = reader.read_encoded_string(primary_key_offset, "/")
    internal_id = reader.read_encoded_string(internal_id_offset, "/")
    provider_id = reader.read_encoded_string(provider_id_offset, ".")

    dependency_offsets = reader.read_offset_array(dependencies_offset)
    dependencies = [
        reader.read_custom(
            dependency_offset,
            lambda resource_offset=dependency_offset: _resource_location_from_binary(
                reader,
                resource_offset,
            ),
        )
        for dependency_offset in dependency_offsets
    ]

    return ResourceLocation(
        internal_id=internal_id,
        provider_id=provider_id,
        dependency_key=None,
        dependencies=dependencies,
        data=SerializedObjectDecoder.decode_v2(reader, data_offset),
        hash_code=hash(internal_id) * 31 + hash(provider_id),
        dependency_hash_code=dependency_hash_code,
        primary_key=primary_key,
        type=reader.read_serialized_type(type_offset),
    )

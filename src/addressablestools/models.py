from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import struct
from typing import Generic, TypeAlias, TypeVar


@dataclass(frozen=True, slots=True)
class SerializedType:
    assembly_name: str | None
    class_name: str | None

    @property
    def assembly_short_name(self) -> str:
        if self.assembly_name is None:
            raise ValueError("assembly_name is required")
        return self.assembly_name.split(",", 1)[0]

    @property
    def match_name(self) -> str:
        if self.class_name is None:
            raise ValueError("class_name is required")
        return f"{self.assembly_short_name}; {self.class_name}"


@dataclass(frozen=True, slots=True)
class TypeReference:
    clsid: str


@dataclass(frozen=True, slots=True)
class Hash128:
    value: str

    @classmethod
    def from_uint32s(cls, first: int, second: int, third: int, fourth: int) -> Hash128:
        return cls(struct.pack("<IIII", first, second, third, fourth).hex())


@dataclass(frozen=True, slots=True)
class ClassJsonObject:
    type: SerializedType
    json_text: str


@dataclass(frozen=True, slots=True)
class ObjectInitializationData:
    id: str | None
    object_type: SerializedType
    data: str | None


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class WrappedSerializedObject(Generic[T]):
    type: SerializedType
    object: T


class AssetLoadMode(Enum):
    REQUESTED_ASSET_AND_DEPENDENCIES = 0
    ALL_PACKED_ASSETS_AND_DEPENDENCIES = 1


@dataclass(slots=True)
class CommonInfo:
    timeout: int = 0
    redirect_limit: int = 0
    retry_count: int = 0
    asset_load_mode: AssetLoadMode = AssetLoadMode.ALL_PACKED_ASSETS_AND_DEPENDENCIES
    chunked_transfer: bool = False
    use_crc_for_cached_bundle: bool = False
    use_unity_web_request_for_local_bundles: bool = False
    clear_other_cached_versions_when_loaded: bool = False
    version: int = 0


@dataclass(slots=True)
class AssetBundleRequestOptions:
    hash: str = ""
    crc: int = 0
    common_info: CommonInfo | None = None
    bundle_name: str | None = None
    bundle_size: int = 0


SerializedObject: TypeAlias = (
    ClassJsonObject
    | TypeReference
    | Hash128
    | int
    | str
    | bool
    | WrappedSerializedObject[AssetBundleRequestOptions]
    | None
)


@dataclass(slots=True)
class ResourceLocation:
    internal_id: str | None = None
    provider_id: str | None = None
    dependency_key: object = None
    dependencies: list[ResourceLocation] | None = None
    data: SerializedObject = None
    hash_code: int = 0
    dependency_hash_code: int = 0
    primary_key: str | None = None
    type: SerializedType | None = None


@dataclass(slots=True)
class ContentCatalogData:
    version: int = 0
    locator_id: str | None = None
    build_result_hash: str | None = None
    instance_provider_data: ObjectInitializationData | None = None
    scene_provider_data: ObjectInitializationData | None = None
    resource_provider_data: list[ObjectInitializationData] = field(default_factory=list)
    provider_ids: list[str] = field(default_factory=list)
    internal_ids: list[str] = field(default_factory=list)
    keys: list[str] | None = None
    resource_types: list[SerializedType] = field(default_factory=list)
    internal_id_prefixes: list[str] = field(default_factory=list)
    resources: dict[object, list[ResourceLocation]] = field(default_factory=dict)


__all__ = [
    "AssetBundleRequestOptions",
    "AssetLoadMode",
    "ClassJsonObject",
    "CommonInfo",
    "ContentCatalogData",
    "Hash128",
    "ObjectInitializationData",
    "ResourceLocation",
    "SerializedObject",
    "SerializedType",
    "TypeReference",
    "WrappedSerializedObject",
]

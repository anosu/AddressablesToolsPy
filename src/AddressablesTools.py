from __future__ import annotations

import sys
import warnings
from collections.abc import Callable
from io import BytesIO
from types import ModuleType
from typing import Any, cast

import addressablestools
from addressablestools.binary import CatalogBinaryReader
from addressablestools.decoder import (
    BinaryDecodeContext,
    DecoderRegistry,
    SerializedObjectDecoder,
)
from addressablestools.models import (
    AssetBundleRequestOptions,
    ClassJsonObject,
    CommonInfo,
    ContentCatalogData,
    Hash128,
    ObjectInitializationData,
    ResourceLocation,
    SerializedType,
    TypeReference,
)

type Patcher = Callable[[str], str | None]
type Handler = Callable[[CatalogBinaryReader, int, bool], object]

_LEGACY_HANDLER_MATCH_NAME = "\0AddressablesTools.legacy-handler"


class _LegacyDecoderRegistry(DecoderRegistry):
    def __init__(self, patcher: Patcher | None, handler: Handler | None) -> None:
        super().__init__()
        self._patcher = patcher if patcher is not None else lambda match_name: match_name
        self._handler = handler if handler is not None else lambda _reader, _offset, _default: None
        self.register(_LEGACY_HANDLER_MATCH_NAME, self._decode_legacy)

    def _resolve(self, match_name: str, /) -> str:
        resolved = self._patcher(match_name)
        if resolved is None:
            return _LEGACY_HANDLER_MATCH_NAME
        return super()._resolve(resolved)

    def _decode_legacy(self, context: BinaryDecodeContext) -> object:
        return self._handler(context.reader, context.offset, context.is_default)


__path__: list[str] = []
__version__ = addressablestools.__version__


class _CompatValue:
    def __init__(self, value: object) -> None:
        self._value = value

    def __eq__(self, other: object) -> bool:
        if isinstance(other, _CompatValue):
            return self._value == other._value
        return self._value == other

    def __hash__(self) -> int:
        return hash(self._value)

    def __repr__(self) -> str:
        return repr(self._value)


class CompatSerializedType(_CompatValue):
    _value: SerializedType

    @property
    def AssemblyName(self) -> str | None:
        return self._value.assembly_name

    @property
    def ClassName(self) -> str | None:
        return self._value.class_name

    def get_assembly_short_name(self) -> str:
        return self._value.assembly_short_name

    def get_match_name(self) -> str:
        return self._value.match_name


class CompatTypeReference(_CompatValue):
    _value: TypeReference

    @property
    def Clsid(self) -> str:
        return self._value.clsid


class CompatHash128(_CompatValue):
    _value: Hash128

    @property
    def Value(self) -> str:
        return self._value.value


class CompatClassJsonObject(_CompatValue):
    _value: ClassJsonObject

    @property
    def Type(self) -> object:
        return wrap_legacy(self._value.type)

    @property
    def JsonText(self) -> str:
        return self._value.json_text


class CompatObjectInitializationData(_CompatValue):
    _value: ObjectInitializationData

    @property
    def Id(self) -> str | None:
        return self._value.id

    @property
    def ObjectType(self) -> object:
        return wrap_legacy(self._value.object_type)

    @property
    def Data(self) -> str | None:
        return self._value.data


class CompatCommonInfo(_CompatValue):
    _value: CommonInfo

    @property
    def Timeout(self) -> int:
        return self._value.timeout

    @property
    def RedirectLimit(self) -> int:
        return self._value.redirect_limit

    @property
    def RetryCount(self) -> int:
        return self._value.retry_count

    @property
    def AssetLoadMode(self) -> object:
        return self._value.asset_load_mode

    @property
    def ChunkedTransfer(self) -> bool:
        return self._value.chunked_transfer

    @property
    def UseCrcForCachedBundle(self) -> bool:
        return self._value.use_crc_for_cached_bundle

    @property
    def UseUnityWebRequestForLocalBundles(self) -> bool:
        return self._value.use_unity_web_request_for_local_bundles

    @property
    def ClearOtherCachedVersionsWhenLoaded(self) -> bool:
        return self._value.clear_other_cached_versions_when_loaded

    @property
    def Version(self) -> int:
        return self._value.version


class CompatAssetBundleRequestOptions(_CompatValue):
    _value: AssetBundleRequestOptions

    @property
    def Hash(self) -> str:
        return self._value.hash

    @property
    def Crc(self) -> int:
        return self._value.crc

    @property
    def ComInfo(self) -> object:
        return wrap_legacy(self._value.common_info)

    @property
    def BundleName(self) -> str | None:
        return self._value.bundle_name

    @property
    def BundleSize(self) -> int:
        return self._value.bundle_size


class CompatWrappedSerializedObject(_CompatValue):
    def __init__(self, serialized_type: object, obj: object) -> None:
        if isinstance(serialized_type, CompatSerializedType):
            serialized_type = serialized_type._value
        if not isinstance(serialized_type, SerializedType):
            raise TypeError("type must be a SerializedType")
        if isinstance(obj, _CompatValue):
            obj = obj._value
        self._type = serialized_type
        self._object = obj
        super().__init__((serialized_type, obj))

    @property
    def Type(self) -> object:
        return wrap_legacy(self._type)

    @property
    def Object(self) -> object:
        return wrap_legacy(self._object)


class CompatResourceLocation(_CompatValue):
    _value: ResourceLocation

    @property
    def InternalId(self) -> str | None:
        return self._value.internal_id

    @property
    def ProviderId(self) -> str | None:
        return self._value.provider_id

    @property
    def DependencyKey(self) -> object:
        return wrap_legacy(self._value.dependency_key)

    @property
    def Dependencies(self) -> object:
        return wrap_legacy(self._value.dependencies)

    @property
    def Data(self) -> object:
        if isinstance(self._value.data, AssetBundleRequestOptions):
            data_type = self._value._data_type
            if data_type is not None:
                return CompatWrappedSerializedObject(data_type, self._value.data)
        return wrap_legacy(self._value.data)

    @property
    def HashCode(self) -> int:
        return self._value.hash_code

    @property
    def DependencyHashCode(self) -> int:
        return self._value.dependency_hash_code

    @property
    def PrimaryKey(self) -> str | None:
        return self._value.primary_key

    @property
    def Type(self) -> object:
        return wrap_legacy(self._value.type)


class CompatCatalog(_CompatValue):
    _value: ContentCatalogData

    @property
    def Version(self) -> int:
        return self._value.version

    @property
    def LocatorId(self) -> str | None:
        return self._value.locator_id

    @property
    def BuildResultHash(self) -> str | None:
        return self._value.build_result_hash

    @property
    def InstanceProviderData(self) -> object:
        return wrap_legacy(self._value.instance_provider_data)

    @property
    def SceneProviderData(self) -> object:
        return wrap_legacy(self._value.scene_provider_data)

    @property
    def ResourceProviderData(self) -> list[object]:
        return [wrap_legacy(item) for item in self._value.resource_provider_data]

    @property
    def ProviderIds(self) -> list[str]:
        return self._value.provider_ids

    @property
    def InternalIds(self) -> list[str]:
        return self._value.internal_ids

    @property
    def Keys(self) -> list[str] | None:
        return self._value.keys

    @property
    def ResourceTypes(self) -> list[object]:
        return [wrap_legacy(item) for item in self._value.resource_types]

    @property
    def InternalIdPrefixes(self) -> list[str]:
        return self._value.internal_id_prefixes

    @property
    def Resources(self) -> dict[object, list[object]]:
        return {
            wrap_legacy(key): [wrap_legacy(location) for location in locations]
            for key, locations in self._value.resources.items()
        }


def wrap_legacy(value: object) -> object:
    if value is None or isinstance(value, str | int | bool):
        return value
    if isinstance(value, ContentCatalogData):
        return CompatCatalog(value)
    if isinstance(value, ResourceLocation):
        return CompatResourceLocation(value)
    if isinstance(value, AssetBundleRequestOptions):
        return CompatAssetBundleRequestOptions(value)
    if isinstance(value, CommonInfo):
        return CompatCommonInfo(value)
    if isinstance(value, ObjectInitializationData):
        return CompatObjectInitializationData(value)
    if isinstance(value, ClassJsonObject):
        return CompatClassJsonObject(value)
    if isinstance(value, SerializedType):
        return CompatSerializedType(value)
    if isinstance(value, Hash128):
        return CompatHash128(value)
    if isinstance(value, TypeReference):
        return CompatTypeReference(value)
    if isinstance(value, list):
        return [wrap_legacy(item) for item in value]
    if isinstance(value, dict):
        return {wrap_legacy(key): wrap_legacy(item) for key, item in value.items()}
    return value


def parse(
    data: str | bytes,
    patcher: Patcher | None = None,
    handler: Handler | None = None,
) -> CompatCatalog:
    _warn_deprecated("AddressablesTools.parse")
    if isinstance(data, str):
        parsed = addressablestools.parse_json(data)
    else:
        parsed = addressablestools.parse_binary(
            data,
            registry=_LegacyDecoderRegistry(patcher, handler),
        )
    return cast(
        CompatCatalog,
        wrap_legacy(parsed),
    )


def parse_json(data: str) -> CompatCatalog:
    _warn_deprecated("AddressablesTools.parse_json")
    return cast(CompatCatalog, wrap_legacy(addressablestools.parse_json(data)))


def parse_binary(
    data: bytes,
    patcher: Patcher | None = None,
    handler: Handler | None = None,
) -> CompatCatalog:
    _warn_deprecated("AddressablesTools.parse_binary")
    return cast(
        CompatCatalog,
        wrap_legacy(
            addressablestools.parse_binary(
                data,
                registry=_LegacyDecoderRegistry(patcher, handler),
            )
        ),
    )


def _warn_deprecated(name: str) -> None:
    warnings.warn(
        f"{name} is deprecated; use the addressablestools package instead.",
        DeprecationWarning,
        stacklevel=3,
    )


class _Parser:
    from_json = staticmethod(parse_json)
    from_binary = staticmethod(parse_binary)


Parser = _Parser


class CompatCatalogBinaryReader(CatalogBinaryReader):
    def __init__(
        self,
        stream: BytesIO,
        patcher: Patcher | None = None,
        handler: Handler | None = None,
    ) -> None:
        super().__init__(stream)
        self._patcher = patcher
        self._handler = handler

    @property
    def Version(self) -> int:
        return self.version

    @Version.setter
    def Version(self, value: int) -> None:
        self.version = value


class CompatSerializedObjectDecoder:
    INT_MATCHNAME = SerializedObjectDecoder.INT_MATCH_NAME
    LONG_MATCHNAME = SerializedObjectDecoder.LONG_MATCH_NAME
    BOOL_MATCHNAME = SerializedObjectDecoder.BOOL_MATCH_NAME
    STRING_MATCHNAME = SerializedObjectDecoder.STRING_MATCH_NAME
    HASH128_MATCHNAME = SerializedObjectDecoder.HASH128_MATCH_NAME
    ABRO_MATCHNAME = SerializedObjectDecoder.ASSET_BUNDLE_REQUEST_OPTIONS_MATCH_NAME

    @staticmethod
    def decode_v1(reader: object) -> object:
        value, serialized_type = SerializedObjectDecoder._decode_v1(cast(Any, reader))
        if isinstance(value, AssetBundleRequestOptions) and serialized_type is not None:
            return CompatWrappedSerializedObject(serialized_type, value)
        return wrap_legacy(value)

    @staticmethod
    def decode_v2(
        reader: CatalogBinaryReader,
        offset: int,
        patcher: Patcher | None = None,
        handler: Handler | None = None,
    ) -> object:
        if isinstance(reader, CompatCatalogBinaryReader):
            patcher = patcher if patcher is not None else reader._patcher
            handler = handler if handler is not None else reader._handler
        value, serialized_type = SerializedObjectDecoder._decode_v2(
            reader,
            offset,
            _LegacyDecoderRegistry(patcher, handler),
        )
        if isinstance(value, AssetBundleRequestOptions) and serialized_type is not None:
            return CompatWrappedSerializedObject(serialized_type, value)
        return wrap_legacy(value)

    read_string1 = staticmethod(SerializedObjectDecoder.read_string1)
    read_string4 = staticmethod(SerializedObjectDecoder.read_string4)
    read_string4_unicode = staticmethod(SerializedObjectDecoder.read_string4_unicode)


CompatCatalogBinaryReader.__name__ = "CatalogBinaryReader"
CompatCatalogBinaryReader.__qualname__ = "CatalogBinaryReader"
CompatSerializedObjectDecoder.__name__ = "SerializedObjectDecoder"
CompatSerializedObjectDecoder.__qualname__ = "SerializedObjectDecoder"


classes = cast(Any, ModuleType("AddressablesTools.classes"))
classes.WrappedSerializedObject = CompatWrappedSerializedObject
classes.ContentCatalogData = CompatCatalog
classes.ClassJsonObject = CompatClassJsonObject
classes.SerializedType = CompatSerializedType
classes.ResourceLocation = CompatResourceLocation
classes.ObjectInitializationData = CompatObjectInitializationData
classes.TypeReference = CompatTypeReference
classes.Hash128 = CompatHash128
classes.AssetBundleRequestOptions = CompatAssetBundleRequestOptions
classes.SerializedObjectDecoder = CompatSerializedObjectDecoder
classes.CatalogBinaryReader = CompatCatalogBinaryReader
classes.__all__ = [
    "WrappedSerializedObject",
    "ContentCatalogData",
    "ClassJsonObject",
    "SerializedType",
    "ResourceLocation",
    "ObjectInitializationData",
    "TypeReference",
    "Hash128",
    "AssetBundleRequestOptions",
    "SerializedObjectDecoder",
    "CatalogBinaryReader",
]
sys.modules["AddressablesTools.classes"] = classes

__all__ = [
    "Parser",
    "classes",
    "parse",
    "parse_binary",
    "parse_json",
]

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
import json
from struct import Struct
from typing import TypeVar, cast, overload

from addressablestools.binary import UINT32_MAX, BinaryReader, CatalogBinaryReader
from addressablestools.exceptions import UnsupportedSerializedObjectError
from addressablestools.models import (
    AssetBundleRequestOptions,
    AssetLoadMode,
    ClassJsonObject,
    CommonInfo,
    Hash128,
    SerializedType,
    TypeReference,
)


@dataclass(frozen=True, slots=True)
class BinaryDecodeContext:
    """Context supplied to a registered binary object decoder.

    Attributes:
        reader: Reader positioned by the decoder as needed.
        offset: Offset of the serialized object payload.
        is_default: Whether the catalog stores the type's default value.
        serialized_type: Exact Unity type identity read from the catalog.
    """

    reader: CatalogBinaryReader
    offset: int
    is_default: bool
    serialized_type: SerializedType


T = TypeVar("T")
type ObjectDecoder[T] = Callable[[BinaryDecodeContext], T]

_OBJECT_DATA = Struct("<2I")
_STRING_OBJECT = Struct("<IB")
_HASH128 = Struct("<16s")
_ASSET_BUNDLE_REQUEST_OPTIONS = Struct("<5I")
_COMMON_INFO = Struct("<hBBi")


class DecoderRegistry:
    """Per-parse registry for custom binary object decoders and type aliases.

    Registries are intentionally independent rather than global, so customizations
    cannot leak between catalog parses or tests.
    """

    def __init__(self) -> None:
        self._decoders: dict[str, ObjectDecoder[object]] = {}
        self._aliases: dict[str, str] = {}
        self._revision = 0

    @overload
    def register(self, match_name: str, decoder: ObjectDecoder[T], /) -> ObjectDecoder[T]: ...

    @overload
    def register(
        self,
        match_name: str,
        decoder: None = None,
        /,
    ) -> Callable[[ObjectDecoder[T]], ObjectDecoder[T]]: ...

    def register(
        self,
        match_name: str,
        decoder: ObjectDecoder[T] | None = None,
        /,
    ) -> ObjectDecoder[T] | Callable[[ObjectDecoder[T]], ObjectDecoder[T]]:
        """Register a decoder directly or use the result as a decorator.

        Args:
            match_name: Unity serialized type match name.
            decoder: Optional decoder function. Omit it for decorator usage.
        """

        def add(registered: ObjectDecoder[T]) -> ObjectDecoder[T]:
            self._decoders[match_name] = cast(ObjectDecoder[object], registered)
            self._revision += 1
            return registered

        return add if decoder is None else add(decoder)

    def alias(self, match_name: str, target: str, /) -> None:
        """Map one serialized type match name to another registered or built-in type."""

        self._aliases[match_name] = target
        self._revision += 1

    def _resolve(self, match_name: str, /) -> str:
        resolved = match_name
        visited: set[str] = set()
        while resolved in self._aliases:
            if resolved in visited:
                raise ValueError(f"decoder alias cycle contains {resolved!r}")
            visited.add(resolved)
            resolved = self._aliases[resolved]
        return resolved

    def _get(self, match_name: str, /) -> ObjectDecoder[object] | None:
        return self._decoders.get(match_name)


class SerializedObjectDecoder:
    INT_MATCH_NAME = "mscorlib; System.Int32"
    LONG_MATCH_NAME = "mscorlib; System.Int64"
    BOOL_MATCH_NAME = "mscorlib; System.Boolean"
    STRING_MATCH_NAME = "mscorlib; System.String"
    INT_V3_MATCH_NAME = "System.Int32"
    LONG_V3_MATCH_NAME = "System.Int64"
    BOOL_V3_MATCH_NAME = "System.Boolean"
    STRING_V3_MATCH_NAME = "System.String"
    HASH128_MATCH_NAME = "UnityEngine.CoreModule; UnityEngine.Hash128"
    ASSET_BUNDLE_REQUEST_OPTIONS_MATCH_NAME = (
        "Unity.ResourceManager; "
        "UnityEngine.ResourceManagement.ResourceProviders.AssetBundleRequestOptions"
    )

    class ObjectType(Enum):
        ASCII_STRING = 0
        UNICODE_STRING = 1
        UINT16 = 2
        UINT32 = 3
        INT32 = 4
        HASH128 = 5
        TYPE = 6
        JSON_OBJECT = 7

    @staticmethod
    def decode_v1(reader: BinaryReader) -> object:
        """Decode a version 1 serialized value without returning type metadata."""

        return SerializedObjectDecoder._decode_v1(reader)[0]

    @staticmethod
    def _decode_v1(reader: BinaryReader) -> tuple[object, SerializedType | None]:
        object_type = SerializedObjectDecoder.ObjectType(reader.read_byte())
        match object_type:
            case SerializedObjectDecoder.ObjectType.ASCII_STRING:
                return SerializedObjectDecoder.read_string4(reader), None
            case SerializedObjectDecoder.ObjectType.UNICODE_STRING:
                return SerializedObjectDecoder.read_string4_unicode(reader), None
            case SerializedObjectDecoder.ObjectType.UINT16:
                return reader.read_uint16(), None
            case SerializedObjectDecoder.ObjectType.UINT32:
                return reader.read_uint32(), None
            case SerializedObjectDecoder.ObjectType.INT32:
                return reader.read_int32(), None
            case SerializedObjectDecoder.ObjectType.HASH128:
                return Hash128(SerializedObjectDecoder.read_string1(reader)), None
            case SerializedObjectDecoder.ObjectType.TYPE:
                return TypeReference(SerializedObjectDecoder.read_string1(reader)), None
            case SerializedObjectDecoder.ObjectType.JSON_OBJECT:
                assembly_name = SerializedObjectDecoder.read_string1(reader)
                class_name = SerializedObjectDecoder.read_string1(reader)
                json_text = SerializedObjectDecoder.read_string4_unicode(reader)
                serialized_type = SerializedType(assembly_name, class_name)
                if serialized_type.match_name_for_version(1) == (
                    SerializedObjectDecoder.ASSET_BUNDLE_REQUEST_OPTIONS_MATCH_NAME
                ):
                    return (
                        SerializedObjectDecoder.decode_asset_bundle_request_options_json(json_text),
                        serialized_type,
                    )
                return ClassJsonObject(serialized_type, json_text), serialized_type

    @staticmethod
    def decode_v2(
        reader: CatalogBinaryReader,
        offset: int,
        registry: DecoderRegistry | None = None,
    ) -> object:
        """Decode a binary catalog value without returning type metadata."""

        return SerializedObjectDecoder._decode_v2(reader, offset, registry)[0]

    @staticmethod
    def _decode_v2(
        reader: CatalogBinaryReader,
        offset: int,
        registry: DecoderRegistry | None = None,
    ) -> tuple[object, SerializedType | None]:
        if offset == UINT32_MAX:
            return None, None

        type_name_offset, object_offset = cast(
            "tuple[int, int]",
            reader.read_struct_from(_OBJECT_DATA, offset),
        )
        is_default_object = object_offset == UINT32_MAX

        cached_type = reader._type_name_cache.get(type_name_offset)
        if cached_type is None or cached_type[0] != reader.version:
            serialized_type = reader.read_serialized_type(type_name_offset)
            match_name = serialized_type.match_name_for_version(reader.version)
            reader._type_name_cache[type_name_offset] = (reader.version, serialized_type, match_name)
        else:
            _, serialized_type, match_name = cached_type
        resolved_match_name = registry._resolve(match_name) if registry is not None else match_name
        custom_decoder = registry._get(resolved_match_name) if registry is not None else None
        if custom_decoder is not None:
            context = BinaryDecodeContext(
                reader=reader,
                offset=object_offset,
                is_default=is_default_object,
                serialized_type=serialized_type,
            )
            return custom_decoder(context), serialized_type

        match resolved_match_name:
            case SerializedObjectDecoder.INT_MATCH_NAME | SerializedObjectDecoder.INT_V3_MATCH_NAME:
                if is_default_object:
                    return 0, serialized_type
                reader.seek(object_offset)
                return reader.read_int32(), serialized_type
            case (
                SerializedObjectDecoder.LONG_MATCH_NAME | SerializedObjectDecoder.LONG_V3_MATCH_NAME
            ):
                if is_default_object:
                    return 0, serialized_type
                reader.seek(object_offset)
                return reader.read_int64(), serialized_type
            case (
                SerializedObjectDecoder.BOOL_MATCH_NAME | SerializedObjectDecoder.BOOL_V3_MATCH_NAME
            ):
                if is_default_object:
                    return False, serialized_type
                reader.seek(object_offset)
                return reader.read_boolean(), serialized_type
            case (
                SerializedObjectDecoder.STRING_MATCH_NAME
                | SerializedObjectDecoder.STRING_V3_MATCH_NAME
            ):
                if is_default_object:
                    return None, serialized_type
                string_offset, separator_value = cast(
                    "tuple[int, int]",
                    reader.read_struct_from(_STRING_OBJECT, object_offset),
                )
                separator = chr(separator_value)
                return reader.read_encoded_string(string_offset, separator), serialized_type
            case SerializedObjectDecoder.HASH128_MATCH_NAME:
                if is_default_object:
                    return None, serialized_type
                reader.seek(object_offset)
                return Hash128.from_uint32s(*reader.read_four_uint32()), serialized_type
            case SerializedObjectDecoder.ASSET_BUNDLE_REQUEST_OPTIONS_MATCH_NAME:
                if is_default_object:
                    return None, serialized_type
                options = reader._object_cache.get(object_offset)
                if options is None:
                    options = SerializedObjectDecoder.decode_asset_bundle_request_options_binary(
                        reader,
                        object_offset,
                    )
                    reader._object_cache[object_offset] = options
                return options, serialized_type
            case _:
                raise UnsupportedSerializedObjectError(f"Unsupported object type: {match_name}")

    @staticmethod
    def decode_asset_bundle_request_options_json(json_text: str) -> AssetBundleRequestOptions:
        try:
            payload = json.loads(json_text)
        except json.JSONDecodeError:
            return AssetBundleRequestOptions()

        if not isinstance(payload, dict) or not payload:
            return AssetBundleRequestOptions()

        if payload.get("m_ChunkedTransfer") is None:
            common_info_version = 1
        elif (
            payload.get("m_AssetLoadMode") is None
            and payload.get("m_UseCrcForCachedBundle") is None
            and payload.get("m_UseCrcForCachedBundles") is None
            and payload.get("m_UseUWRForLocalBundles") is None
            and payload.get("m_ClearOtherCachedVersionsWhenLoaded") is None
        ):
            common_info_version = 2
        else:
            common_info_version = 3

        return AssetBundleRequestOptions(
            hash=str(payload.get("m_Hash", "")),
            crc=int(payload.get("m_Crc", 0)),
            bundle_name=payload.get("m_BundleName"),
            bundle_size=int(payload.get("m_BundleSize", 0)),
            common_info=CommonInfo(
                timeout=int(payload.get("m_Timeout", 0)),
                redirect_limit=int(payload.get("m_RedirectLimit", 0)),
                retry_count=int(payload.get("m_RetryCount", 0)),
                asset_load_mode=AssetLoadMode(int(payload.get("m_AssetLoadMode", 0))),
                chunked_transfer=bool(payload.get("m_ChunkedTransfer", False)),
                use_crc_for_cached_bundle=bool(
                    payload.get(
                        "m_UseCrcForCachedBundle",
                        payload.get("m_UseCrcForCachedBundles", False),
                    )
                ),
                use_unity_web_request_for_local_bundles=bool(
                    payload.get("m_UseUWRForLocalBundles", False)
                ),
                clear_other_cached_versions_when_loaded=bool(
                    payload.get("m_ClearOtherCachedVersionsWhenLoaded", False)
                ),
                version=common_info_version,
            ),
        )

    @staticmethod
    def decode_asset_bundle_request_options_binary(
        reader: CatalogBinaryReader,
        offset: int,
    ) -> AssetBundleRequestOptions:
        hash_offset, bundle_name_offset, crc, bundle_size, common_info_offset = cast(
            "tuple[int, int, int, int, int]",
            reader.read_struct_from(_ASSET_BUNDLE_REQUEST_OPTIONS, offset),
        )

        # Hash128's little-endian representation is already the desired byte order.
        hash_value = cast(bytes, reader.read_struct_from(_HASH128, hash_offset)[0]).hex()
        common_info = cast("CommonInfo | None", reader._object_cache.get(common_info_offset))
        if common_info is None:
            common_info = SerializedObjectDecoder.decode_common_info_binary(reader, common_info_offset)
            reader._object_cache[common_info_offset] = common_info
        common_info.version = 3
        return AssetBundleRequestOptions(
            hash=hash_value,
            crc=crc,
            common_info=common_info,
            bundle_name=reader.read_encoded_string(bundle_name_offset, "_"),
            bundle_size=bundle_size,
        )

    @staticmethod
    def decode_common_info_binary(reader: CatalogBinaryReader, offset: int) -> CommonInfo:
        timeout, redirect_limit, retry_count, flags = cast(
            "tuple[int, int, int, int]",
            reader.read_struct_from(_COMMON_INFO, offset),
        )
        return CommonInfo(
            timeout=timeout,
            redirect_limit=redirect_limit,
            retry_count=retry_count,
            asset_load_mode=(
                AssetLoadMode.ALL_PACKED_ASSETS_AND_DEPENDENCIES
                if (flags & 1) != 0
                else AssetLoadMode.REQUESTED_ASSET_AND_DEPENDENCIES
            ),
            chunked_transfer=(flags & 2) != 0,
            use_crc_for_cached_bundle=(flags & 4) != 0,
            use_unity_web_request_for_local_bundles=(flags & 8) != 0,
            clear_other_cached_versions_when_loaded=(flags & 16) != 0,
        )

    @staticmethod
    def read_string1(reader: BinaryReader) -> str:
        length = reader.read_byte()
        return reader.read_bytes(length).decode("ascii")

    @staticmethod
    def read_string4(reader: BinaryReader) -> str:
        length = reader.read_int32()
        return reader.read_bytes(length).decode("ascii")

    @staticmethod
    def read_string4_unicode(reader: BinaryReader) -> str:
        length = reader.read_int32()
        return reader.read_bytes(length).decode("utf-16le")


__all__ = [
    "BinaryDecodeContext",
    "DecoderRegistry",
    "ObjectDecoder",
    "SerializedObjectDecoder",
]

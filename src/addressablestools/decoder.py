from __future__ import annotations

from enum import Enum
import json

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
    WrappedSerializedObject,
)


class SerializedObjectDecoder:
    INT_MATCH_NAME = "mscorlib; System.Int32"
    LONG_MATCH_NAME = "mscorlib; System.Int64"
    BOOL_MATCH_NAME = "mscorlib; System.Boolean"
    STRING_MATCH_NAME = "mscorlib; System.String"
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
        object_type = SerializedObjectDecoder.ObjectType(reader.read_byte())
        match object_type:
            case SerializedObjectDecoder.ObjectType.ASCII_STRING:
                return SerializedObjectDecoder.read_string4(reader)
            case SerializedObjectDecoder.ObjectType.UNICODE_STRING:
                return SerializedObjectDecoder.read_string4_unicode(reader)
            case SerializedObjectDecoder.ObjectType.UINT16:
                return reader.read_uint16()
            case SerializedObjectDecoder.ObjectType.UINT32:
                return reader.read_uint32()
            case SerializedObjectDecoder.ObjectType.INT32:
                return reader.read_int32()
            case SerializedObjectDecoder.ObjectType.HASH128:
                return Hash128(SerializedObjectDecoder.read_string1(reader))
            case SerializedObjectDecoder.ObjectType.TYPE:
                return TypeReference(SerializedObjectDecoder.read_string1(reader))
            case SerializedObjectDecoder.ObjectType.JSON_OBJECT:
                assembly_name = SerializedObjectDecoder.read_string1(reader)
                class_name = SerializedObjectDecoder.read_string1(reader)
                json_text = SerializedObjectDecoder.read_string4_unicode(reader)
                json_object = ClassJsonObject(
                    type=SerializedType(assembly_name, class_name),
                    json_text=json_text,
                )
                if json_object.type.match_name == (
                    SerializedObjectDecoder.ASSET_BUNDLE_REQUEST_OPTIONS_MATCH_NAME
                ):
                    return WrappedSerializedObject(
                        json_object.type,
                        SerializedObjectDecoder.decode_asset_bundle_request_options_json(json_text),
                    )
                return json_object

    @staticmethod
    def decode_v2(reader: CatalogBinaryReader, offset: int) -> object:
        if offset == UINT32_MAX:
            return None

        reader.seek(offset)
        type_name_offset = reader.read_uint32()
        object_offset = reader.read_uint32()
        is_default_object = object_offset == UINT32_MAX

        serialized_type = reader.read_serialized_type(type_name_offset)
        match_name = serialized_type.match_name
        patched_match_name = reader.patcher(match_name)

        match patched_match_name:
            case SerializedObjectDecoder.INT_MATCH_NAME:
                if is_default_object:
                    return 0
                reader.seek(object_offset)
                return reader.read_int32()
            case SerializedObjectDecoder.LONG_MATCH_NAME:
                if is_default_object:
                    return 0
                reader.seek(object_offset)
                return reader.read_int64()
            case SerializedObjectDecoder.BOOL_MATCH_NAME:
                if is_default_object:
                    return False
                reader.seek(object_offset)
                return reader.read_boolean()
            case SerializedObjectDecoder.STRING_MATCH_NAME:
                if is_default_object:
                    return None
                reader.seek(object_offset)
                string_offset = reader.read_uint32()
                separator = reader.read_char()
                return reader.read_encoded_string(string_offset, separator)
            case SerializedObjectDecoder.HASH128_MATCH_NAME:
                if is_default_object:
                    return None
                reader.seek(object_offset)
                return Hash128.from_uint32s(*reader.read_four_uint32())
            case SerializedObjectDecoder.ASSET_BUNDLE_REQUEST_OPTIONS_MATCH_NAME:
                if is_default_object:
                    return None
                options = reader.read_custom(
                    object_offset,
                    lambda: SerializedObjectDecoder.decode_asset_bundle_request_options_binary(
                        reader,
                        object_offset,
                    ),
                )
                return WrappedSerializedObject(serialized_type, options)
            case None:
                return reader.handler(reader, object_offset, is_default_object)
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
        reader.seek(offset)
        hash_offset = reader.read_uint32()
        bundle_name_offset = reader.read_uint32()
        crc = reader.read_uint32()
        bundle_size = reader.read_uint32()
        common_info_offset = reader.read_uint32()

        reader.seek(hash_offset)
        hash_value = Hash128.from_uint32s(*reader.read_four_uint32()).value
        common_info = reader.read_custom(
            common_info_offset,
            lambda: SerializedObjectDecoder.decode_common_info_binary(reader, common_info_offset),
        )
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
        reader.seek(offset)
        timeout = reader.read_int16()
        redirect_limit = reader.read_byte()
        retry_count = reader.read_byte()
        flags = reader.read_int32()
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


__all__ = ["SerializedObjectDecoder"]

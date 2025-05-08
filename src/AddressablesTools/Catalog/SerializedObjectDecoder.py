from enum import Enum

from .ClassJsonObject import ClassJsonObject
from .SerializedType import SerializedType
from .WrappedSerializedObject import WrappedSerializedObject
from ..constants import uint
from ..Classes.AssetBundleRequestOptions import AssetBundleRequestOptions
from ..Classes.Hash128 import Hash128
from ..Classes.TypeReference import TypeReference
from ..Reader.BinaryReader import BinaryReader
from ..Reader.CatalogBinaryReader import CatalogBinaryReader, Patcher, Handler


class SerializedObjectDecoder:
    INT_TYPENAME = "System.Int32"
    LONG_TYPENAME = "System.Int64"
    BOOL_TYPENAME = "System.Boolean"
    STRING_TYPENAME = "System.String"
    HASH128_TYPENAME = "UnityEngine.Hash128"
    ABRO_TYPENAME = (
        "UnityEngine.ResourceManagement.ResourceProviders.AssetBundleRequestOptions"
    )

    INT_MATCHNAME = "mscorlib; " + INT_TYPENAME
    LONG_MATCHNAME = "mscorlib; " + LONG_TYPENAME
    BOOL_MATCHNAME = "mscorlib; " + BOOL_TYPENAME
    STRING_MATCHNAME = "mscorlib; " + STRING_TYPENAME
    HASH128_MATCHNAME = "UnityEngine.CoreModule; " + HASH128_TYPENAME
    ABRO_MATCHNAME = "Unity.ResourceManager; " + ABRO_TYPENAME

    class ObjectType(Enum):
        AsciiString = 0
        UnicodeString = 1
        UInt16 = 2
        UInt32 = 3
        Int32 = 4
        Hash128 = 5
        Type = 6
        JsonObject = 7

    @staticmethod
    def decode_v1(br: BinaryReader):
        type = SerializedObjectDecoder.ObjectType(br.read_byte())
        match type:
            case SerializedObjectDecoder.ObjectType.AsciiString:
                return SerializedObjectDecoder.read_string4(br)
            case SerializedObjectDecoder.ObjectType.UnicodeString:
                return SerializedObjectDecoder.read_string4_unicode(br)
            case SerializedObjectDecoder.ObjectType.UInt16:
                return br.read_uint16()
            case SerializedObjectDecoder.ObjectType.UInt32:
                return br.read_uint32()
            case SerializedObjectDecoder.ObjectType.Int32:
                return br.read_int32()
            case SerializedObjectDecoder.ObjectType.Hash128:
                return Hash128(SerializedObjectDecoder.read_string1(br))
            case SerializedObjectDecoder.ObjectType.Type:
                return TypeReference(SerializedObjectDecoder.read_string1(br))
            case SerializedObjectDecoder.ObjectType.JsonObject:
                assemblyName = SerializedObjectDecoder.read_string1(br)
                className = SerializedObjectDecoder.read_string1(br)
                jsonText = SerializedObjectDecoder.read_string4_unicode(br)

                jsonObj = ClassJsonObject(assemblyName, className, jsonText)
                matchName = jsonObj.Type.get_match_name()
                match matchName:
                    case SerializedObjectDecoder.ABRO_MATCHNAME:
                        return WrappedSerializedObject(
                            jsonObj.Type, AssetBundleRequestOptions._from_json(jsonText)
                        )
                return jsonObj
            case _:
                return None

    @staticmethod
    def decode_v2(
        reader: CatalogBinaryReader,
        offset: int,
        patcher: Patcher,
        handler: Handler,
    ):
        if offset == uint.MaxValue:
            return None

        reader.seek(offset)
        typeNameOffset = reader.read_uint32()
        objectOffset = reader.read_uint32()

        isDefaultObject = objectOffset == uint.MaxValue

        # serializedType = SerializedType.FromBinary(reader, typeNameOffset)
        serializedType = reader.read_custom(
            typeNameOffset, lambda: SerializedType._from_binary(reader, typeNameOffset)
        )
        matchName = serializedType.get_match_name()
        match patcher(matchName):
            case SerializedObjectDecoder.INT_MATCHNAME:
                if isDefaultObject:
                    return 0
                reader.seek(objectOffset)
                return reader.read_int32()
            case SerializedObjectDecoder.LONG_MATCHNAME:
                if isDefaultObject:
                    return 0
                reader.seek(objectOffset)
                return reader.read_int64()
            case SerializedObjectDecoder.BOOL_MATCHNAME:
                if isDefaultObject:
                    return False
                reader.seek(objectOffset)
                return reader.read_boolean()
            case SerializedObjectDecoder.STRING_MATCHNAME:
                if isDefaultObject:
                    return None
                reader.seek(objectOffset)
                stringOffset = reader.read_uint32()
                seperator = reader.read_char()
                return reader.read_encoded_string(stringOffset, seperator)
            case SerializedObjectDecoder.HASH128_MATCHNAME:
                if isDefaultObject:
                    return None
                reader.seek(objectOffset)
                return Hash128(*reader.read_4uint32())
            case SerializedObjectDecoder.ABRO_MATCHNAME:
                if isDefaultObject:
                    return None
                obj = reader.read_custom(
                    objectOffset,
                    lambda: AssetBundleRequestOptions._from_binary(
                        reader, objectOffset
                    ),
                )
                return WrappedSerializedObject(serializedType, obj)
            case None:
                return handler(reader, objectOffset, isDefaultObject)
            case _:
                raise Exception(f"Unsupported object type: {matchName}")

    @staticmethod
    def read_string1(br: BinaryReader):
        length = br.read_byte()
        return br.read_bytes(length).decode("ascii")

    @staticmethod
    def read_string4(br: BinaryReader):
        length = br.read_int32()
        return br.read_bytes(length).decode("ascii")

    @staticmethod
    def read_string4_unicode(br: BinaryReader):
        length = br.read_int32()
        return br.read_bytes(length).decode("utf-16le")

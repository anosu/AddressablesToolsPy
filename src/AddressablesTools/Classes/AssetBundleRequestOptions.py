from __future__ import annotations

import json
from enum import Enum
from struct import unpack

from .Hash128 import Hash128
from ..Reader.CatalogBinaryReader import CatalogBinaryReader


class AssetLoadMode(Enum):
    RequestedAssetAndDependencies = 0
    AllPackedAssetsAndDependencies = 1


_AssetLoadMode = AssetLoadMode


class AssetBundleRequestOptions:
    __slots__ = ("Hash", "Crc", "ComInfo", "BundleName", "BundleSize")

    Hash: str | None
    Crc: int
    ComInfo: CommonInfo | None
    BundleName: str | None
    BundleSize: int

    @classmethod
    def FromJson(cls, jsonText: str):
        obj = cls()
        obj.ReadJson(jsonText)
        return obj

    @classmethod
    def FromBinary(cls, reader: CatalogBinaryReader, offset: int):
        obj = cls()
        obj.ReadBinary(reader, offset)
        return obj

    def __repr__(self):
        return (
            f"<{self.__class__.__name__}("
            f"Hash={self.Hash}, "
            f"Crc={self.Crc}, "
            f"ComInfo={self.ComInfo}, "
            f"BundleName={self.BundleName}, "
            f"BundleSize={self.BundleSize}"
            f")>"
        )

    def __init__(self):
        self.Hash = None
        self.Crc = 0
        self.ComInfo = None
        self.BundleName = None
        self.BundleSize = 0

    class CommonInfo:
        __slots__ = (
            "Timeout",
            "RedirectLimit",
            "RetryCount",
            "AssetLoadMode",
            "ChunkedTransfer",
            "UseCrcForCachedBundle",
            "UseUnityWebRequestForLocalBundles",
            "ClearOtherCachedVersionsWhenLoaded",
            "Version",
        )

        Timeout: int
        RedirectLimit: int
        RetryCount: int
        AssetLoadMode: AssetLoadMode
        ChunkedTransfer: bool
        UseCrcForCachedBundle: bool
        UseUnityWebRequestForLocalBundles: bool
        ClearOtherCachedVersionsWhenLoaded: bool

        Version: int  # not real field

        @classmethod
        def FromBinary(cls, reader: CatalogBinaryReader, offset: int):
            obj = cls()
            obj.Read(reader, offset)
            return obj

        def __repr__(self):
            return (
                f"<{self.__class__.__name__}("
                f"Timeout={self.Timeout}, "
                f"RedirectLimit={self.RedirectLimit}, "
                f"RetryCount={self.RetryCount}, "
                f"AssetLoadMode={self.AssetLoadMode}, "
                f"ChunkedTransfer={self.ChunkedTransfer}, "
                f"UseCrcForCachedBundle={self.UseCrcForCachedBundle}, "
                f"UseUnityWebRequestForLocalBundles={self.UseUnityWebRequestForLocalBundles}, "
                f"ClearOtherCachedVersionsWhenLoaded={self.ClearOtherCachedVersionsWhenLoaded}"
                f")>"
            )

        def __init__(
            self,
            timeout: int = 0,
            redirectLimit: int = 0,
            retryCount: int = 0,
            assetLoadMode: AssetLoadMode = _AssetLoadMode.AllPackedAssetsAndDependencies,
            chunkedTransfer: bool = False,
            useCrcForCachedBundle: bool = False,
            useUnityWebRequestForLocalBundles: bool = False,
            clearOtherCachedVersionsWhenLoaded: bool = False,
            version: int = 0,
        ):
            self.Timeout = timeout
            self.RedirectLimit = redirectLimit
            self.RetryCount = retryCount
            self.AssetLoadMode = assetLoadMode
            self.ChunkedTransfer = chunkedTransfer
            self.UseCrcForCachedBundle = useCrcForCachedBundle
            self.UseUnityWebRequestForLocalBundles = useUnityWebRequestForLocalBundles
            self.ClearOtherCachedVersionsWhenLoaded = clearOtherCachedVersionsWhenLoaded
            self.Version = version

        def Read(self, reader: CatalogBinaryReader, offset: int):
            reader.Seek(offset)

            timeout = reader.ReadInt16()
            redirectLimit = reader.ReadByte()
            retryCount = reader.ReadByte()
            flags = reader.ReadInt32()

            self.Timeout = timeout
            self.RedirectLimit = redirectLimit
            self.RetryCount = retryCount

            if (flags & 1) != 0:
                self.AssetLoadMode = AssetLoadMode.AllPackedAssetsAndDependencies
            else:
                self.AssetLoadMode = AssetLoadMode.RequestedAssetAndDependencies

            self.ChunkedTransfer = (flags & 2) != 0
            self.UseCrcForCachedBundle = (flags & 4) != 0
            self.UseUnityWebRequestForLocalBundles = (flags & 8) != 0
            self.ClearOtherCachedVersionsWhenLoaded = (flags & 16) != 0

    def ReadJson(self, jsonText: str):
        try:
            jsonObj = json.loads(jsonText)
        except json.JSONDecodeError:
            return
        except Exception as e:
            raise e

        if not jsonObj:
            return

        self.Hash = jsonObj["m_Hash"]
        self.Crc = jsonObj["m_Crc"]
        self.BundleName = jsonObj["m_BundleName"]
        self.BundleSize = jsonObj["m_BundleSize"]

        commonInfoVersion: int
        if jsonObj["m_ChunkedTransfer"] is None:
            commonInfoVersion = 1
        elif (
            jsonObj["m_AssetLoadMode"] is None
            and jsonObj["m_UseCrcForCachedBundles"] is None
            and jsonObj["m_UseUWRForLocalBundles"] is None
            and jsonObj["m_ClearOtherCachedVersionsWhenLoaded"] is None
        ):
            commonInfoVersion = 2
        else:
            commonInfoVersion = 3

        self.ComInfo = AssetBundleRequestOptions.CommonInfo(
            jsonObj["m_Timeout"],
            jsonObj["m_ChunkedTransfer"],
            jsonObj["m_RedirectLimit"],
            jsonObj["m_RetryCount"],
            AssetLoadMode(jsonObj.get("m_AssetLoadMode", 0)),
            jsonObj.get("m_UseCrcForCachedBundle", False),
            jsonObj.get("m_UseUWRForLocalBundles", False),
            jsonObj.get("m_ClearOtherCachedVersionsWhenLoaded", False),
            commonInfoVersion,
        )

    def ReadBinary(self, reader: CatalogBinaryReader, offset: int):
        reader.Seek(offset)

        hashOffset, bundleNameOffset, crc, bundleSize, commonInfoOffset = unpack(
            "<5I", reader.ReadBytes(20)
        )

        reader.Seek(hashOffset)
        self.Hash = Hash128(*unpack("<4I", reader.ReadBytes(16))).Value

        self.BundleName = reader.ReadEncodedString(bundleNameOffset, "_")
        self.Crc = crc
        self.BundleSize = bundleSize

        self.ComInfo = AssetBundleRequestOptions.CommonInfo.FromBinary(
            reader, commonInfoOffset
        )
        self.ComInfo.Version = 3


__all__ = ["AssetBundleRequestOptions"]

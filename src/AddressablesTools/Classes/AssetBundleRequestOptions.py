from __future__ import annotations

import json
from enum import Enum

from ..Reader import CatalogBinaryReader
from .Hash128 import Hash128


class AssetLoadMode(Enum):
    RequestedAssetAndDependencies = 0
    AllPackedAssetsAndDependencies = 1


class AssetBundleRequestOptions:
    Hash: str | None
    Crc: int
    ComInfo: CommonInfo | None
    BundleName: str | None
    BundleSize: int

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
        Timeout: int
        RedirectLimit: int
        RetryCount: int
        AssetLoadMode: AssetLoadMode
        ChunkedTransfer: bool
        UseCrcForCachedBundle: bool
        UseUnityWebRequestForLocalBundles: bool
        ClearOtherCachedVersionsWhenLoaded: bool

        Version: int

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

        def Read(self, reader: CatalogBinaryReader, offset: int):
            reader.BaseStream.seek(offset)

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
        self.ComInfo = AssetBundleRequestOptions.CommonInfo()
        self.ComInfo.Version = commonInfoVersion
        self.ComInfo.Timeout = jsonObj["m_Timeout"]
        self.ComInfo.ChunkedTransfer = jsonObj["m_ChunkedTransfer"]
        self.ComInfo.RedirectLimit = jsonObj["m_RedirectLimit"]
        self.ComInfo.RetryCount = jsonObj["m_RetryCount"]
        self.ComInfo.AssetLoadMode = AssetLoadMode(jsonObj.get("m_AssetLoadMode", 0))
        self.ComInfo.UseCrcForCachedBundle = jsonObj.get(
            "m_UseCrcForCachedBundle", False
        )
        self.ComInfo.UseUnityWebRequestForLocalBundles = jsonObj.get(
            "m_UseUWRForLocalBundles", False
        )
        self.ComInfo.ClearOtherCachedVersionsWhenLoaded = jsonObj.get(
            "m_ClearOtherCachedVersionsWhenLoaded", False
        )

    def ReadBinary(self, reader: CatalogBinaryReader, offset: int):
        reader.BaseStream.seek(offset)

        hashOffset = reader.ReadUInt32()
        bundleNameOffset = reader.ReadUInt32()
        crc = reader.ReadUInt32()
        bundleSize = reader.ReadUInt32()
        commonInfoOffset = reader.ReadUInt32()

        reader.BaseStream.seek(hashOffset)
        hashV0 = reader.ReadUInt32()
        hashV1 = reader.ReadUInt32()
        hashV2 = reader.ReadUInt32()
        hashV3 = reader.ReadUInt32()
        self.Hash = Hash128(hashV0, hashV1, hashV2, hashV3).Value

        self.BundleName = reader.ReadEncodedString(bundleNameOffset, "_")
        self.Crc = crc
        self.BundleSize = bundleSize

        commonInfo = AssetBundleRequestOptions.CommonInfo()
        commonInfo.Version = 3
        commonInfo.Read(reader, commonInfoOffset)


__all__ = ["AssetBundleRequestOptions"]

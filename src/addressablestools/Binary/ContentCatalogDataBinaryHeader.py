from ..constants import uint
from ..Reader.CatalogBinaryReader import CatalogBinaryReader


class ContentCatalogDataBinaryHeader:
    Magic: int
    Version: int
    KeysOffset: int
    IdOffset: int
    InstanceProviderOffset: int
    SceneProviderOffset: int
    InitObjectsArrayOffset: int
    BuildResultHashOffset: int

    def __repr__(self):
        return (
            f"{self.__class__.__name__}("
            f"Magic={self.Magic}, "
            f"Version={self.Version}, "
            f"KeysOffset={self.KeysOffset}, "
            f"IdOffset={self.IdOffset}, "
            f"InstanceProviderOffset={self.InstanceProviderOffset}, "
            f"SceneProviderOffset={self.SceneProviderOffset}, "
            f"InitObjectsArrayOffset={self.InitObjectsArrayOffset}, "
            f"BuildResultHashOffset={self.BuildResultHashOffset}"
            f")"
        )

    def __init__(self):
        self.Magic = 0
        self.Version = 0
        self.KeysOffset = 0
        self.IdOffset = 0
        self.InstanceProviderOffset = 0
        self.SceneProviderOffset = 0
        self.InitObjectsArrayOffset = 0
        self.BuildResultHashOffset = 0

    def _read(self, reader: CatalogBinaryReader):
        self.Magic = reader.read_int32()
        self.Version = reader.read_int32()
        if self.Version not in [1, 2]:
            raise Exception("Only versions 1 and 2 are supported")
        reader.Version = self.Version

        self.KeysOffset = reader.read_uint32()
        self.IdOffset = reader.read_uint32()
        self.InstanceProviderOffset = reader.read_uint32()
        self.SceneProviderOffset = reader.read_uint32()
        self.InitObjectsArrayOffset = reader.read_uint32()
        self.BuildResultHashOffset = (
            uint.MaxValue
            if self.Version == 1 and self.KeysOffset == 0x20
            else reader.read_uint32()
        )

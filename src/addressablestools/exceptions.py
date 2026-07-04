class AddressablesToolsError(Exception):
    """Base exception for addressablestools failures."""


class CatalogParseError(AddressablesToolsError):
    """Raised when catalog input cannot be parsed."""


class UnsupportedCatalogVersionError(CatalogParseError):
    """Raised when a binary catalog version is not supported."""


class UnsupportedSerializedObjectError(CatalogParseError):
    """Raised when a serialized object type is not supported."""


class BinaryReadError(CatalogParseError):
    """Raised when binary catalog data cannot be read safely."""

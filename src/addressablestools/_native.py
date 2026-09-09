"""Native capabilities and per-call backend selection."""

from collections.abc import Callable
from importlib import import_module
from typing import Literal, cast
from typing import TYPE_CHECKING

from addressablestools.exceptions import NativeBackendUnavailableError
from addressablestools.models import ContentCatalogData, ResourceLocation, SerializedType

if TYPE_CHECKING:
    from addressablestools.binary import CatalogBinaryReader
    from addressablestools.decoder import DecoderRegistry

type Backend = Literal["auto", "python", "rust"]

type DecodeResources = Callable[
    [bytes, int, int, dict[int, object]], dict[object, list[ResourceLocation]]
]

type DecodeJsonResources = Callable[
    [ContentCatalogData, dict[str, object]], dict[object, list[ResourceLocation]]
]

type DecodeRegistryResources = Callable[
    [bytes, int, int, dict[int, object], Callable[[int], tuple[object, SerializedType | None]]],
    dict[object, list[ResourceLocation]],
]

type DecodeRegistryResourcesFast = Callable[
    [bytes, int, int, dict[int, object], Callable[[int], tuple[object, SerializedType | None]],
     "DecoderRegistry", "CatalogBinaryReader"],
    dict[object, list[ResourceLocation]],
]

decode_resources: DecodeResources | None = None
decode_json_resources: DecodeJsonResources | None = None
decode_registry_resources: DecodeRegistryResources | None = None
decode_registry_resources_fast: DecodeRegistryResourcesFast | None = None
_load_error: str | None = None
try:
    _extension = import_module("addressablestools._rust")
except (ImportError, OSError) as exc:
    _load_error = f"cannot load the bundled addressablestools._rust module: {exc}"
else:
    _version = getattr(_extension, "API_VERSION", None)
    if type(_version) is not int or _version not in (1, 2, 3):
        _load_error = f"unsupported native API version {_version!r}; rebuild addressablestools"
    else:
        if callable(getattr(_extension, "decode_resources", None)):
            decode_resources = cast(DecodeResources, _extension.decode_resources)
        if _version >= 2 and callable(getattr(_extension, "decode_json_resources", None)):
            decode_json_resources = cast(DecodeJsonResources, _extension.decode_json_resources)
        if _version >= 3 and callable(getattr(_extension, "decode_resources_with_registry", None)):
            decode_registry_resources = cast(
                DecodeRegistryResources, _extension.decode_resources_with_registry,
            )
        if _version >= 3 and callable(getattr(_extension, "decode_resources_with_registry_fast", None)):
            decode_registry_resources_fast = cast(
                DecodeRegistryResourcesFast, _extension.decode_resources_with_registry_fast,
            )


def validate_backend(backend: Backend) -> None:
    if backend not in ("auto", "python", "rust"):
        raise ValueError(f"unknown backend {backend!r}; expected auto, python, or rust")


def select_decoder[T](
    backend: Backend, decoder: T | None, *, restriction: str | None = None,
) -> T | None:
    validate_backend(backend)
    if backend == "python":
        return None
    if restriction is not None:
        if backend == "rust":
            raise NativeBackendUnavailableError(restriction)
        return None
    if decoder is None and backend == "rust":
        reason = _load_error or "installed extension does not provide this decoder"
        raise NativeBackendUnavailableError(
            f"Rust backend unavailable: {reason}. Install/rebuild with uv sync --locked, "
            "or select backend='python'."
        )
    return decoder


def available_backends(format: Literal["binary", "json"] = "binary") -> tuple[Backend, ...]:
    """Return installed backends for a format; registry acceleration needs native API 3."""
    if format not in ("binary", "json"):
        raise ValueError(f"unknown catalog format {format!r}")
    decoder = decode_resources if format == "binary" else decode_json_resources
    return ("python", "rust") if decoder is not None else ("python",)

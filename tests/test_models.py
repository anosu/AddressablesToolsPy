from addressablestools.models import (
    AssetBundleRequestOptions,
    AssetLoadMode,
    ClassJsonObject,
    Hash128,
    ObjectInitializationData,
    ResourceLocation,
    SerializedType,
    TypeReference,
    WrappedSerializedObject,
)


def test_serialized_type_match_name_uses_short_assembly_name() -> None:
    serialized_type = SerializedType(
        assembly_name="Unity.ResourceManager, Version=0.0.0.0, Culture=neutral, PublicKeyToken=null",
        class_name="UnityEngine.ResourceManagement.ResourceProviders.AssetBundleRequestOptions",
    )

    assert serialized_type.assembly_short_name == "Unity.ResourceManager"
    assert serialized_type.match_name == (
        "Unity.ResourceManager; "
        "UnityEngine.ResourceManagement.ResourceProviders.AssetBundleRequestOptions"
    )


def test_hash128_from_four_uint32_values_matches_existing_byte_order() -> None:
    value = Hash128.from_uint32s(0x11223344, 0x55667788, 0x99AABBCC, 0xDDEEFF00)

    assert value.value == "4433221188776655ccbbaa9900ffeedd"


def test_resource_location_uses_pythonic_fields() -> None:
    resource_type = SerializedType("Assembly, Version=1.0.0.0", "ClassName")
    location = ResourceLocation(
        internal_id="bundle/path",
        provider_id="provider",
        dependency_key="dependency",
        dependencies=None,
        data=None,
        hash_code=123,
        dependency_hash_code=456,
        primary_key="primary",
        type=resource_type,
    )

    assert location.internal_id == "bundle/path"
    assert location.provider_id == "provider"
    assert location.primary_key == "primary"
    assert location.type == resource_type


def test_asset_bundle_request_options_defaults_are_typed() -> None:
    options = AssetBundleRequestOptions()

    assert options.hash == ""
    assert options.crc == 0
    assert options.bundle_name is None
    assert options.bundle_size == 0
    assert options.common_info is None


def test_wrapped_serialized_object_keeps_type_and_object() -> None:
    serialized_type = SerializedType("Assembly, Version=1.0.0.0", "ClassName")
    wrapped = WrappedSerializedObject(type=serialized_type, object=TypeReference("clsid"))

    assert wrapped.type is serialized_type
    assert wrapped.object == TypeReference("clsid")


def test_catalog_related_models_are_importable() -> None:
    serialized_type = SerializedType("Assembly, Version=1.0.0.0", "ClassName")
    obj = ObjectInitializationData(id="id", object_type=serialized_type, data=None)
    json_obj = ClassJsonObject(type=serialized_type, json_text="{}")

    assert obj.id == "id"
    assert json_obj.type == serialized_type
    assert AssetLoadMode.ALL_PACKED_ASSETS_AND_DEPENDENCIES.value == 1

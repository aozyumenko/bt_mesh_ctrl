from enum import IntEnum
from typing import Final

from bluetooth_mesh.messages.properties import PropertyID
from bluetooth_mesh.models import (
    ConfigServer,
    ConfigClient,
    HealthServer,
    HealthClient,
    RemoteProvisioningServer,
    RemoteProvisioningClient,
    PrivateBeaconServer,
    PrivateBeaconClient,
)
from bluetooth_mesh.models.generic.onoff import GenericOnOffServer
from bluetooth_mesh.models.generic.dtt import GenericDTTServer
from bluetooth_mesh.models.generic.level import GenericLevelServer
from bluetooth_mesh.models.generic.ponoff import GenericPowerOnOffServer, GenericPowerOnOffSetupServer
from bluetooth_mesh.models.generic.battery import GenericBatteryServer
from bluetooth_mesh.models.sensor import SensorServer, SensorSetupServer, SensorClient
from bluetooth_mesh.models.light.lightness import LightLightnessServer, LightLightnessSetupServer
from bluetooth_mesh.models.light.ctl import LightCTLServer, LightCTLSetupServer, LightCTLTemperatureServer
from bluetooth_mesh.models.light.hsl import LightHSLServer, LightHSLSetupServer, LightHSLHueServer, LightHSLSaturationServer
from bluetooth_mesh.models.vendor.thermostat import ThermostatServer

from bluetooth_mesh.messages.config import ConfigOpcode
from bluetooth_mesh.messages.health import HealthOpcode
from bluetooth_mesh.messages.generic.battery import GenericBatteryOpcode
from bluetooth_mesh.messages.generic.level import GenericLevelOpcode
from bluetooth_mesh.messages.generic.onoff import GenericOnOffOpcode
from bluetooth_mesh.messages.generic.dtt import GenericDTTOpcode
from bluetooth_mesh.messages.generic.ponoff import GenericPowerOnOffOpcode, GenericPowerOnOffSetupOpcode
from bluetooth_mesh.messages.light.lightness import LightLightnessOpcode, LightLightnessSetupOpcode
from bluetooth_mesh.messages.light.ctl import LightCTLOpcode, LightCTLSetupOpcode
from bluetooth_mesh.messages.light.hsl import LightHSLOpcode, LightHSLSetupOpcode
from bluetooth_mesh.messages.scene import SceneOpcode
from bluetooth_mesh.messages.sensor import SensorOpcode, SensorSetupOpcode
from bluetooth_mesh.messages.time import TimeOpcode
from bluetooth_mesh.messages.vendor.thermostat import ThermostatOpcode


__all__ = (
    "IntEnumName",
    "BtMeshModelId",
    "BtSensorAttrPropertyId",
    "BtMeshOpcode"
)


class IntEnumName(IntEnum):
    @classmethod
    def has_value(_class, val: int):
        return val in _class._value2member_map_

    @classmethod
    def get_name(_class, val: int):
        return _class(val).name if _class.has_value(val) else "%04x" % (val)


def model_id_to_num(model_id):
    return (0 if model_id[0] is None else model_id[0] * 65536) + model_id[1]


class BtMeshModelId(IntEnumName):
    """ BT Mesh model names. """
    ConfigServer = model_id_to_num(ConfigServer.MODEL_ID)
    ConfigClient = model_id_to_num(ConfigClient.MODEL_ID)
    HealthServer = model_id_to_num(HealthServer.MODEL_ID)
    HealthClient = model_id_to_num(HealthClient.MODEL_ID)
    RemoteProvisioningServer = model_id_to_num(RemoteProvisioningServer.MODEL_ID)
    RemoteProvisioningClient = model_id_to_num(RemoteProvisioningClient.MODEL_ID)
    PrivateBeaconServer = model_id_to_num(PrivateBeaconServer.MODEL_ID)
    PrivateBeaconClient = model_id_to_num(PrivateBeaconClient.MODEL_ID)
    GenericOnOffServer = model_id_to_num(GenericOnOffServer.MODEL_ID)
    GenericDTTServer = model_id_to_num(GenericDTTServer.MODEL_ID)
    GenericLevelServer = model_id_to_num(GenericLevelServer.MODEL_ID)
    GenericPowerOnOffServer = model_id_to_num(GenericPowerOnOffServer.MODEL_ID)
    GenericPowerOnOffSetupServer = model_id_to_num(GenericPowerOnOffSetupServer.MODEL_ID)
    GenericBatteryServer = model_id_to_num(GenericBatteryServer.MODEL_ID)
    SensorServer = model_id_to_num(SensorServer.MODEL_ID),
    SensorSetupServer = model_id_to_num(SensorSetupServer.MODEL_ID),
    SensorClient = model_id_to_num(SensorClient.MODEL_ID),
    LightLightnessServer = model_id_to_num(LightLightnessServer.MODEL_ID)
    LightLightnessSetupServer = model_id_to_num(LightLightnessSetupServer.MODEL_ID)
    LightCTLServer = model_id_to_num(LightCTLServer.MODEL_ID)
    LightCTLSetupServer = model_id_to_num(LightCTLSetupServer.MODEL_ID)
    LightCTLTemperatureServer = model_id_to_num(LightCTLTemperatureServer.MODEL_ID)
    LightHSLServer = model_id_to_num(LightHSLServer.MODEL_ID)
    LightHSLSetupServer = model_id_to_num(LightHSLSetupServer.MODEL_ID)
    LightHSLHueServer = model_id_to_num(LightHSLHueServer.MODEL_ID)
    LightHSLSaturationServer = model_id_to_num(LightHSLSaturationServer.MODEL_ID)
    ThermostatServer = model_id_to_num(ThermostatServer.MODEL_ID)


class BtSensorAttrPropertyId(IntEnumName):
    """ BT Mesh sensor property names. """

    @classmethod
    def get_name(_class, val: int):
        return PropertyID(val).name if val in PropertyID._value2member_map_ else f"{val:04x}"


class BtMeshOpcode:
    """ BT Mesh opcode names. """

    OPCODES: Final = [
        ConfigOpcode,
        HealthOpcode,
        GenericOnOffOpcode,
        GenericLevelOpcode,
        GenericDTTOpcode,
        GenericPowerOnOffOpcode,
        GenericPowerOnOffSetupOpcode,
        GenericBatteryOpcode,
        LightLightnessOpcode,
        LightLightnessSetupOpcode,
        LightCTLOpcode,
        LightCTLSetupOpcode,
        LightHSLOpcode,
        LightHSLSetupOpcode,
        SceneOpcode,
        SensorOpcode,
        SensorSetupOpcode,
        TimeOpcode,
        ThermostatOpcode,
    ]
    _opcodes = {
        key: opcode
        for opcode_class in OPCODES
        for key, opcode in opcode_class._value2member_map_.items()
    }

    @classmethod
    def get(_class, val: int) -> IntEnum:
        return _class._opcodes[val] if val in _class._opcodes else None

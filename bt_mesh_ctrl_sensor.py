#!/opt/homeassistant/bin/python3

import os
import sys
sys.path.append(os.getcwd())

import logging
import asyncio
from contextlib import suppress
from uuid import UUID
import json
import yaml
from docopt import docopt

from bluetooth_mesh.application import Application, Element, Capabilities
from bluetooth_mesh.messages.config import GATTNamespaceDescriptor
from bluetooth_mesh.messages.properties import PropertyID
from bluetooth_mesh.models import ConfigServer, ConfigClient, HealthClient
from bluetooth_mesh.models.generic.onoff import GenericOnOffClient
from bluetooth_mesh.models.generic.ponoff import GenericPowerOnOffClient
from bluetooth_mesh.models.generic.level import GenericLevelClient
from bluetooth_mesh.models.generic.dtt import GenericDTTClient
from bluetooth_mesh.models.generic.battery import GenericBatteryClient
from bluetooth_mesh.models.sensor import SensorClient
from bluetooth_mesh.models.time import TimeClient
from bluetooth_mesh.models.light.lightness import LightLightnessClient
from bluetooth_mesh.models.light.ctl import LightCTLClient
from bluetooth_mesh.models.light.hsl import LightHSLClient
from bluetooth_mesh.models.vendor.thermostat import ThermostatClient
from bluetooth_mesh.models.scene import SceneClient
from bluetooth_mesh.models.time import TimeServer, TimeSetupServer

from bt_mesh.mesh_cfgclient_conf import MeshCfgclientConf
from bt_mesh import BtMeshModelId
from bt_mesh import BtSensorAttrPropertyId
from bt_mesh.publication import Publication
from bt_mesh.cadence import Cadence



G_PATH = "/com/silvair/sample_" + os.environ['USER']
#G_CFGCLIENT_CONFIG_PATH = "/home/homeassistant/.config/meshcfg/config_db.json"
G_CFGCLIENT_CONFIG_PATH = "/home/scg/.config/meshcfg/config_db.json"
G_SENSOR_CONFIG_PATH = "./mesh_sensor_config.yaml"
G_SEND_INTERVAL = 0.5
G_TIMEOUT = 10.0

#PROVISIONER_UUID = "d4a89960-ad5b-4bfd-a943-9d795551534d"
PROVISIONER_UUID = "f7f2ded9-2cb3-454e-975e-a79f4e5830cd"



log = logging.getLogger()



class ProvisionerMainElement(Element):
    LOCATION = GATTNamespaceDescriptor.MAIN
    MODELS = [
        ConfigServer,
        ConfigClient,
    ]

class ProvisionerApplication(Application):
    COMPANY_ID = 0x05f1         # The Linux Foundation
    PRODUCT_ID = 0x0001
    VERSION_ID = 1
    ELEMENTS = {
        0: ProvisionerMainElement,
    }
    CAPABILITIES = [Capabilities.OUT_NUMERIC]
    CRPL = 0x8000
    PATH = "/ru/stdio/ha_mesh_ctrl_provisioner"
    _uuid: UUID

    @property
    def uuid(self) -> UUID:
        return self._uuid

    def __init__(self, loop: asyncio.AbstractEventLoop, uuid: str):
        self._uuid = UUID(uuid)
        super().__init__(loop)

    def dbus_disconnected(self, owner) -> any:
        pass



class ClientMainElement(Element):
    LOCATION = GATTNamespaceDescriptor.MAIN
    MODELS = [
        HealthClient,
        GenericOnOffClient,
        GenericPowerOnOffClient,
        GenericLevelClient,
        GenericDTTClient,
        GenericBatteryClient,
        SensorClient,
        LightLightnessClient,
        LightCTLClient,
        LightHSLClient,
        ThermostatClient,
        SceneClient,
        TimeServer,
        TimeSetupServer
    ]

class ClientApplication(Application):
    COMPANY_ID = 0x05f1         # The Linux Foundation
    PRODUCT_ID = 0x0001
    VERSION_ID = 1
    ELEMENTS = {
        0: ClientMainElement,
    }
    CAPABILITIES = [Capabilities.OUT_NUMERIC]
    CRPL = 0x8000
    PATH = G_PATH

    def dbus_disconnected(self, owner) -> any:
        pass



async def get(loop: asyncio.AbstractEventLoop, unicast_addr: [int | None] = None):
    provisioner = ProvisionerApplication(loop, PROVISIONER_UUID)
    client = ClientApplication(loop)

    from bluetooth_mesh import models

    mesh_conf = MeshCfgclientConf(G_CFGCLIENT_CONFIG_PATH)
    mesh_conf.load()
    elements = mesh_conf.get_models_by_model_id(BtMeshModelId.SensorSetupServer)
    elements.sort(key=lambda e : e.unicast_addr)

    try:
        with open(G_SENSOR_CONFIG_PATH, 'r') as file:
            conf = yaml.safe_load(file)
    except FileNotFoundError as e:
        conf = dict()

    group_publication = {}
    group_cadence = {}
    if "config_group" in conf:
        if "publication" in conf["config_group"]:
            group_publication = conf["config_group"]["publication"]
        if "cadence" in conf["config_group"]:
            group_cadence = conf["config_group"]["cadence"]

    # define element(s)
    if "elements" not in conf:
        conf["elements"] = dict()

    for element in elements:
        device_unicast_addr = element.device.unicast_addr
        device_net_key = element.device.net_keys[0]
        element_unicast_addr = element.unicast_addr
        key = f"0x{element_unicast_addr:04x}"

        if (key in  conf["elements"]):
            continue

        if (not unicast_addr or unicast_addr == element_unicast_addr):
            conf["elements"][key] = {
                "model": element.model_id.name,
                "app_key": element.app_key,
                "device_unicat_addr": f"0x{device_unicast_addr:04x}",
                "net_key": device_net_key,
                "publication": {},
                "cadence": {}
            }

    # get element(s) publication
    async with provisioner:
        await provisioner.connect()
        config_client = provisioner.elements[0][ConfigClient]

        for element in elements:
            device_unicast_addr = element.device.unicast_addr
            device_net_key = element.device.net_keys[0]
            element_unicast_addr = element.unicast_addr
            key = f"0x{element_unicast_addr:04x}"

            if (not unicast_addr or unicast_addr == element_unicast_addr):
                print(f"{key}: load publication...")
                try:
                    status = await config_client.get_publication(
                        device_unicast_addr,
                        device_net_key,
                        element_unicast_addr,
                        models.SensorServer,
                        send_interval=G_SEND_INTERVAL,
                        timeout=G_TIMEOUT
                    )
                    publication = Publication.extract(status)
                    try:
                        group_name = conf["elements"][key]["publication"]["group"]
                    except:
                        group_name = None
                    if not group_name or group_name not in group_publication or publication != group_publication[group_name]:
                        conf["elements"][key]["publication"] = publication
                except TimeoutError as e:
                    publication = {}
                    print(f"0x{element_unicast_addr:04x} - fail: {e}")

    # get element(s) cadence
    async with client:
        await client.connect()
        sensor_client = client.elements[0][SensorClient]

        for element in elements:
            device_unicast_addr = element.device.unicast_addr
            element_unicast_addr = element.unicast_addr
            element_app_key = element.app_key
            key = f"0x{element_unicast_addr:04x}"

            if (not unicast_addr or unicast_addr == element_unicast_addr):
                print(f"{key}: load cadence...")

                cadence = dict()

                try:
                    desc = await sensor_client.descriptor_get(
                        element_unicast_addr,
                        app_index=element_app_key,
                        send_interval=G_SEND_INTERVAL,
                        timeout=G_TIMEOUT
                    )

                    for desc_entity in desc:
                        property_id = desc_entity.sensor_property_id
                        property_name = BtSensorAttrPropertyId.get_name(property_id)

                        status = await sensor_client.cadence_get(
                            element_unicast_addr,
                            app_index=element_app_key,
                            property_id=property_id,
                            send_interval=G_SEND_INTERVAL,
                            timeout=G_TIMEOUT
                        )
                        cadence[property_name] = Cadence.extract(status)
                except TimeoutError as e:
                    cadence = {}
                    print(f"0x{element_unicast_addr:04x} - fail: {e}")
                    pass

                try:
                    group_name = conf["elements"][key]["cadence"]["group"]
                except:
                    group_name = None
                if not group_name or group_name not in group_cadence or cadence != group_cadence[group_name]:
                    conf["elements"][key]["cadence"] = cadence


    with open(G_SENSOR_CONFIG_PATH, 'w') as file:
        yaml.dump(conf, file)



async def set(loop: asyncio.AbstractEventLoop, unicast_addr: [int | None] = None):
    provisioner = ProvisionerApplication(loop, PROVISIONER_UUID)
    client = ClientApplication(loop)

    from bluetooth_mesh import models

    try:
        with open(G_SENSOR_CONFIG_PATH, 'r') as file:
            conf = yaml.safe_load(file)
    except FileNotFoundError as e:
        print(f"Can't load Sensor config {G_SENSOR_CONFIG_PATH}: {e}")
        return

    group_publication = {}
    group_cadence = {}
    if "config_group" in conf:
        if "publication" in conf["config_group"]:
            group_publication = conf["config_group"]["publication"]
        if "cadence" in conf["config_group"]:
            group_cadence = conf["config_group"]["cadence"]

    # store element(s) publication
    async with provisioner:
        await provisioner.connect()
        config_client = provisioner.elements[0][ConfigClient]

        for key in conf["elements"].keys():
            element_unicast_addr = int(key, 16)

            if (not unicast_addr or unicast_addr == element_unicast_addr):
                print(f"{key}: store publication...")
                element = conf["elements"][key]

                try:
                    group_name = element["publication"]["group"]
                except:
                    group_name = None
                if group_name and group_name in group_publication:
                    publication = group_publication[group_name]
                else:
                    publication = element["publication"]

                print(f"publication_address={int(publication['unicast_addr'], 16)}")
                try:
                    status = await config_client.set_publication(
                        destination=int(element["device_unicat_addr"], 16),
                        net_index=element["net_key"],
                        element_address=element_unicast_addr,
                        publication_address=int(publication["unicast_addr"], 16),
                        app_key_index=publication["app_key"],
                        model=models.SensorServer,
                        ttl=publication["ttl"],
                        publish_period=publication["period"],
                        retransmit_count=publication["retransmissions"]["count"],
                        retransmit_interval=publication["retransmissions"]["interval"],
                        send_interval=G_SEND_INTERVAL,
                        timeout=G_TIMEOUT
                    )
                except TimeoutError as e:
                    print(f"0x{element_unicast_addr:04x} - fail: {e}")

                print(f"publication={publication}")
                print(f"status={status}")

    # store element(s) cadence
    async with client:
        await client.connect()
        sensor_client = client.elements[0][SensorClient]

        for key in conf["elements"].keys():
            element_unicast_addr = int(key, 16)

            if (not unicast_addr or unicast_addr == element_unicast_addr):
                print(f"{key}: store cadence...")
                element = conf["elements"][key]

                try:
                    group_name = element["cadence"]["group"]
                except:
                    group_name = None
                if group_name and group_name in group_cadence:
                    cadence = group_cadence[group_name]
                else:
                    cadence = element["cadence"]

#                print(f"cadence={cadence}")
                for property_name in cadence:
                    property_cadence = cadence[property_name];
                    print(f"    {property_name}")
                    print(f"        {cadence[property_name]}")
                    status = await sensor_client.cadence_set(
                        destination=element_unicast_addr,
                        app_index=element["app_key"],
                        sensor_setting_property_id=getattr(PropertyID, property_name),
                        fast_cadence_period_divisor=property_cadence["fast_cadence_period_divisor"],
                        status_trigger_type=(0 if property_cadence["status_trigger_type"] == "unit" else 1),
                        status_trigger_delta_down=property_cadence["status_trigger_delta_down"],
                        status_trigger_delta_up=property_cadence["status_trigger_delta_up"],
                        status_min_interval=property_cadence["status_min_interval"],
                        fast_cadence_low=property_cadence["fast_cadence_low"],
                        fast_cadence_high=property_cadence["fast_cadence_high"],
                        send_interval=G_SEND_INTERVAL,
                        timeout=G_TIMEOUT
                    )
                    print(f"{status}");



async def run(loop: asyncio.AbstractEventLoop):
    doc = """
    Sensor control script

    Usage:
        ha_mesh_ctrl_sensor.py [-a <address>] get
        ha_mesh_ctrl_sensor.py [-a <address>] set
        ha_mesh_ctrl_sensor.py [-h | --help]
        ha_mesh_ctrl_sensor.py --version

    Options:
        -a <address>            Local node unicast address
        -V                      Show verbose messages
        -h --help               Show this screen
        --version               Show version
    """
    arguments = docopt(doc, version='1.0')

    unicast_addr = int(arguments["-a"], 16) if "-a" in arguments and arguments["-a"] is not None else None

    if arguments['get']:
        await get(loop, unicast_addr)
    elif arguments['set']:
        await set(loop, unicast_addr)
    else:
        print(doc)
        exit(-1)


def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    with suppress(KeyboardInterrupt):
        loop.run_until_complete(run(loop))


if __name__ == '__main__':
    main()

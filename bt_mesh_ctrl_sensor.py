#!python3

import os
import sys

import logging
import asyncio
from contextlib import suppress
from docopt import docopt
import yaml

from bluetooth_mesh.application import Application, Element, Capabilities
from bluetooth_mesh.messages.config import GATTNamespaceDescriptor
from bluetooth_mesh.messages.properties import PropertyID
from bluetooth_mesh.models import Model, ConfigServer, ConfigClient
from bluetooth_mesh.models.sensor import SensorClient, SensorServer

from bt_mesh.mesh_provisioner_conf import MeshProvisionerConf
from bt_mesh.mesh_cfgclient_conf import MeshCfgclientConf
from bt_mesh import BtMeshModelId
from bt_mesh import BtSensorAttrPropertyId
from bt_mesh.publication import Publication
from bt_mesh.cadence import Cadence
from bt_mesh.application import MeshCfgclient



log = logging.getLogger()



G_PATH = "/mesh/bt_mesh_ctrl_sensor"
G_CFGCLIENT_CONFIG_PATH = "~/.config/meshcfg/config_db.json"
G_SENSOR_CONFIG_PATH = "./mesh_sensor_config.yaml"
G_SEND_INTERVAL = 0.5
G_TIMEOUT = 10.0



class ClientMainElement(Element):
    LOCATION = GATTNamespaceDescriptor.MAIN
    MODELS = [
        SensorClient,
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

    def display_numeric(self, type: str, number: int):
        print("request key, number: %d" % (number))



async def mesh_join(loop: asyncio.AbstractEventLoop):
    client = ClientApplication(loop)
    async with client:
        print("Join start...")
        client_token = await client.join()
        print("Join complete");

async def mesh_leave(loop: asyncio.AbstractEventLoop):
    client = ClientApplication(loop)
    async with client:
        await client.connect()
        await client.leave()


async def get(loop: asyncio.AbstractEventLoop, unicast_addr: [int | None] = None):
    provisioner_conf = MeshProvisionerConf(G_CFGCLIENT_CONFIG_PATH)
    provisioner = MeshCfgclient(loop, provisioner_conf)
    client = ClientApplication(loop)

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
                        SensorServer,
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
    provisioner_conf = MeshProvisionerConf(G_CFGCLIENT_CONFIG_PATH)
    provisioner = MeshCfgclient(loop, provisioner_conf)
    client = ClientApplication(loop)

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

                try:
                    status = await config_client.set_publication(
                        destination=int(element["device_unicat_addr"], 16),
                        net_index=element["net_key"],
                        element_address=element_unicast_addr,
                        publication_address=int(publication["unicast_addr"], 16),
                        app_key_index=publication["app_key"],
                        model=SensorServer,
                        ttl=publication["ttl"],
                        publish_period=publication["period"],
                        retransmit_count=publication["retransmissions"]["count"],
                        retransmit_interval=publication["retransmissions"]["interval"],
                        send_interval=G_SEND_INTERVAL,
                        timeout=G_TIMEOUT
                    )
                except TimeoutError as e:
                    print(f"0x{element_unicast_addr:04x} - fail: {e}")

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

                for property_name in cadence:
                    property_cadence = cadence[property_name];
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



async def run(loop: asyncio.AbstractEventLoop):
    doc = """
    Sensor control script

    Usage:
        ha_mesh_ctrl_sensor.py [-V] join
        ha_mesh_ctrl_sensor.py [-V] leave
        ha_mesh_ctrl_sensor.py [-V] [-a <address>] get
        ha_mesh_ctrl_sensor.py [-V] [-a <address>] set
        ha_mesh_ctrl_sensor.py [-h | --help]
        ha_mesh_ctrl_sensor.py --version

    Options:
        -a <address>            Local node unicast address
        -V                      Show verbose messages
        -h --help               Show this screen
        --version               Show version
    """
    arguments = docopt(doc, version='1.0')

    if "-V" in arguments and arguments['-V']:
        logging.basicConfig(level=logging.DEBUG)

    unicast_addr = int(arguments["-a"], 16) if "-a" in arguments and arguments["-a"] is not None else None

    if arguments['join']:
        await mesh_join(loop)
    elif arguments['leave']:
        await mesh_leave(loop)
    elif arguments['get']:
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

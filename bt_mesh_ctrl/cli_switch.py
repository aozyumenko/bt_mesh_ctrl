import asyncio
from contextlib import suppress
from docopt import docopt
import yaml
from enum import IntEnum

from bluetooth_mesh.application import Application, Element, Capabilities
from bluetooth_mesh.messages.config import GATTNamespaceDescriptor
from bluetooth_mesh.models import ConfigClient
from bluetooth_mesh.models.generic.onoff import GenericOnOffServer, GenericOnOffClient
from bluetooth_mesh.models.generic.dtt import GenericDTTClient
from bluetooth_mesh.models.generic.ponoff import GenericPowerOnOffClient

from bt_mesh_ctrl import BtMeshModelId
from bt_mesh_ctrl.mesh_provisioner_conf import MeshProvisionerConf
from bt_mesh_ctrl.mesh_cfgclient_conf import MeshCfgclientConf
from bt_mesh_ctrl.publication import Publication
from bt_mesh_ctrl.application import MeshCfgclient

import logging
log = logging.getLogger()


G_PATH = "/mesh/bt_mesh_ctrl"
G_CFGCLIENT_CONFIG_PATH = "~/.config/meshcfg/config_db.json"
G_SWITCH_CONFIG_PATH = "./mesh_switch_config.yaml"
G_SEND_INTERVAL = 1.0
G_TIMEOUT = 10.0


class ClientMainElement(Element):
    LOCATION = GATTNamespaceDescriptor.MAIN
    MODELS = [
        GenericOnOffClient,
        GenericDTTClient,
        GenericPowerOnOffClient,
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
        print("Join complete")


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
    elements = mesh_conf.get_models_by_model_id(BtMeshModelId.GenericOnOffServer)
    dtt_elements = {
        model.unicast_addr: model
        for model in mesh_conf.get_models_by_model_id(
            BtMeshModelId.GenericDTTServer
        )
    }
    elements.sort(key=lambda e: e.unicast_addr)

    try:
        with open(G_SWITCH_CONFIG_PATH, 'r') as file:
            conf = yaml.safe_load(file)
    except FileNotFoundError:
        conf = dict()

    group_publication = {}
    group_dtt = {}
    if "config_group" in conf:
        if "publication" in conf["config_group"]:
            group_publication = conf["config_group"]["publication"]
        if "dtt" in conf["config_group"]:
            group_dtt = conf["config_group"]["dtt"]

    # define element(s)
    if "elements" not in conf:
        conf["elements"] = dict()

    for element in elements:
        device_unicast_addr = element.device.unicast_addr
        device_net_key = element.device.net_keys[0]
        element_unicast_addr = element.unicast_addr
        key = f"0x{element_unicast_addr:04x}"

        if (key in conf["elements"]):
            continue

        if (not unicast_addr or unicast_addr == element_unicast_addr):
            conf["elements"][key] = {
                "model": element.model_id.name,
                "app_key": element.app_key,
                "device_unicat_addr": f"0x{device_unicast_addr:04x}",
                "net_key": device_net_key,
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
                        GenericOnOffServer,
                        send_interval=G_SEND_INTERVAL,
                        timeout=G_TIMEOUT
                    )
                    publication = Publication.extract(status)
                    try:
                        group_name = conf["elements"][key]["server"]["publication"]["group"]
                    except KeyError:
                        group_name = None
                    if not group_name or group_name not in group_publication or publication != group_publication[group_name]:
                        conf["elements"][key]["server"] = {}
                        conf["elements"][key]["server"]["publication"] = publication
                except TimeoutError as e:
                    publication = {}
                    print(f"0x{element_unicast_addr:04x} - fail: {e}")

    # get element(s) DTT
    async with client:
        await client.connect()

        for element in elements:
            device_unicast_addr = element.device.unicast_addr
            element_unicast_addr = element.unicast_addr
            element_app_key = element.app_key
            key = f"0x{element_unicast_addr:04x}"

            if (not unicast_addr or unicast_addr == element_unicast_addr):
                if element_unicast_addr in dtt_elements:
                    print(f"{key}: load DTT...")
                    generic_dtt_client = client.elements[0][GenericDTTClient]

                    transition_time = None

                    try:
                        result = await generic_dtt_client.get(
                            element_unicast_addr,
                            app_index=element_app_key,
                            send_interval=G_SEND_INTERVAL,
                            timeout=G_TIMEOUT
                        )
                        transition_time = result.transition_time

                    except TimeoutError as e:
                        transition_time = None
                        print(f"0x{element_unicast_addr:04x} - fail: {e}")

                    try:
                        group_name = conf["elements"][key]["server"]["dtt"]["group"]
                    except KeyError:
                        group_name = None
                    if (
                        not group_name
                        or group_name not in group_dtt
                        or transition_time != group_dtt[group_name]["transition_time"]
                    ):
                        conf["elements"][key]["server"]["dtt"] = {
                            "transition_time": transition_time
                        }

    with open(G_SWITCH_CONFIG_PATH, 'w') as file:
        yaml.dump(conf, file)


async def set(loop: asyncio.AbstractEventLoop, unicast_addr: [int | None] = None):
    provisioner_conf = MeshProvisionerConf(G_CFGCLIENT_CONFIG_PATH)
    provisioner = MeshCfgclient(loop, provisioner_conf)
    client = ClientApplication(loop)

    try:
        with open(G_SWITCH_CONFIG_PATH, 'r') as file:
            conf = yaml.safe_load(file)
    except FileNotFoundError as e:
        print(f"Can't load Switch config {G_SWITCH_CONFIG_PATH}: {e}")
        return

    group_publication = {}
    group_dtt = {}
    if "config_group" in conf:
        if "publication" in conf["config_group"]:
            group_publication = conf["config_group"]["publication"]
        if "dtt" in conf["config_group"]:
            group_dtt = conf["config_group"]["dtt"]

    # store element(s) publication
    async with provisioner:
        await provisioner.connect()
        config_client = provisioner.elements[0][ConfigClient]

        for key in conf["elements"].keys():
            element = conf["elements"][key]
            element_unicast_addr = int(key, 16)

            if (not unicast_addr or unicast_addr == element_unicast_addr) and "server" in element:
                print(f"{key}: store publication...")

                try:
                    group_name = element["server"]["publication"]["group"]
                except KeyError:
                    group_name = None
                if group_name and group_name in group_publication:
                    publication = group_publication[group_name]
                else:
                    publication = element["server"]["publication"]

                try:
                    await config_client.set_publication(
                        destination=int(element["device_unicat_addr"], 16),
                        net_index=element["net_key"],
                        element_address=element_unicast_addr,
                        publication_address=int(publication["unicast_addr"], 16),
                        app_key_index=publication["app_key"],
                        model=GenericOnOffServer,
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

        for key in conf["elements"].keys():
            element_unicast_addr = int(key, 16)
            element = conf["elements"][key]

            if (not unicast_addr or unicast_addr == element_unicast_addr) and "server" in element:
                if "dtt" in element["server"]:
                    print(f"{key}: store DTT...")
                    generic_dtt_client = client.elements[0][GenericDTTClient]

                    try:
                        group_name = element["server"]["dtt"]["group"]
                    except KeyError:
                        group_name = None

                    if group_name and group_name in group_dtt:
                        transition_time = group_dtt[group_name]["transition_time"]
                    else:
                        transition_time = element["server"]["dtt"]["transition_time"]

                    try:
                        await generic_dtt_client.set(
                            destination=element_unicast_addr,
                            app_index=element["app_key"],
                            transition_time=transition_time,
                            send_interval=G_SEND_INTERVAL,
                            timeout=G_TIMEOUT
                        )
                    except TimeoutError as e:
                        print(f"0x{element_unicast_addr:04x} - fail: {e}")


async def run(loop: asyncio.AbstractEventLoop):
    doc = """
    Switch control script

    Usage:
        bt_mesh_ctrl_switch [-V] join
        bt_mesh_ctrl_switch [-V] leave
        bt_mesh_ctrl_switch [-V] [-a <address>] get
        bt_mesh_ctrl_switch [-V] [-a <address>] set
        bt_mesh_ctrl_switch [-h | --help]
        bt_mesh_ctrl_switch --version

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


def cli():
    yaml.add_multi_representer(IntEnum, lambda dumper, data: dumper.represent_int(data.value))
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    with suppress(KeyboardInterrupt):
        loop.run_until_complete(run(loop))


if __name__ == '__main__':
    cli()

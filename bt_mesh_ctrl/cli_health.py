import asyncio
from contextlib import suppress
from docopt import docopt
import yaml
from enum import IntEnum

from bluetooth_mesh.application import Application, Element, Capabilities
from bluetooth_mesh.messages.config import GATTNamespaceDescriptor
from bluetooth_mesh.models import ConfigClient, HealthServer, HealthClient

from bt_mesh_ctrl import BtMeshModelId
from bt_mesh_ctrl.mesh_provisioner_conf import MeshProvisionerConf
from bt_mesh_ctrl.mesh_cfgclient_conf import MeshCfgclientConf
from bt_mesh_ctrl.publication import Publication
from bt_mesh_ctrl.application import MeshCfgclient

import logging
log = logging.getLogger()


G_PATH = "/mesh/bt_mesh_ctrl"
G_CFGCLIENT_CONFIG_PATH = "~/.config/meshcfg/config_db.json"
G_HEALTH_CONFIG_PATH = "./mesh_health_config.yaml"
G_SEND_INTERVAL = 0.5
G_TIMEOUT = 10.0


class ClientMainElement(Element):
    LOCATION = GATTNamespaceDescriptor.MAIN
    MODELS = [
        HealthClient,
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
    elements = mesh_conf.get_models_by_model_id(BtMeshModelId.HealthServer)
    elements.sort(key=lambda e: e.unicast_addr)

    try:
        with open(G_HEALTH_CONFIG_PATH, 'r') as file:
            conf = yaml.safe_load(file)
    except FileNotFoundError:
        conf = dict()

    group_publication = {}
    group_health = {}
    if "config_group" in conf:
        if "publication" in conf["config_group"]:
            group_publication = conf["config_group"]["publication"]
        if "health" in conf["config_group"]:
            group_health = conf["config_group"]["health"]

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
                "publication": {},
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
                        HealthServer,
                        send_interval=G_SEND_INTERVAL,
                        timeout=G_TIMEOUT
                    )
                    publication = Publication.extract(status)
                    try:
                        group_name = conf["elements"][key]["publication"]["group"]
                    except KeyError:
                        group_name = None
                    if not group_name or group_name not in group_publication or publication != group_publication[group_name]:
                        conf["elements"][key]["publication"] = publication
                except TimeoutError as e:
                    publication = {}
                    print(f"0x{element_unicast_addr:04x} - fail: {e}")

    # get element(s) health
    async with client:
        await client.connect()
        health_client = client.elements[0][HealthClient]

        for element in elements:
            device_unicast_addr = element.device.unicast_addr
            element_unicast_addr = element.unicast_addr
            element_app_key = element.app_key
            key = f"0x{element_unicast_addr:04x}"

            if (not unicast_addr or unicast_addr == element_unicast_addr):
                print(f"{key}: load health...")

                health = dict()

                try:
                    status = await health_client.period_get(
                        element_unicast_addr,
                        app_index=element_app_key,
                        send_interval=G_SEND_INTERVAL,
                        timeout=G_TIMEOUT
                    )
                    health['fast_period_divisor'] = status.fast_period_divisor
                except TimeoutError as e:
                    health = {}
                    print(f"0x{element_unicast_addr:04x} - fail: {e}")
                    pass

                try:
                    group_name = conf["elements"][key]["health"]["group"]
                except KeyError:
                    group_name = None
                if not group_name or group_name not in group_health or health != group_health[group_name]:
                    conf["elements"][key]["health"] = health

    with open(G_HEALTH_CONFIG_PATH, 'w') as file:
        yaml.dump(conf, file)


async def set(loop: asyncio.AbstractEventLoop, unicast_addr: [int | None] = None):
    provisioner_conf = MeshProvisionerConf(G_CFGCLIENT_CONFIG_PATH)
    provisioner = MeshCfgclient(loop, provisioner_conf)
    client = ClientApplication(loop)

    try:
        with open(G_HEALTH_CONFIG_PATH, 'r') as file:
            conf = yaml.safe_load(file)
    except FileNotFoundError as e:
        print(f"Can't load Health config {G_HEALTH_CONFIG_PATH}: {e}")
        return

    group_publication = {}
    group_health = {}
    if "config_group" in conf:
        if "publication" in conf["config_group"]:
            group_publication = conf["config_group"]["publication"]
        if "health" in conf["config_group"]:
            group_health = conf["config_group"]["health"]

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
                except KeyError:
                    group_name = None
                if group_name and group_name in group_publication:
                    publication = group_publication[group_name]
                else:
                    publication = element["publication"]

                if publication:
                    try:
                        await config_client.set_publication(
                            destination=int(element["device_unicat_addr"], 16),
                            net_index=element["net_key"],
                            element_address=element_unicast_addr,
                            publication_address=int(publication["unicast_addr"], 16),
                            app_key_index=publication["app_key"],
                            model=HealthServer,
                            ttl=publication["ttl"],
                            publish_period=publication["period"],
                            retransmit_count=publication["retransmissions"]["count"],
                            retransmit_interval=publication["retransmissions"]["interval"],
                            send_interval=G_SEND_INTERVAL,
                            timeout=G_TIMEOUT
                        )
                    except TimeoutError as e:
                        print(f"0x{element_unicast_addr:04x} - fail: {e}")

    # store element(s) health
    async with client:
        await client.connect()
        health_client = client.elements[0][HealthClient]

        for key in conf["elements"].keys():
            element_unicast_addr = int(key, 16)

            if (not unicast_addr or unicast_addr == element_unicast_addr):
                print(f"{key}: store health...")
                element = conf["elements"][key]

                try:
                    group_name = element["health"]["group"]
                except KeyError:
                    group_name = None
                if group_name and group_name in group_health:
                    health = group_health[group_name]
                else:
                    health = element["health"]

                if "fast_period_divisor" in health:
                    await health_client.period_set(
                        destination=element_unicast_addr,
                        app_index=element["app_key"],
                        fast_period_divisor=health["fast_period_divisor"],
                        send_interval=G_SEND_INTERVAL,
                        timeout=G_TIMEOUT
                    )


async def run(loop: asyncio.AbstractEventLoop):
    doc = """
    Health control script

    Usage:
        bt_mesh_ctrl_health [-V] join
        bt_mesh_ctrl_health [-V] leave
        bt_mesh_ctrl_health [-V] [-a <address>] get
        bt_mesh_ctrl_health [-V] [-a <address>] set
        bt_mesh_ctrl_health [-h | --help]
        bt_mesh_ctrl_health --version

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

    # TODO: add commands: fault_log, fault_clear


def cli():
    yaml.add_multi_representer(IntEnum, lambda dumper, data: dumper.represent_int(data.value))
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    with suppress(KeyboardInterrupt):
        loop.run_until_complete(run(loop))


if __name__ == '__main__':
    cli()

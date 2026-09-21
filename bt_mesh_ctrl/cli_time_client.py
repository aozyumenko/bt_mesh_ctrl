#!python3

import logging
import asyncio
from contextlib import suppress
from docopt import docopt
import yaml

from bluetooth_mesh.models import ConfigClient
from bluetooth_mesh.models.time import TimeClient

from bt_mesh_ctrl.mesh_provisioner_conf import MeshProvisionerConf
from bt_mesh_ctrl.mesh_cfgclient_conf import MeshCfgclientConf
from bt_mesh_ctrl import BtMeshModelId
from bt_mesh_ctrl.publication import Publication
from bt_mesh_ctrl.application import MeshCfgclient


log = logging.getLogger()


G_CFGCLIENT_CONFIG_PATH = "~/.config/meshcfg/config_db.json"
G_TIME_CLIENT_CLIENT_CONFIG_PATH = "./mesh_time_client_config.yaml"
G_SEND_INTERVAL = 0.5
G_TIMEOUT = 20.0


async def get(loop: asyncio.AbstractEventLoop, unicast_addr: [int | None] = None):
    provisioner_conf = MeshProvisionerConf(G_CFGCLIENT_CONFIG_PATH)
    provisioner = MeshCfgclient(loop, provisioner_conf)

    mesh_conf = MeshCfgclientConf(G_CFGCLIENT_CONFIG_PATH)
    mesh_conf.load()
    elements = mesh_conf.get_models_by_model_id(BtMeshModelId.TimeClient)
    elements.sort(key=lambda e: e.unicast_addr)

    try:
        with open(G_TIME_CLIENT_CONFIG_PATH, 'r') as file:
            conf = yaml.safe_load(file)
    except FileNotFoundError:
        conf = dict()

    group_publication = {}
    if "config_group" in conf:
        if "publication" in conf["config_group"]:
            group_publication = conf["config_group"]["publication"]

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
                        TimeClient,
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

    with open(G_TIME_CLIENT_CONFIG_PATH, 'w') as file:
        yaml.dump(conf, file)


async def set(loop: asyncio.AbstractEventLoop, unicast_addr: [int | None] = None):
    provisioner_conf = MeshProvisionerConf(G_CFGCLIENT_CONFIG_PATH)
    provisioner = MeshCfgclient(loop, provisioner_conf)

    try:
        with open(G_TIME_CLIENT_CONFIG_PATH, 'r') as file:
            conf = yaml.safe_load(file)
    except FileNotFoundError as e:
        print(f"Can't load Sensor config {G_TIME_CLIENT_CONFIG_PATH}: {e}")
        return

    group_publication = {}
    if "config_group" in conf:
        if "publication" in conf["config_group"]:
            group_publication = conf["config_group"]["publication"]

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

                try:
                    await config_client.set_publication(
                        destination=int(element["device_unicat_addr"], 16),
                        net_index=element["net_key"],
                        element_address=element_unicast_addr,
                        publication_address=int(publication["unicast_addr"], 16),
                        app_key_index=publication["app_key"],
                        model=TimeClient,
                        ttl=publication["ttl"],
                        publish_period=publication["period"],
                        retransmit_count=publication["retransmissions"]["count"],
                        retransmit_interval=publication["retransmissions"]["interval"],
                        send_interval=G_SEND_INTERVAL,
                        timeout=G_TIMEOUT
                    )
                except TimeoutError as e:
                    print(f"0x{element_unicast_addr:04x} - fail: {e}")


async def run(loop: asyncio.AbstractEventLoop):
    doc = """
    Time client control script

    Usage:
        cli_time_client.py [-V] [-a <address>] get
        cli_time_client.py [-V] [-a <address>] set
        cli_time_client.py [-h | --help]
        cli_time_client.py --version

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

    if arguments['get']:
        await get(loop, unicast_addr)
    elif arguments['set']:
        await set(loop, unicast_addr)
    else:
        print(doc)
        exit(-1)


def cli():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    with suppress(KeyboardInterrupt):
        loop.run_until_complete(run(loop))


if __name__ == '__main__':
    cli()

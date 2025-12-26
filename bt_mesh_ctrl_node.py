#!/opt/homeassistant/bin/python3


import os
import logging
import asyncio
#import secrets
from contextlib import suppress
#from uuid import UUID
import json
#from typing import (Union)

#from docopt import docopt

#from bluetooth_mesh.utils import ParsedMeshMessage
from bluetooth_mesh.application import Application, Element, Capabilities
#from bluetooth_mesh.crypto import ApplicationKey, DeviceKey, NetworkKey
from bluetooth_mesh.messages.config import GATTNamespaceDescriptor#, StatusCode
#from bluetooth_mesh.messages.generic.onoff import GenericOnOffOpcode
from bluetooth_mesh.models import ConfigClient, HealthClient
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



G_PATH = "/com/silvair/sample_" + os.environ['USER']


log = logging.getLogger()



class MainElement(Element):
    LOCATION = GATTNamespaceDescriptor.MAIN
    MODELS = [
        ConfigClient,
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


class SampleApplication(Application):
    COMPANY_ID = 0x0136  # Silvair
    PRODUCT_ID = 0x0001
    VERSION_ID = 1
    ELEMENTS = {
        0: MainElement,
    }
    CAPABILITIES = [Capabilities.OUT_NUMERIC]

    CRPL = 32768
    PATH = G_PATH


    async def run(self):
        async with self:
            await self.connect()

            client = self.elements[0][ConfigClient]
            client(



def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    app = SampleApplication(loop)

    with suppress(KeyboardInterrupt):
        loop.run_until_complete(app.run())

    pass


if __name__ == '__main__':
    main()

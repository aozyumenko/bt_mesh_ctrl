"""BT Mesh application helpers"""
from __future__ import annotations

import asyncio
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Mapping,
    Optional,
    Tuple,
)
from uuid import UUID

from bluetooth_mesh import models as bluetooth_mesh_models
from bluetooth_mesh.application import Application, Element

from bt_mesh_ctrl import BtMeshModelId
from bt_mesh_ctrl.mesh_provisioner_conf import MeshProvisionerConf

import logging
_LOGGER = logging.getLogger(__name__)


__all__ = (
    "G_PROVISIONER_PATH",
    "SimpleTokenRing",
    "MeshCfgclient",
)


G_PROVISIONER_PATH = "/mesh/cfgclient"


class SimpleTokenRing:
    """
    Override the bluetooth_mesh.tokenring.TokenRing
    to detach from the token's disk storage.

    Using this class we can set the token ourselves when
    creating an application object.
    """

    def __init__(self, uuid):
        self.uuid = str(uuid)
        self.data = dict(token=0, acl={}, network={})

    @property
    def token(self):
        return self.data["token"]

    @token.setter
    def token(self, value):
        self.data["token"] = value

    def acl(self, uuid=None, token=None):
        if all((uuid, token)):
            self.data["acl"][uuid] = token
            return

        return self.data["acl"].get(uuid) if uuid else self.data["acl"].items()

    def drop_acl(self, uuid):
        del self.data["acl"][uuid]


class MeshCfgclient(Application):
    """
    Application for configuring mesh network nodes.

    The application connects to the dBus using mesh-cfglicent settings,
    which it takes from the ~/.config/meshcfg/config_db.json node database.
    """

    PATH = G_PROVISIONER_PATH

    _uuid: str
    _token_ring: SimpleTokenRing

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        provisioner_conf: MeshProvisionerConf
    ):
        provisioner = provisioner_conf.get_provisioner(0)

        self.COMPANY_ID = provisioner.cid
        self.PRODUCT_ID = provisioner.pid
        self.VERSION_ID = provisioner.vid
        self.CRPL = provisioner.crpl
        self.ELEMENTS = {}
        for element in provisioner.elements:
            models = [
                getattr(bluetooth_mesh_models, BtMeshModelId.get_name(x))
                for x in element.models
            ]
            self.ELEMENTS[element.index] = type(
                'ProvisionerMainElement',
                (Element, object),
                {
                    "LOCATION": element.location,
                    "MODELS": models
                }
            )
        self._token_ring = SimpleTokenRing(uuid=provisioner.uuid)

        self.token_ring.token = provisioner_conf.token

        super().__init__(loop)

    async def connect_wait(
        self,
        timeout: int,
        join_callback: Optional[Callable[[int], Awaitable[int]]] = None,
        **kwargs,
    ) -> Mapping[int, Dict[Tuple[int, int], Dict[str, Tuple[Any, int]]]]:
        for i in range(20):
            try:
                return await self.connect(join_callback, **kwargs)
            except NotImplementedError:
                pass
            await asyncio.sleep(1)
        raise NotImplementedError("Getting primary network key should be overridden!")

    # replace parent Application class members
    def get_namespace(self):
        return UUID(self._uuid)

    @property
    def token_ring(self) -> SimpleTokenRing:
        return self._token_ring

    def dbus_disconnected(self, owner) -> any:
        pass

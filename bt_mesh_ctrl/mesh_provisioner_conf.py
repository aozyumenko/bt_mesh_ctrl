"""mesh_cfgclient provisioner configuration file reader"""
from __future__ import annotations

import os.path
from pathlib import Path
import json
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from bluetooth_mesh.messages.config import GATTNamespaceDescriptor

from bt_mesh_ctrl import BtMeshModelId

import logging
_LOGGER = logging.getLogger(__name__)


__all__ = (
    "MeshProvisionerConf"
)


JSON_TOKEN: Final = "token"
JSON_PROVISIONERS: Final = "provisioners"
JSON_NODES: Final = "nodes"
JSON_UUID: Final = "UUID"
JSON_UNICAST_ADDRESS: Final = "unicastAddress"
JSON_ELEMENTS: Final = "elements"
JSON_CID: Final = "cid"
JSON_PID: Final = "pid"
JSON_VID: Final = "vid"
JSON_CRPL: Final = "crpl"
JSON_NET_KEYS: Final = "netKeys"
JSON_APP_KEYS: Final = "appKeys"
JSON_INDEX: Final = "index"
JSON_UPDATED: Final = "updated"
JSON_MODELS: Final = "models"
JSON_MODEL_ID: Final = "modelId"
JSON_LOCATION: Final = "location"


@dataclass
class MeshProvisionerElement:
    index: int
    models: list[BtMeshModelId]
    location: GATTNamespaceDescriptor


@dataclass
class MeshProvisioner:
    uuid: UUID
    cid: int
    pid: int
    vid: int
    crpl: int
    elements: list[MeshProvisionerElement]


class MeshProvisionerConf:
    _token: [int | None]
    _provisioners: list[MeshProvisioner]
    _nodes_unicast_addr: dict[str: int]
    _appkeys: list[int]

    def _parse(self, data):
        # get all allowing for network AppKeys
        self._appkeys = [
            appkey[JSON_INDEX] for appkey in data.get(JSON_APP_KEYS, ())
        ]

        # get provisioners
        provisioners = [
            provisioner[JSON_UUID]
            for provisioner in data.get(JSON_PROVISIONERS, ())
        ]

        # enumerate nodes and search provisioners
        for node in data.get(JSON_NODES, ()):
            try:
                node_uuid = node[JSON_UUID]
                node_unicast_addr = int(node[JSON_UNICAST_ADDRESS], 16)

                self._nodes_unicast_addr[node_uuid] = node_unicast_addr

                node_net_keys = [
                    int(net_key[JSON_INDEX])
                    for net_key in node[JSON_NET_KEYS]
                    if not net_key[JSON_UPDATED]
                ]
                node_elements = node[JSON_ELEMENTS]
                node_cid = int(node[JSON_CID], 16)
                node_pid = int(node[JSON_PID], 16)
                node_vid = int(node[JSON_VID], 16)
                node_crpl = int(node[JSON_CRPL], 16)
            except Exception:
                continue

            if node_uuid not in provisioners:
                continue

            # get elements of provisioner node
            provisioner_elements = []
            for element in node_elements:
                try:
                    element_index = int(element[JSON_INDEX])
                    element_location = int(element[JSON_LOCATION], 16)
                    element_models = element[JSON_MODELS]
                except Exception:
                    continue

                # get element's models
                provisioner_element_models = []
                for model in element_models:
                    try:
                        model_id = int(model[JSON_MODEL_ID], 16)
                    except Exception:
                        continue
                    provisioner_element_models.append(
                        BtMeshModelId(model_id)
                    )

                provisioner_element = MeshProvisionerElement(
                    index=element_index,
                    location=GATTNamespaceDescriptor(element_location),
                    models=provisioner_element_models
                )
                provisioner_elements.insert(element_index, provisioner_element)

        provisioner = MeshProvisioner(
            uuid=node_uuid,
            node_net_keys=node_net_keys,
            cid=node_cid,
            pid=node_pid,
            vid=node_vid,
            crpl=node_crpl,
            elements=provisioner_elements
        )

        self._provisioners.append(provisioner)

    def __init__(self, filename: str):
        self.filename: str = os.path.expanduser(filename)
        self._token = None
        self._provisioners = []
        self._nodes_unicast_addr = {}
        self._appkeys = ()
        self.load()

    def load(self) -> dict:
        conf_file = Path(self.filename)
        conf_data = json.loads(conf_file.read_text(encoding="utf8"))

        t = conf_data.get(JSON_TOKEN, None)
        self._token = int(t, 16) if t is not None else None

        self._parse(conf_data)

    @property
    def token(self) -> int:
        return self._token

    def get_provisioners_num(self) -> int:
        return len(self._provisioners)

    def get_provisioner(self, idx: int) -> MeshProvisioner:
        return self._provisioners[idx]

    def get_node_unicast_addr(self, uuid: str):
        return self._nodes_unicast_addr[uuid]

    def get_appkeys(self):
        return self._appkeys

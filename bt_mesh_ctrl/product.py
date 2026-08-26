"""Module with known BT Mesh device IDs."""
from __future__ import annotations

from typing import Tuple, Dict
from bluetooth_numbers.exceptions import (
    BluetoothNumbersError,
    No16BitIntegerError,
)
from bluetooth_numbers.utils import is_uint16

__all__ = ["product"]


class UnknownPIDError(BluetoothNumbersError):
    """Exception raised when a PID is not known."""


class PIDDict(Dict[Tuple[int, int], str]):
    def __missing__(self, key: Tuple[int, int]) -> str:
        """Try the key and raise exception when it's invalid.

        Args:
            key (int, int): The key to check.

        Raises:
            No16BitIntegerError: If ``key`` isn't a tuple of 16-bit unsigned integer.
            UnknownPIDError: If ``key`` isn't in this PIDDict instance.
        """
        if is_uint16(key[0]) and is_uint16(key[1]):
            raise UnknownPIDError(key)

        raise No16BitIntegerError(key)


product = PIDDict(
    {  # 16-bit Product IDs
        (0x0059, 0x5301): "SCG Mesh Wall Switch 1",
        (0x0059, 0x5302): "SCG Mesh Wall Switch 2",
        (0x0059, 0x5303): "SCG Mesh Wall Switch 3",
        (0x0059, 0x5304): "SCG Mesh Wall Plug",
        (0x0059, 0x5305): "SCG RGBWC LED Light Model 1",
        (0x0059, 0x5306): "SCG RGBW LED Light Model 1",
        (0x0059, 0x5307): "Smart Meter HIKING DDS328-2",
        (0x0059, 0x5308): "Thermostat K5H16A-wifi",
        (0x0059, 0x5309): "SCG Mesh Wall Plug PM",
        (0x0059, 0x530a): "Temperatute & Humidity Sensor TH01",
        (0x0059, 0x530b): "SCG Screen Controller",
        (0x0059, 0x530c): "Radiator Thermostat BRT-100",
        (0x0059, 0x530d): "SCG Scene Switch - 4 buttons",
        (0x0059, 0x530e): "Temperatute & Humidity Sensor TH11",
        (0x0059, 0x530f): "PIR Motion Sensor P01",
        (0x0059, 0x5310): "PJ-1103 Electricity Energy Monitor",
        (0x0059, 0x5311): "SCG Plumbing Controller",
    }
)

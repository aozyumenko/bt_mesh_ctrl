"""Cadnce storage class"""
from __future__ import annotations

from construct import Container


__all__ = (
    "Cadence",
)



class Cadence:
    @classmethod
    def unpack_property(_class, prop: Container) -> dict():
        result = dict()
        for key in prop.keys():
            value = prop[key]
            if isinstance(value, dict):
                result[key] = _class.unpack_property(value)
            else:
                result[key] = value
        return result

    @classmethod
    def extract(_class, status: Container) -> dict():
        try:
            cadence = dict()
            cadence["fast_cadence_period_divisor"] = status.fast_cadence_period_divisor
            if status.status_trigger_type == 0:
                cadence["status_trigger_type"] = "unit"
                cadence["status_trigger_delta_down"] = _class.unpack_property(status.status_trigger_delta_down)
                cadence["status_trigger_delta_up"] = _class.unpack_property(status.status_trigger_delta_up)
            else:
                cadence["status_trigger_type"] = "percent"
                cadence["status_trigger_delta_down"] = status.status_trigger_delta_down
                cadence["status_trigger_delta_up"] = status.status_trigger_delta_up
            cadence["status_min_interval"] = status.status_min_interval
            cadence["fast_cadence_low"] = _class.unpack_property(status.fast_cadence_low)
            cadence["fast_cadence_high"] = _class.unpack_property(status.fast_cadence_high)
            return cadence
        except AttributeError as e:
            return {}

    @classmethod
    def build(_class, cadence: dict()) -> Container:
        pass

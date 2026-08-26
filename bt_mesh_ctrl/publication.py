"""Publication storage class"""
from __future__ import annotations


from construct import Container


__all__ = (
    "Publication",
)


class Publication:
    @classmethod
    def extract(_class, status: Container) -> dict():
        publication = {
            "unicast_addr": f"0x{status.publication_address:04x}",
            "app_key": status.app_key_index,
            "ttl": status.ttl,
            "period": status.period,
            "retransmissions": {
                "count": status.retransmissions["count"],
                "interval": status.retransmissions["interval"]
            }
        }
        return publication

"""Publication storage class"""
from __future__ import annotations


__all__ = (
    "Publication",
)


class Publication:
    @classmethod
    def extract(_class, status: Container) -> dict():
#        try:
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
#        except AttributeError as e:
#            return {}

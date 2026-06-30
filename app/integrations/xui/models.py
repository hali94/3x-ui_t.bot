from dataclasses import dataclass, field
from typing import Any


@dataclass
class XUIClientSettings:
    id: str
    email: str
    flow: str = ""
    limit_ip: int = 0
    total_gb: int = 0          # bytes — 0 means unlimited
    expire_time: int = 0       # unix ms — 0 means unlimited
    enable: bool = True
    tg_id: str = ""
    sub_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "email": self.email,
            "flow": self.flow,
            "limitIp": self.limit_ip,
            "totalGB": self.total_gb,
            "expiryTime": self.expire_time,
            "enable": self.enable,
            "tgId": self.tg_id,
            "subId": self.sub_id,
        }


@dataclass
class XUIClientTraffic:
    id: int
    inbound_id: int
    enable: bool
    email: str
    up: int
    down: int
    total: int
    expiry_time: int

    @property
    def used_bytes(self) -> int:
        return self.up + self.down

    @property
    def used_gb(self) -> float:
        return self.used_bytes / (1024 ** 3)

    @classmethod
    def from_dict(cls, data: dict) -> "XUIClientTraffic":
        return cls(
            id=data.get("id", 0),
            inbound_id=data.get("inboundId", 0),
            enable=data.get("enable", True),
            email=data.get("email", ""),
            up=data.get("up", 0),
            down=data.get("down", 0),
            total=data.get("total", 0),
            expiry_time=data.get("expiryTime", 0),
        )


@dataclass
class XUIInbound:
    id: int
    user_id: int
    up: int
    down: int
    total: int
    remark: str
    enable: bool
    expiry_time: int
    protocol: str
    port: int
    tag: str
    clients: list[dict] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "XUIInbound":
        return cls(
            id=data.get("id", 0),
            user_id=data.get("userId", 0),
            up=data.get("up", 0),
            down=data.get("down", 0),
            total=data.get("total", 0),
            remark=data.get("remark", ""),
            enable=data.get("enable", True),
            expiry_time=data.get("expiryTime", 0),
            protocol=data.get("protocol", ""),
            port=data.get("port", 0),
            tag=data.get("tag", ""),
            clients=data.get("clientStats", []),
        )

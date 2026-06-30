import uuid
import shortuuid
from datetime import datetime, timedelta, timezone


def generate_uuid() -> str:
    return str(uuid.uuid4())


def generate_email(reseller_id: int) -> str:
    """Generate a unique client email for 3x-ui."""
    uid = shortuuid.uuid()[:8].lower()
    return f"r{reseller_id}_{uid}@vpn.local"


def expiry_timestamp_ms(days: int) -> int:
    """Return Unix timestamp in milliseconds for 3x-ui expiry field."""
    dt = datetime.now(timezone.utc) + timedelta(days=days)
    return int(dt.timestamp() * 1000)


def gb_to_bytes(gb: float) -> int:
    return int(gb * 1024 ** 3)


def bytes_to_gb(b: int) -> float:
    return b / (1024 ** 3)


def format_expire_date(dt: datetime) -> str:
    """Return a Persian-friendly date string."""
    delta = dt - datetime.now(timezone.utc)
    days = delta.days
    if days < 0:
        return "منقضی شده"
    return f"{days} روز دیگر"

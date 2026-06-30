from typing import Any
from app.models.audit_log import AuditLog
from app.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    model = AuditLog

    async def log(
        self,
        action: str,
        user_id: int | None = None,
        ip: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> AuditLog:
        entry = AuditLog(user_id=user_id, action=action, ip=ip, data=data)
        return await self.create(entry)

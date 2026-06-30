"""
One-time script: promote a Telegram user to ADMIN role.

Usage:
    python scripts/create_admin.py <telegram_id> <full_name>
"""

import asyncio
import sys


async def main(telegram_id: int, full_name: str) -> None:
    from app.database import async_session_factory, init_db
    from app.models.user import UserRole, UserStatus
    from app.repositories.user import UserRepository

    await init_db()

    async with async_session_factory() as session:
        repo = UserRepository(session)
        user = await repo.create_or_update(telegram_id, None, full_name)
        user.role = UserRole.ADMIN
        user.status = UserStatus.ACTIVE
        await session.commit()
        print(f"✅ Admin created: id={user.id} telegram_id={user.telegram_id} name={user.full_name}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python scripts/create_admin.py <telegram_id> <full_name>")
        sys.exit(1)
    asyncio.run(main(int(sys.argv[1]), " ".join(sys.argv[2:])))

from typing import Any, Generic, TypeVar
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, id: int) -> ModelT | None:
        return await self.session.get(self.model, id)

    async def get_all(self, limit: int = 100, offset: int = 0) -> list[ModelT]:
        result = await self.session.execute(
            select(self.model).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def create(self, obj: ModelT) -> ModelT:
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def delete(self, id: int) -> bool:
        result = await self.session.execute(delete(self.model).where(self.model.id == id))
        return result.rowcount > 0

    async def count(self) -> int:
        result = await self.session.execute(select(self.model))
        return len(result.scalars().all())

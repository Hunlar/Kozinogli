from aiogram import BaseMiddleware
from aiogram.types import Message
from db.database import AsyncSessionLocal
from db.models import User
from sqlalchemy import select

class BlockCheckMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Message, data):
        async with AsyncSessionLocal() as session:
            user = await session.execute(
                select(User).where(User.tg_id == event.from_user.id)
            )
            user = user.scalar()
            if user and user.is_blocked:
                await event.answer("🚫 Вы заблокированы!")
                return
        return await handler(event, data)
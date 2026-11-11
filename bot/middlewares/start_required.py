
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select

from db.database import AsyncSessionLocal
from db.models import User


class StartRequiredMiddleware(BaseMiddleware):

    async def __call__(self, handler, event, data):

        telegram_user = getattr(event, "from_user", None)

        if telegram_user is None:
            return await handler(event, data)

        chat_type = None

        if isinstance(event, Message):
            chat_type = event.chat.type

        elif isinstance(event, CallbackQuery):
            if event.message:
                chat_type = event.message.chat.type

        # Özel sohbetlerde bu kontrol uygulanmaz.
        if chat_type not in ("group", "supergroup"):
            return await handler(event, data)

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User.has_started).where(
                    User.tg_id == telegram_user.id
                )
            )

            has_started = result.scalar_one_or_none()

        # Bota özelden /start vermeyen kullanıcı sessizce yok sayılır.
        if has_started is not True:
            return

        return await handler(event, data)

# bot/handlers/profile.py
from aiogram import Router, F
from aiogram.types import Message
from db.database import AsyncSessionLocal
from db.models import User
from datetime import datetime
from sqlalchemy import select
from aiogram import Router, F
from bot.keyboards import main_menu, admin_menu, games_menu, back_button
router = Router()


@router.message(F.text == "Профиль")
async def show_profile(message: Message):
    user_id = message.from_user.id
    async with AsyncSessionLocal() as session:
        user = await session.execute(
            select(User).where(User.tg_id == user_id)
        )
        user = user.scalar()

        if not user:
            await message.answer("Вы не зарегистированы!", reply_markup=back_button())
            return

        days_left = (user.subscription_end - datetime.now()).days if user.subscription_end else 0

        text = (
            f"📝 Профиль:\n"
            f"👤 Логин: {user.login}\n"
            f"🔒 Пароль: <tg-spoiler>{user.password}</tg-spoiler>\n"
            f"💰 Баланс: {user.balance} ₽\n"
            f"📅 Осталось дней подписки: {days_left}\n\n"
            '🔗 <a href="https://t.me/autobattIe">Наш канал</a>\n'
            '💬 <a href="https://t.me/+ZGP8OUDA3iJmOTMy">Наш чат</a>'
        )

        await message.answer(text,
                             parse_mode="HTML",  # Важно!
                             reply_markup=back_button())
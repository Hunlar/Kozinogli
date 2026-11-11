
from aiogram import Router, F
from aiogram.types import Message

from sqlalchemy import select

from db.database import AsyncSessionLocal
from db.models import User
from bot.keyboards import profile_menu

router = Router()


@router.message(F.text == "Profil")
async def show_profile(message: Message):
    telegram_id = message.from_user.id

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.tg_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if user is None:
            await message.answer(
                "Kullanıcı kaydınız bulunamadı. /start komutunu kullanın."
            )
            return

        balance = user.balance or 0

        text = (
            "👤 **Kullanıcı Profili**\n\n"
            f"🆔 Telegram ID: `{telegram_id}`\n"
            f"🪙 Bakiye: **{balance:g} Sanal Kredi**\n"
        )

        if user.subscription_end:
            text += (
                f"\n📅 Abonelik bitişi: "
                f"{user.subscription_end.strftime('%d.%m.%Y')}"
            )

    await message.answer(
        text,
        reply_markup=profile_menu(),
        parse_mode="Markdown"
    )

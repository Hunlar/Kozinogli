
from aiogram import Router, F
from aiogram.types import Message

from sqlalchemy import select

from db.database import AsyncSessionLocal
from db.models import User
from bot.keyboards import profile_menu


router = Router()


@router.message(F.text == "👤 Profil")
async def show_profile(message: Message):

    telegram_id = message.from_user.id

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(User).where(
                User.tg_id == telegram_id
            )
        )

        user = result.scalar_one_or_none()

        if user is None:
            await message.answer(
                "❌ Kullanıcı kaydın bulunamadı.\n"
                "/start komutunu kullanarak yeniden başlayabilirsin."
            )
            return

        balance = user.balance or 0

        text = (
            "👤 **Kullanıcı Profili**\n\n"
            f"🆔 Telegram ID: `{telegram_id}`\n"
            f"🪙 Bakiye: **{balance:,.2f} Sanal Kredi**\n"
        )

        if user.subscription_end:
            text += (
                "\n📅 Abonelik bitişi: "
                f"{user.subscription_end.strftime('%d.%m.%Y')}"
            )

        if user.is_bankrupt:
            text += (
                "\n\n💸 **Hesap Durumu: İFLAS**\n"
                "Yeni oyunlar için kasadan borç almalısın.\n"
                "🏦 Borç işlemi: /borc"
            )

    await message.answer(
        text,
        reply_markup=profile_menu(),
        parse_mode="Markdown"
    )

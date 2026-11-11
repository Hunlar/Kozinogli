
from aiogram import Router, F
from aiogram.types import Message
from datetime import datetime, timedelta
import random

from sqlalchemy import select

from db.database import AsyncSessionLocal
from db.models import User
from bot.keyboards import bonuses_menu, back_button

router = Router()


ROULETTE_OPTIONS = [
    {"text": "%10 Sanal Kredi", "chance": 0.45, "multiplier": 0.10},
    {"text": "%25 Sanal Kredi", "chance": 0.30, "multiplier": 0.25},
    {"text": "%50 Sanal Kredi", "chance": 0.15, "multiplier": 0.50},
    {"text": "Bakiyeni İkiye Katla", "chance": 0.10, "multiplier": 1.00}
]


@router.message(F.text == "Bonuslar")
async def show_bonuses(message: Message):
    await message.answer(
        "🎁 Bonuslar:",
        reply_markup=bonuses_menu()
    )


@router.message(F.text == "Bonus Çarkı")
async def spin_roulette(message: Message):
    user_id = message.from_user.id

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.tg_id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer(
                "Kullanıcı kaydınız bulunamadı. /start komutunu kullanın."
            )
            return

        now = datetime.now()

        if (
            user.last_roulette_spin
            and now - user.last_roulette_spin < timedelta(hours=24)
        ):
            remaining = (
                timedelta(hours=24) - (now - user.last_roulette_spin)
            )

            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)

            await message.answer(
                f"⏳ Bonus çarkını tekrar çevirmek için "
                f"{hours} saat {minutes} dakika beklemelisin."
            )
            return

        weights = [option["chance"] for option in ROULETTE_OPTIONS]
        selected = random.choices(
            ROULETTE_OPTIONS,
            weights=weights,
            k=1
        )[0]

        win_amount = user.balance * selected["multiplier"]
        user.balance += win_amount
        user.last_roulette_spin = now

        await session.commit()

        await message.answer(
            f"🎉 Tebrikler! {selected['text']} kazandın!\n\n"
            f"🪙 Kazandığın: +{win_amount:.2f} Sanal Kredi\n"
            f"💰 Güncel bakiye: {user.balance:.2f} Sanal Kredi",
            reply_markup=back_button()
        )

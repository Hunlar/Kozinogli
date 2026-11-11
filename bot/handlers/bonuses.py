
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardRemove

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import random

from sqlalchemy import select

from db.database import AsyncSessionLocal
from db.models import User


router = Router()

BANKRUPTCY_LIMIT = 4000
TURKEY_TIMEZONE = ZoneInfo("Europe/Istanbul")


ROULETTE_OPTIONS = [
    {
        "text": "%10 Sanal Kredi",
        "chance": 0.45,
        "multiplier": 0.10
    },
    {
        "text": "%25 Sanal Kredi",
        "chance": 0.30,
        "multiplier": 0.25
    },
    {
        "text": "%50 Sanal Kredi",
        "chance": 0.15,
        "multiplier": 0.50
    },
    {
        "text": "Bakiyeni İkiye Katla",
        "chance": 0.10,
        "multiplier": 1.00
    }
]


@router.message(Command("bonus"))
async def show_bonuses(message: Message):

    await message.answer(
        "🎁 **ÖzVeGas Bonus Merkezi**\n\n"
        "Günlük bonus çarkıyla Sanal Kredi kazanabilirsin.\n\n"
        "🎡 Çarkı çevirmek için:\n"
        "/bonuscevir",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )


@router.message(Command("bonuscevir"))
async def spin_roulette(message: Message):

    user_id = message.from_user.id

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User)
            .where(User.tg_id == user_id)
            .with_for_update()
        )

        user = result.scalar_one_or_none()

        if user is None:
            await message.answer(
                "❌ Kullanıcı kaydın bulunamadı.\n"
                "/start komutunu kullan."
            )
            return

        now = datetime.now(TURKEY_TIMEZONE).replace(tzinfo=None)

        if user.last_roulette_spin is not None:
            elapsed = now - user.last_roulette_spin
            cooldown = timedelta(hours=24)

            if elapsed < cooldown:
                remaining = cooldown - elapsed
                hours = int(remaining.total_seconds() // 3600)
                minutes = int(
                    (remaining.total_seconds() % 3600) // 60
                )

                await message.answer(
                    "⏳ Bonus çarkını tekrar çevirmek için "
                    f"{hours} saat {minutes} dakika beklemelisin."
                )
                return

        selected = random.choices(
            ROULETTE_OPTIONS,
            weights=[
                option["chance"]
                for option in ROULETTE_OPTIONS
            ],
            k=1
        )[0]

        balance_before = user.balance or 0
        win_amount = balance_before * selected["multiplier"]

        user.balance = balance_before + win_amount
        user.last_roulette_spin = now

        if user.balance >= BANKRUPTCY_LIMIT:
            user.is_bankrupt = False
            user.bankruptcy_announced = False
            user.bankruptcy_chat_id = None

        await session.commit()
        current_balance = user.balance

    await message.answer(
        "🎉 **BONUS ÇARKI SONUCU**\n\n"
        f"🎁 Kazandığın ödül: {selected['text']}\n"
        f"🪙 Kazandığın miktar: +{win_amount:,.2f} Sanal Kredi\n\n"
        f"💰 Güncel bakiyen: {current_balance:,.2f} Sanal Kredi",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )

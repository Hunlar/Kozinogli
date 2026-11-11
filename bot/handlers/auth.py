
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext

from sqlalchemy import select

from db.database import AsyncSessionLocal
from db.models import User


router = Router()

ISTANBUL = ZoneInfo("Europe/Istanbul")
DAILY_CREDIT = 20_000

BANK_OWNER_TG_ID = 8658946296


@router.message(Command("start"))
async def start_command(
    message: Message,
    state: FSMContext
):
    await state.clear()

    telegram_id = message.from_user.id
    today = datetime.now(ISTANBUL).date()

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(User)
            .where(User.tg_id == telegram_id)
            .with_for_update()
        )

        user = result.scalar_one_or_none()

        if user is None:

            user = User(
                tg_id=telegram_id,
                login=f"user_{telegram_id}",
                balance=DAILY_CREDIT,
                is_blocked=False,
                daily_credit_date=today,
                is_bankrupt=False,
                bankruptcy_announced=False
            )

            session.add(user)
            await session.commit()

            welcome_text = (
                "🎰 ÖzVeGas'a hoş geldin!\n\n"
                "🪙 İlk kredin hesabına eklendi: "
                "20.000 Sanal Kredi\n\n"
                "🎮 Oyunları komutlarla başlatabilirsin.\n"
                "Yardım için /help yaz."
            )

        else:

            welcome_text = (
                "🎰 ÖzVeGas'a tekrar hoş geldin!\n\n"
                f"🪙 Bakiyen: {(user.balance or 0):,.2f} "
                "Sanal Kredi\n\n"
                "🎮 Oyunları komutlarla başlatabilirsin.\n"
                "Yardım için /help yaz."
            )

        if telegram_id == BANK_OWNER_TG_ID:
            welcome_text += (
                "\n\n🏦 ÖzVeGas Kasası sahibi olarak "
                "tanımlandın."
            )

        await session.commit()

    await message.answer(
        welcome_text,
        reply_markup=ReplyKeyboardRemove()
    )
    

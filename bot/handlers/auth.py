
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from sqlalchemy import select

from db.database import AsyncSessionLocal
from db.models import User
from bot.keyboards import main_menu

router = Router()


@router.message(Command("start"))
async def start_command(message: Message, state: FSMContext):
    await state.clear()

    telegram_id = message.from_user.id

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.tg_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                tg_id=telegram_id,
                login=f"user_{telegram_id}",
                balance=0.0,
                is_blocked=False
            )

            session.add(user)
            await session.commit()

    await message.answer(
        "🎰 ÖzVeGas'a hoş geldin!\n\n"
        "🪙 Sanal Kredi ile oyunların keyfini çıkarabilirsin.\n"
        "🎮 Oyunlar ücretsizdir.\n\n"
        "Aşağıdaki menüden bir bölüm seçebilirsin.",
        reply_markup=main_menu(user_id=telegram_id)
    )

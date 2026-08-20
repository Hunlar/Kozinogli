# bot/handlers/games/slots.py
import random
import asyncio
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from db.database import AsyncSessionLocal
from db.models import User
from sqlalchemy import select
from bot.keyboards import games_menu, bet_kb

router = Router()

SLOT_SYMBOLS = {
    "🍒": {"base": 1, "triple": 3},
    "🍊": {"base": 2, "triple": 5},
    "🍋": {"base": 3, "triple": 8},
    "💎": {"base": 5, "triple": 15},
    "7️⃣": {"base": 10, "triple": 30},
    "🔔": {"base": 7, "triple": 20}
}

class SlotsStates(StatesGroup):
    BET = State()

async def spin_animation(message: Message, final_result: list):
    frames = ["🎰|🌀|🌀", "🌀|🎰|🌀", "🌀|🌀|🎰", "|".join(final_result)]
    msg = await message.answer("Крутим...")
    for frame in frames:
        await asyncio.sleep(0.5)
        await msg.edit_text(frame)

@router.message(F.text == "💎Слоты💎")
async def start_slots(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "💰 Введите ставку (или '🔙 Назад' для отмены):",
        reply_markup=bet_kb()
    )
    await state.set_state(SlotsStates.BET)

@router.message(SlotsStates.BET, F.text == "🔙 Назад")
async def cancel_bet(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Игра отменена",
        reply_markup=games_menu()
    )

@router.message(SlotsStates.BET)
async def process_slots(message: Message, state: FSMContext):
    # Обработка кнопки "Назад"
    if message.text == "🔙 Назад":
        await cancel_bet(message, state)
        return

    # Проверка на число
    try:
        bet = float(message.text.replace("₽", "").strip())
        if bet <= 0:
            await state.clear()
            await message.answer(
                "❌ Ставка должна быть больше нуля! Игра отменена",
                reply_markup=games_menu()
            )
            return
    except ValueError:
        await state.clear()
        await message.answer(
            "❌ Некорректная сумма! Игра отменена",
            reply_markup=games_menu()
        )
        return

    # Проверка баланса
    user_id = message.from_user.id
    async with AsyncSessionLocal() as session:
        user = await session.execute(select(User).where(User.tg_id == user_id))
        user = user.scalar()

        if not user:
            await state.clear()
            await message.answer("❌ Вы не зарегистрированы!", reply_markup=games_menu())
            return

        if user.balance < bet:
            await state.clear()
            await message.answer(
                "❌ Недостаточно средств! Игра отменена",
                reply_markup=games_menu()
            )
            return

        user.balance -= bet
        symbols = list(SLOT_SYMBOLS.keys())
        result = [random.choice(symbols) for _ in range(3)]
        await spin_animation(message, result)

        # Расчет выигрыша
        if result[0] == result[1] == result[2]:
            multiplier = SLOT_SYMBOLS[result[0]]["triple"]
        elif len(set(result)) == 2:
            multiplier = max(SLOT_SYMBOLS[s]["base"] for s in result)
        else:
            multiplier = 0

        win = bet * multiplier
        user.balance += win
        await session.commit()

        await message.answer(
            f"🎰 {' '.join(result)}\n"
            f"Множитель: x{multiplier}\n"
            f"💵 Выигрыш: {win} ₽\n"
            f"💰 Баланс: {user.balance} ₽",
            reply_markup=games_menu()
        )
        await state.clear()
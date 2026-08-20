# bot/handlers/games/even_odd.py
import random
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from db.database import AsyncSessionLocal
from db.models import User
from sqlalchemy import select
from bot.keyboards import games_menu, even_odd_kb, bet_kb

router = Router()

class EvenOddStates(StatesGroup):
    BET = State()
    CHOICE = State()

@router.message(F.text == "🎲Чет/Нечет🎲")
async def game_even_odd(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "💰 Сделайте ставку (или '🔙 Назад' для отмены):",
        reply_markup=bet_kb()
    )
    await state.set_state(EvenOddStates.BET)

@router.message(EvenOddStates.BET)
async def process_bet(message: Message, state: FSMContext):
    # Обработка кнопки "Назад"
    if message.text == "🔙 Назад":
        await state.clear()
        await message.answer(
            "❌ Ставка отменена",
            reply_markup=games_menu()
        )
        return

    # Проверка на число
    try:
        bet_amount = float(message.text.replace("₽", "").strip())
        if bet_amount <= 0:
            await state.clear()
            await message.answer(
                "❌ Ставка должна быть больше нуля! Игра отменена",
                reply_markup=games_menu()
            )
            return
    except ValueError:
        await state.clear()
        await message.answer(
            "❌Игра отменена❌",
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

        if user.balance < bet_amount:
            await state.clear()
            await message.answer(
                f"❌ Недостаточно средств! Баланс: {user.balance} ₽",
                reply_markup=games_menu()
            )
            return

        await state.update_data(bet_amount=bet_amount)
        await message.answer("Выберите:", reply_markup=even_odd_kb())
        await state.set_state(EvenOddStates.CHOICE)

@router.message(EvenOddStates.CHOICE, F.text == "🔙 Назад")
async def cancel_choice(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌Игра отменена❌",
        reply_markup=games_menu()
    )

@router.message(EvenOddStates.CHOICE, F.text.in_(["Чет", "Нечет"]))
async def process_choice(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    bet_amount = data.get("bet_amount")

    async with AsyncSessionLocal() as session:
        user = await session.execute(select(User).where(User.tg_id == user_id))
        user = user.scalar()

        random_number = random.randint(1, 100)
        is_even = random_number % 2 == 0
        choice = message.text.lower()

        if (choice == "чет" and is_even) or (choice == "нечет" and not is_even):
            user.balance += bet_amount * 1.5
            result = f"✅ Выигрыш! Число: {random_number}"
        else:
            user.balance -= bet_amount
            result = f"❌ Проигрыш! Число: {random_number}"

        await session.commit()
        await message.answer(
            f"{result}\nНовый баланс: {user.balance} ₽",
            reply_markup=games_menu()
        )
        await state.clear()
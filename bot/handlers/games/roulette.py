# bot/handlers/games/roulette.py
import asyncio
import random
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from db.database import AsyncSessionLocal
from db.models import User
from sqlalchemy import select
from bot.keyboards import (
    roulette_bet_types_kb,
    roulette_colors_kb,
    roulette_ranges_kb,
    roulette_numbers_kb,
    games_menu,
    bet_kb
)

router = Router()

class RouletteStates(StatesGroup):
    CHOOSE_BET_TYPE = State()
    CHOOSE_NUMBER = State()
    CHOOSE_COLOR = State()
    CHOOSE_RANGE = State()
    CONFIRM_BET = State()

ROULETTE_NUMBERS = list(range(0, 37))
COLOR_MAP = {
    "🔴 Красный": [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36],
    "⚫ Черный": [2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35],
    "🟢 Зеленый": [0]
}
RANGE_MAP = {
    "1️⃣-1️⃣2️⃣": (1, 12),
    "1️⃣3️⃣-2️⃣4️⃣": (13, 24),
    "2️⃣5️⃣-3️⃣6️⃣": (25, 36)
}

async def spin_animation(message: Message, result: int):
    msg = await message.answer("🌀 Запускаем рулетку...")
    previous_value = None

    for _ in range(8):
        while True:
            num = random.randint(0, 36)
            color = get_color_emoji(num)
            current_value = f"{color} {num}"
            if current_value != previous_value:
                break

        try:
            await msg.edit_text(current_value)
        except:
            pass

        await asyncio.sleep(0.15)
        previous_value = current_value

    result_color = get_color_emoji(result)
    await msg.edit_text(
        f"🎯 Результат: {result_color} {result}\n"
        f"Цвет: {get_color_name(result)}"
    )

def get_color_emoji(number: int) -> str:
    if number == 0:
        return "🟢"
    return "🔴" if number in COLOR_MAP["🔴 Красный"] else "⚫"

def get_color_name(number: int) -> str:
    if number == 0:
        return "Зеленый"
    return "Красный" if number in COLOR_MAP["🔴 Красный"] else "Черный"

@router.message(F.text == "🎰Рулетка🎰")
async def start_roulette(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🎰 Выберите тип ставки:",
        reply_markup=roulette_bet_types_kb()
    )
    await state.set_state(RouletteStates.CHOOSE_BET_TYPE)

@router.message(RouletteStates.CHOOSE_BET_TYPE, F.text == "🔙 Назад")
async def cancel_roulette(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Игра отменена",
        reply_markup=games_menu()
    )

@router.message(RouletteStates.CHOOSE_BET_TYPE)
async def process_bet_type(message: Message, state: FSMContext):
    if message.text == "🔙 Назад":
        await cancel_roulette(message, state)
        return

    if "Число" in message.text:
        await message.answer(
            "🔢 Выберите число (или '🔙 Назад' для отмены):",
            reply_markup=roulette_numbers_kb()
        )
        await state.set_state(RouletteStates.CHOOSE_NUMBER)
    elif "Цвет" in message.text:
        await message.answer(
            "🎨 Выберите цвет (или '🔙 Назад' для отмены):",
            reply_markup=roulette_colors_kb()
        )
        await state.set_state(RouletteStates.CHOOSE_COLOR)
    elif "Диапазон" in message.text:
        await message.answer(
            "📊 Выберите диапазон (или '🔙 Назад' для отмены):",
            reply_markup=roulette_ranges_kb()
        )
        await state.set_state(RouletteStates.CHOOSE_RANGE)

@router.message(RouletteStates.CHOOSE_NUMBER, F.text == "🔙 Назад")
async def cancel_number_choice(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Игра отменена",
        reply_markup=games_menu()
    )

@router.message(RouletteStates.CHOOSE_NUMBER)
async def process_number(message: Message, state: FSMContext):
    if message.text == "🔙 Назад":
        await cancel_number_choice(message, state)
        return

    try:
        number = int(message.text.strip())
        if number < 0 or number > 36:
            await state.clear()
            await message.answer(
                "❌ Число должно быть от 0 до 36! Игра отменена",
                reply_markup=games_menu()
            )
            return

        await state.update_data(bet_type="number", bet_value=number)
        await ask_bet_amount(message, state)
    except ValueError:
        await state.clear()
        await message.answer(
            "❌ Некорректное число! Игра отменена",
            reply_markup=games_menu()
        )

@router.message(RouletteStates.CHOOSE_COLOR, F.text == "🔙 Назад")
async def cancel_color_choice(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Игра отменена",
        reply_markup=games_menu()
    )

@router.message(RouletteStates.CHOOSE_COLOR)
async def process_color(message: Message, state: FSMContext):
    if message.text == "🔙 Назад":
        await cancel_color_choice(message, state)
        return

    if message.text not in COLOR_MAP:
        await state.clear()
        await message.answer(
            "❌ Некорректный цвет! Игра отменена",
            reply_markup=games_menu()
        )
        return

    await state.update_data(bet_type="color", bet_value=message.text)
    await ask_bet_amount(message, state)

@router.message(RouletteStates.CHOOSE_RANGE, F.text == "🔙 Назад")
async def cancel_range_choice(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Игра отменена",
        reply_markup=games_menu()
    )

@router.message(RouletteStates.CHOOSE_RANGE)
async def process_range(message: Message, state: FSMContext):
    if message.text == "🔙 Назад":
        await cancel_range_choice(message, state)
        return

    if message.text not in RANGE_MAP:
        await state.clear()
        await message.answer(
            "❌ Некорректный диапазон! Игра отменена",
            reply_markup=games_menu()
        )
        return

    await state.update_data(bet_type="range", bet_value=message.text)
    await ask_bet_amount(message, state)

async def ask_bet_amount(message: Message, state: FSMContext):
    await message.answer(
        "💰 Введите сумму ставки (или '🔙 Назад' для отмены):",
        reply_markup=bet_kb()
    )
    await state.set_state(RouletteStates.CONFIRM_BET)

@router.message(RouletteStates.CONFIRM_BET, F.text == "🔙 Назад")
async def cancel_bet_amount(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Игра отменена",
        reply_markup=games_menu()
    )

@router.message(RouletteStates.CONFIRM_BET)
async def process_bet_amount(message: Message, state: FSMContext):
    if message.text == "🔙 Назад":
        await cancel_bet_amount(message, state)
        return

    try:
        bet_amount = float(message.text.replace("₽", "").strip())
        if bet_amount <= 0:
            await state.clear()
            await message.answer(
                "❌ Ставка должна быть больше нуля! Игра отменена",
                reply_markup=games_menu()
            )
            return

        async with AsyncSessionLocal() as session:
            user = await session.execute(select(User).where(User.tg_id == message.from_user.id))
            user = user.scalar()

            if user.balance < bet_amount:
                await state.clear()
                await message.answer(
                    "❌ Недостаточно средств! Игра отменена",
                    reply_markup=games_menu()
                )
                return

            result = random.choice(ROULETTE_NUMBERS)
            await spin_animation(message, result)

            data = await state.get_data()
            win = check_win(data, result)
            multiplier = get_multiplier(data["bet_type"])

            user.balance += bet_amount * multiplier if win else -bet_amount
            await session.commit()

            result_text = (
                f"🎉 Выигрыш: +{bet_amount * multiplier:.2f} ₽" if win else
                f"😞 Проигрыш: -{bet_amount:.2f} ₽"
            )
            await message.answer(
                f"{result_text}\n💵 Баланс: {user.balance:.2f} ₽",
                reply_markup=games_menu()
            )
            await state.clear()

    except ValueError:
        await state.clear()
        await message.answer(
            "❌ Некорректная сумма! Игра отменена",
            reply_markup=games_menu()
        )

def check_win(data: dict, result: int) -> bool:
    bet_type = data["bet_type"]
    value = data["bet_value"]

    if bet_type == "number":
        return int(value) == result
    elif bet_type == "color":
        return result in COLOR_MAP[value]
    elif bet_type == "range":
        start, end = RANGE_MAP[value]
        return start <= result <= end

def get_multiplier(bet_type: str) -> float:
    return {
        "number": 35,
        "color": 2,
        "range": 3
    }[bet_type]
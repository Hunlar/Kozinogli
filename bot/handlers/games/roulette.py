
import asyncio
import random
import math

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from sqlalchemy import select

from db.database import AsyncSessionLocal
from db.models import User

from bot.keyboards import (
    roulette_bet_types_kb,
    roulette_colors_kb,
    roulette_ranges_kb,
    roulette_numbers_kb,
    bet_kb
)

from bot.utils.bankruptcy import check_bankruptcy


router = Router()


class RouletteStates(StatesGroup):
    CHOOSE_BET_TYPE = State()
    CHOOSE_NUMBER = State()
    CHOOSE_COLOR = State()
    CHOOSE_RANGE = State()
    CONFIRM_BET = State()


ROULETTE_NUMBERS = list(range(37))


COLOR_MAP = {
    "🔴 Kırmızı": [
        1, 3, 5, 7, 9, 12, 14, 16, 18,
        19, 21, 23, 25, 27, 30, 32, 34, 36
    ],
    "⚫ Siyah": [
        2, 4, 6, 8, 10, 11, 13, 15, 17,
        20, 22, 24, 26, 28, 29, 31, 33, 35
    ],
    "🟢 Yeşil": [0]
}


RANGE_MAP = {
    "1️⃣-1️⃣2️⃣": (1, 12),
    "1️⃣3️⃣-2️⃣4️⃣": (13, 24),
    "2️⃣5️⃣-3️⃣6️⃣": (25, 36)
}


async def spin_animation(message: Message, result: int):
    msg = await message.answer("🎰 Rulet dönüyor...")

    previous = None

    for _ in range(10):
        while True:
            number = random.randint(0, 36)
            value = f"{get_color_emoji(number)} {number}"

            if value != previous:
                break

        try:
            await msg.edit_text(value)
        except Exception:
            pass

        await asyncio.sleep(0.15)
        previous = value

    await msg.edit_text(
        f"🎯 {get_color_emoji(result)} {result} "
        f"| {get_color_name(result)}"
    )


def get_color_emoji(number: int) -> str:
    if number == 0:
        return "🟢"

    if number in COLOR_MAP["🔴 Kırmızı"]:
        return "🔴"

    return "⚫"


def get_color_name(number: int) -> str:
    if number == 0:
        return "Yeşil"

    if number in COLOR_MAP["🔴 Kırmızı"]:
        return "Kırmızı"

    return "Siyah"


@router.message(Command("roulette"))
@router.message(F.text == "🎰 Rulet")
async def start_roulette(message: Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "🎰 **Rulet**\n\nBahis türünü seç:",
        reply_markup=roulette_bet_types_kb(),
        parse_mode="Markdown"
    )

    await state.set_state(RouletteStates.CHOOSE_BET_TYPE)


async def cancel(message: Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "❌ Rulet oyunu iptal edildi.",
        reply_markup=ReplyKeyboardRemove()
    )


@router.message(
    RouletteStates.CHOOSE_BET_TYPE,
    F.text == "🔙 Geri"
)
async def cancel_bet_type(message: Message, state: FSMContext):
    await cancel(message, state)


@router.message(RouletteStates.CHOOSE_BET_TYPE)
async def process_bet_type(message: Message, state: FSMContext):

    if message.text == "🔢 Sayı":
        await message.answer(
            "🔢 Bahis yapmak istediğin sayıyı seç:",
            reply_markup=roulette_numbers_kb()
        )

        await state.set_state(RouletteStates.CHOOSE_NUMBER)

    elif message.text == "🎨 Renk":
        await message.answer(
            "🎨 Bir renk seç:",
            reply_markup=roulette_colors_kb()
        )

        await state.set_state(RouletteStates.CHOOSE_COLOR)

    elif message.text == "📊 Aralık":
        await message.answer(
            "📊 Bir sayı aralığı seç:",
            reply_markup=roulette_ranges_kb()
        )

        await state.set_state(RouletteStates.CHOOSE_RANGE)

    else:
        await message.answer("❌ Lütfen menüden bir bahis türü seç.")


@router.message(
    RouletteStates.CHOOSE_NUMBER,
    F.text == "🔙 Geri"
)
async def cancel_number(message: Message, state: FSMContext):
    await cancel(message, state)


@router.message(RouletteStates.CHOOSE_NUMBER)
async def process_number(message: Message, state: FSMContext):

    try:
        number = int(message.text.strip())

        if not 0 <= number <= 36:
            raise ValueError

    except (ValueError, AttributeError):
        await message.answer("❌ 0 ile 36 arasında bir sayı seç.")
        return

    await state.update_data(
        bet_type="number",
        bet_value=number
    )

    await ask_bet(message, state)


@router.message(
    RouletteStates.CHOOSE_COLOR,
    F.text == "🔙 Geri"
)
async def cancel_color(message: Message, state: FSMContext):
    await cancel(message, state)


@router.message(RouletteStates.CHOOSE_COLOR)
async def process_color(message: Message, state: FSMContext):

    if message.text not in COLOR_MAP:
        await message.answer("❌ Geçersiz renk seçimi.")
        return

    await state.update_data(
        bet_type="color",
        bet_value=message.text
    )

    await ask_bet(message, state)


@router.message(
    RouletteStates.CHOOSE_RANGE,
    F.text == "🔙 Geri"
)
async def cancel_range(message: Message, state: FSMContext):
    await cancel(message, state)


@router.message(RouletteStates.CHOOSE_RANGE)
async def process_range(message: Message, state: FSMContext):

    if message.text not in RANGE_MAP:
        await message.answer("❌ Geçersiz sayı aralığı.")
        return

    await state.update_data(
        bet_type="range",
        bet_value=message.text
    )

    await ask_bet(message, state)


async def ask_bet(message: Message, state: FSMContext):
    await message.answer(
        "🪙 Bahis miktarını gir:",
        reply_markup=bet_kb()
    )

    await state.set_state(RouletteStates.CONFIRM_BET)


@router.message(
    RouletteStates.CONFIRM_BET,
    F.text == "🔙 Geri"
)
async def cancel_bet_amount(message: Message, state: FSMContext):
    await cancel(message, state)


@router.message(RouletteStates.CONFIRM_BET)
async def process_bet_amount(message: Message, state: FSMContext):

    try:
        bet = float(message.text.replace(",", ".").strip())

        if not math.isfinite(bet) or bet <= 0:
            raise ValueError

    except (ValueError, AttributeError):
        await message.answer("❌ Geçerli ve pozitif bir bahis miktarı gir.")
        return

    data = await state.get_data()

    if not all(key in data for key in ("bet_type", "bet_value")):
        await state.clear()

        return await message.answer(
            "❌ Bahis bilgileri bulunamadı. Oyunu yeniden başlat.",
            reply_markup=ReplyKeyboardRemove()
        )

    async with AsyncSessionLocal() as session:

        result_user = await session.execute(
            select(User)
            .where(User.tg_id == message.from_user.id)
            .with_for_update()
        )

        user = result_user.scalar_one_or_none()

        if user is None:
            await state.clear()

            return await message.answer(
                "❌ Kullanıcı kaydın bulunamadı.",
                reply_markup=ReplyKeyboardRemove()
            )

        balance = user.balance or 0

        if balance < bet:
            await state.clear()

            return await message.answer(
                "❌ Bahsin için yeterli Sanal Kredin yok.",
                reply_markup=ReplyKeyboardRemove()
            )

        user.balance = balance - bet

        await session.commit()

    roulette_result = random.choice(ROULETTE_NUMBERS)

    await spin_animation(message, roulette_result)

    won = check_win(data, roulette_result)
    multiplier = get_multiplier(data["bet_type"])

    if won:
        payout = bet * (multiplier + 1)

        result_text = (
            f"🎉 Kazandın!\n"
            f"🪙 Net kazanç: +{bet * multiplier:,.2f} "
            f"Sanal Kredi"
        )

    else:
        payout = 0

        result_text = (
            f"😔 Kaybettin!\n"
            f"🪙 Kaybedilen bahis: -{bet:,.2f} Sanal Kredi"
        )

    async with AsyncSessionLocal() as session:

        result_user = await session.execute(
            select(User)
            .where(User.tg_id == message.from_user.id)
            .with_for_update()
        )

        user = result_user.scalar_one_or_none()

        if user is None:
            await state.clear()

            return await message.answer(
                "❌ Kullanıcı hesabına ulaşılamadı.",
                reply_markup=ReplyKeyboardRemove()
            )

        user.balance = (user.balance or 0) + payout

        final_balance = user.balance

        await session.commit()

    await state.clear()

    await check_bankruptcy(
        bot=message.bot,
        telegram_id=message.from_user.id,
        chat_id=message.chat.id,
        chat_type=message.chat.type,
        first_name=message.from_user.first_name
    )

    await message.answer(
        f"🎰 **Rulet Sonucu**\n\n"
        f"🎯 Gelen sayı: {get_color_emoji(roulette_result)} "
        f"{roulette_result}\n"
        f"🎨 Renk: {get_color_name(roulette_result)}\n\n"
        f"{result_text}\n\n"
        f"📊 Çarpan: x{multiplier}\n"
        f"💰 Güncel bakiye: {final_balance:,.2f} Sanal Kredi",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )


def check_win(data: dict, result: int) -> bool:
    bet_type = data["bet_type"]
    bet_value = data["bet_value"]

    if bet_type == "number":
        return int(bet_value) == result

    elif bet_type == "color":
        return result in COLOR_MAP[bet_value]

    elif bet_type == "range":
        start, end = RANGE_MAP[bet_value]
        return start <= result <= end

    return False


def get_multiplier(bet_type: str) -> float:
    return {
        "number": 35,
        "color": 1,
        "range": 2
    }[bet_type]


import random
import asyncio
import math

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from sqlalchemy import select

from db.database import AsyncSessionLocal
from db.models import User
from bot.utils.bankruptcy import check_bankruptcy


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
    frames = [
        "🎰 | 🌀 | 🌀",
        "🌀 | 🎰 | 🌀",
        "🌀 | 🌀 | 🎰",
        " | ".join(final_result)
    ]

    msg = await message.answer("🎰 Slot makinesi çalışıyor...")

    for frame in frames:
        await asyncio.sleep(0.5)

        try:
            await msg.edit_text(frame)
        except Exception:
            pass


@router.message(Command("slots"))
@router.message(F.text == "💎 Slot Makinesi")
async def start_slots(message: Message, state: FSMContext):
    await state.clear()

    await state.update_data(owner_id=message.from_user.id)
    await state.set_state(SlotsStates.BET)

    await message.answer(
        "🎰 **Slot Makinesi**\n\n"
        "🪙 Oynamak istediğin Sanal Kredi miktarını yaz:\n\n"
        "İptal etmek için /iptal yazabilirsin.",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )


@router.message(SlotsStates.BET, Command("iptal"))
async def cancel_bet(message: Message, state: FSMContext):
    data = await state.get_data()

    if data.get("owner_id") != message.from_user.id:
        return

    await state.clear()

    await message.answer(
        "❌ Slot oyunu iptal edildi.",
        reply_markup=ReplyKeyboardRemove()
    )


@router.message(SlotsStates.BET)
async def process_slots(message: Message, state: FSMContext):

    data = await state.get_data()

    # Bahis yalnızca oyunu başlatan kişiden kabul edilir.
    if data.get("owner_id") != message.from_user.id:
        return

    try:
        bet = float(message.text.replace(",", ".").strip())

        if not math.isfinite(bet) or bet <= 0:
            raise ValueError

    except (ValueError, AttributeError):
        await state.clear()

        return await message.answer(
            "❌ Geçersiz bahis miktarı!",
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
                "❌ Kullanıcı kaydın bulunamadı. /start komutunu kullan.",
                reply_markup=ReplyKeyboardRemove()
            )

        balance = user.balance or 0

        if balance < bet:
            await state.clear()

            return await message.answer(
                "❌ Bu bahis için yeterli Sanal Kredin yok.",
                reply_markup=ReplyKeyboardRemove()
            )

        # Bahis düşülür.
        user.balance = balance - bet

        # Slot sonucu oluşturulur.
        symbols = list(SLOT_SYMBOLS.keys())

        slot_result = [
            random.choice(symbols)
            for _ in range(3)
        ]

        await spin_animation(message, slot_result)

        # Mevcut çarpan sistemi korunur.
        if slot_result[0] == slot_result[1] == slot_result[2]:
            multiplier = SLOT_SYMBOLS[slot_result[0]]["triple"]

        elif (
            slot_result[0] == slot_result[1]
            or slot_result[1] == slot_result[2]
            or slot_result[0] == slot_result[2]
        ):
            if slot_result[0] == slot_result[1]:
                pair_symbol = slot_result[0]
            elif slot_result[1] == slot_result[2]:
                pair_symbol = slot_result[1]
            else:
                pair_symbol = slot_result[0]

            multiplier = SLOT_SYMBOLS[pair_symbol]["base"]

        else:
            multiplier = 0

        # Kazanç hesaplanır.
        win = bet * multiplier
        user.balance += win

        final_balance = user.balance

        await session.commit()

    await state.clear()

    # Bakiye 4.000'in altına düştüyse iflas kontrolü yapılır.
    await check_bankruptcy(
        bot=message.bot,
        telegram_id=message.from_user.id,
        chat_id=message.chat.id,
        chat_type=message.chat.type,
        first_name=message.from_user.first_name
    )

    if multiplier == 0:
        result_text = "😔 Bu turda kazanamadın."
    elif multiplier == 1:
        result_text = "🎉 Çift sembol! Bahsini geri kazandın."
    else:
        result_text = "🎉 Tebrikler, kazandın!"

    await message.answer(
        f"🎰 **Slot Sonucu**\n\n"
        f"{' | '.join(slot_result)}\n\n"
        f"{result_text}\n"
        f"📊 Çarpan: x{multiplier}\n"
        f"🪙 Kazanç: {win:,.2f} Sanal Kredi\n"
        f"💰 Güncel bakiye: {final_balance:,.2f} Sanal Kredi",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )

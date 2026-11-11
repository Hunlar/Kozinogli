
import asyncio
import math
import random

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardRemove
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from sqlalchemy import select

from db.database import AsyncSessionLocal
from db.models import User

from bot.utils.bankruptcy import check_bankruptcy


router = Router()


class CrashStates(StatesGroup):
    BET = State()
    COEFF_INPUT = State()
    FLYING = State()


CRASH_PROBABILITY = 0.025
MULTIPLIER_STEP = 0.01
BASE_MULTIPLIER = 1.00
UPDATE_INTERVAL = 0.1


async def refund_bet(telegram_id: int, bet: float):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User)
            .where(User.tg_id == telegram_id)
            .with_for_update()
        )

        user = result.scalar_one_or_none()

        if user is not None:
            user.balance = (user.balance or 0) + bet
            await session.commit()


async def finish_bankruptcy(message: Message, player_id: int):
    await check_bankruptcy(
        bot=message.bot,
        telegram_id=player_id,
        chat_id=message.chat.id,
        chat_type=message.chat.type,
        first_name=message.from_user.first_name or "Oyuncu"
    )


async def rocket_animation(
    message: Message,
    state: FSMContext,
    stop_event: asyncio.Event
):
    data = await state.get_data()

    current_multiplier = data["multiplier"]
    bet = data["bet"]
    target_coeff = data["target_coeff"]
    player_id = data["owner_id"]

    frames = [
        "🚀✨▰▰▰▰▰▰▰▰▰",
        "▰🚀✨▰▰▰▰▰▰▰▰",
        "▰▰🚀✨▰▰▰▰▰▰",
        "▰▰▰🚀✨▰▰▰▰▰",
        "▰▰▰▰🚀✨▰▰▰▰",
        "▰▰▰▰▰🚀✨▰▰▰",
        "▰▰▰▰▰▰🚀✨▰▰",
        "▰▰▰▰▰▰▰🚀✨▰",
        "▰▰▰▰▰▰▰▰🚀✨"
    ]

    animation_message = await message.answer(
        "🚀 Roket hazırlanıyor..."
    )

    await state.update_data(
        game_message_id=animation_message.message_id
    )

    while not stop_event.is_set():

        current_multiplier = round(
            current_multiplier + MULTIPLIER_STEP,
            2
        )

        await state.update_data(
            multiplier=current_multiplier
        )

        if current_multiplier >= target_coeff:

            stop_event.set()

            win = bet * current_multiplier

            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(User)
                    .where(User.tg_id == player_id)
                    .with_for_update()
                )

                user = result.scalar_one_or_none()

                if user is None:
                    await state.clear()
                    return

                user.balance = (user.balance or 0) + win
                balance = user.balance

                await session.commit()

            await animation_message.edit_text(
                f"🎉 Hedefe ulaşıldı!\n\n"
                f"📈 Katsayı: x{current_multiplier:.2f}\n"
                f"💰 Kazanç: {win:,.2f} Sanal Kredi\n"
                f"🪙 Yeni bakiye: {balance:,.2f} Sanal Kredi"
            )

            await finish_bankruptcy(message, player_id)

            await message.answer(
                "🎮 Başka bir oyun seçebilirsin.",
                reply_markup=ReplyKeyboardRemove()
            )

            await state.clear()
            return

        frame = frames[
            int(current_multiplier * 10) % len(frames)
        ]

        text = (
            f"{frame}\n\n"
            f"📈 Katsayı: x{current_multiplier:.2f}\n"
            f"💰 Potansiyel kazanç: "
            f"{bet * current_multiplier:,.2f} Sanal Kredi"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"🛑 Kazancı Al x{current_multiplier:.2f}",
                        callback_data=f"crash_cashout:{player_id}"
                    )
                ]
            ]
        )

        try:
            await animation_message.edit_text(
                text,
                reply_markup=keyboard
            )
        except Exception:
            pass

        if stop_event.is_set():
            return

        if random.random() < CRASH_PROBABILITY:

            stop_event.set()

            await animation_message.edit_text(
                f"💥 ROKET PATLADI!\n\n"
                f"📉 Patlama katsayısı: x{current_multiplier:.2f}\n"
                f"💸 Kaybedilen bahis: {bet:,.2f} Sanal Kredi"
            )

            await finish_bankruptcy(message, player_id)

            await message.answer(
                "🍀 Şansını tekrar dene!",
                reply_markup=ReplyKeyboardRemove()
            )

            await state.clear()
            return

        await asyncio.sleep(UPDATE_INTERVAL)


@router.message(Command("rocket"))
@router.message(F.text == "🚀 Roket")
async def start_crash(
    message: Message,
    state: FSMContext
):
    await state.clear()

    await state.update_data(
        owner_id=message.from_user.id
    )

    await state.set_state(CrashStates.BET)

    await message.answer(
        "🚀 **ROKET OYUNU**\n\n"
        "💰 Bahis miktarını yaz.\n\n"
        "İptal etmek için /iptal yaz.",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )


@router.message(CrashStates.BET, Command("iptal"))
async def cancel_bet(
    message: Message,
    state: FSMContext
):
    data = await state.get_data()

    if data.get("owner_id") != message.from_user.id:
        return

    await state.clear()

    await message.answer(
        "❌ Roket oyunu iptal edildi.",
        reply_markup=ReplyKeyboardRemove()
    )


@router.message(CrashStates.BET)
async def process_bet(
    message: Message,
    state: FSMContext
):
    data = await state.get_data()

    if data.get("owner_id") != message.from_user.id:
        return

    try:
        bet = float(
            message.text.replace(",", ".").strip()
        )

        if not math.isfinite(bet) or bet <= 0:
            raise ValueError

    except (ValueError, AttributeError):
        return await message.answer(
            "❌ Geçersiz bahis miktarı. Tekrar dene."
        )

    player_id = data["owner_id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User)
            .where(User.tg_id == player_id)
            .with_for_update()
        )

        user = result.scalar_one_or_none()

        if user is None:
            await state.clear()
            return await message.answer(
                "❌ Kullanıcı hesabı bulunamadı.",
                reply_markup=ReplyKeyboardRemove()
            )

        if (user.balance or 0) < bet:
            await state.clear()
            return await message.answer(
                "❌ Yetersiz Sanal Kredi.",
                reply_markup=ReplyKeyboardRemove()
            )

        user.balance -= bet
        await session.commit()

    await state.update_data(bet=bet)

    await state.set_state(CrashStates.COEFF_INPUT)

    await message.answer(
        "📈 Hedef katsayıyı gir.\n\n"
        "Örnek: 1.5 veya 2.0 veya 3.0\n\n"
        "İptal edersen bahis iade edilir. /iptal yaz.",
        reply_markup=ReplyKeyboardRemove()
    )


@router.message(CrashStates.COEFF_INPUT, Command("iptal"))
async def cancel_coeff(
    message: Message,
    state: FSMContext
):
    data = await state.get_data()

    if data.get("owner_id") != message.from_user.id:
        return

    bet = data.get("bet", 0)
    player_id = data["owner_id"]

    await refund_bet(player_id, bet)

    await state.clear()

    await message.answer(
        "❌ Oyun iptal edildi.\n"
        "🪙 Bahsin hesabına iade edildi.",
        reply_markup=ReplyKeyboardRemove()
    )


@router.message(CrashStates.COEFF_INPUT)
async def process_coeff(
    message: Message,
    state: FSMContext
):
    data = await state.get_data()

    if data.get("owner_id") != message.from_user.id:
        return

    try:
        target = float(
            message.text.replace(",", ".").strip()
        )

        if (
            not math.isfinite(target)
            or target <= 1.0
            or target > 100
        ):
            raise ValueError

    except (ValueError, AttributeError):

        bet = data.get("bet", 0)
        player_id = data["owner_id"]

        await refund_bet(player_id, bet)

        await state.clear()

        return await message.answer(
            "❌ Geçersiz katsayı!\n"
            "Katsayı 1.0'dan büyük ve 100'den küçük "
            "veya eşit olmalıdır.\n\n"
            "🪙 Bahsin iade edildi.",
            reply_markup=ReplyKeyboardRemove()
        )

    await state.update_data(
        target_coeff=target,
        multiplier=BASE_MULTIPLIER
    )

    await state.set_state(CrashStates.FLYING)

    stop_event = asyncio.Event()

    await state.update_data(
        stop_event=stop_event
    )

    await rocket_animation(
        message,
        state,
        stop_event
    )


@router.callback_query(
    CrashStates.FLYING,
    F.data.startswith("crash_cashout:")
)
async def cashout_handler(
    callback: CallbackQuery,
    state: FSMContext
):
    data = await state.get_data()

    owner_id = data.get("owner_id")

    if owner_id != callback.from_user.id:
        return await callback.answer(
            "Bu oyun başka bir oyuncuya ait!",
            show_alert=True
        )

    try:
        callback_owner_id = int(
            callback.data.split(":")[1]
        )
    except (ValueError, IndexError):
        return await callback.answer(
            "Geçersiz oyun bilgisi!",
            show_alert=True
        )

    if callback_owner_id != owner_id:
        return await callback.answer(
            "Bu oyun başka bir oyuncuya ait!",
            show_alert=True
        )

    if (
        callback.message is None
        or callback.message.message_id != data.get("game_message_id")
    ):
        return await callback.answer(
            "Bu oyun mesajı artık geçerli değil!",
            show_alert=True
        )

    stop_event = data.get("stop_event")

    if stop_event is None or stop_event.is_set():
        return await callback.answer(
            "Oyun sona erdi!",
            show_alert=True
        )

    stop_event.set()

    multiplier = data["multiplier"]
    bet = data["bet"]
    win = bet * multiplier

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User)
            .where(User.tg_id == owner_id)
            .with_for_update()
        )

        user = result.scalar_one_or_none()

        if user is None:
            await state.clear()
            return await callback.answer(
                "Kullanıcı hesabı bulunamadı.",
                show_alert=True
            )

        user.balance = (user.balance or 0) + win
        balance = user.balance

        await session.commit()

    await callback.answer("Kazancın alındı!")

    await callback.message.edit_text(
        f"🎉 KAZANÇ ALINDI!\n\n"
        f"📈 Katsayı: x{multiplier:.2f}\n"
        f"💰 Kazanç: +{win:,.2f} Sanal Kredi\n"
        f"🪙 Yeni bakiye: {balance:,.2f} Sanal Kredi"
    )

    await check_bankruptcy(
        bot=callback.bot,
        telegram_id=owner_id,
        chat_id=callback.message.chat.id,
        chat_type=callback.message.chat.type,
        first_name=callback.from_user.first_name or "Oyuncu"
    )

    await callback.message.answer(
        "🎮 Başka bir oyun seçebilirsin.",
        reply_markup=ReplyKeyboardRemove()
    )

    await state.clear()
redi\n"
        f"🪙 Yeni bakiye: {balance:,.2f} Sanal Kredi"
    )

    await check_bankruptcy(
        bot=callback.bot,
        telegram_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        chat_type=callback.message.chat.type,
        first_name=callback.from_user.first_name or "Oyuncu"
    )

    await callback.message.answer(
        "🎮 Başka bir oyun seçebilirsin.",
        reply_markup=ReplyKeyboardRemove()
    )

    await state.clear()
            

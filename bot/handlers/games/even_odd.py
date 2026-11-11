
import random

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from db.database import AsyncSessionLocal
from db.models import User
from bot.keyboards import games_menu, even_odd_kb, bet_kb
from bot.utils.bankruptcy import check_bankruptcy


router = Router()


class EvenOddStates(StatesGroup):
    BET = State()
    CHOICE = State()


@router.message(F.text == "🎲 Çift / Tek")
async def game_even_odd(message: Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "🎲 **Çift / Tek Oyunu**\n\n"
        "💰 Oynamak istediğin bahis miktarını seç:",
        reply_markup=bet_kb()
    )

    await state.set_state(EvenOddStates.BET)


@router.message(EvenOddStates.BET)
async def process_bet(message: Message, state: FSMContext):

    if message.text == "🔙 Geri":
        await state.clear()
        await message.answer(
            "❌ Oyun iptal edildi.",
            reply_markup=games_menu()
        )
        return

    try:
        bet = float(message.text.replace("Sanal Kredi", "").strip())

        if bet <= 0:
            raise ValueError

    except (ValueError, TypeError):
        await message.answer(
            "❌ Geçersiz bahis miktarı. Lütfen tekrar dene.",
            reply_markup=bet_kb()
        )
        return

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(User)
            .where(User.tg_id == message.from_user.id)
            .with_for_update()
        )

        user = result.scalar_one_or_none()

        if user is None:
            await state.clear()
            await message.answer(
                "❌ Kullanıcı hesabı bulunamadı.",
                reply_markup=games_menu()
            )
            return

        if (user.balance or 0) < bet:
            balance = user.balance or 0

            await state.clear()
            await message.answer(
                f"❌ Yetersiz bakiye!\n\n"
                f"🪙 Bakiyen: {balance:,.2f} Sanal Kredi",
                reply_markup=games_menu()
            )
            return

        user.balance -= bet

        await session.commit()

    await state.update_data(
        bet=bet,
        owner_id=message.from_user.id
    )

    await message.answer(
        f"🪙 Bahsin: {bet:,.2f} Sanal Kredi\n\n"
        "🎯 Sence gelecek sayı çift mi, tek mi?",
        reply_markup=even_odd_kb()
    )

    await state.set_state(EvenOddStates.CHOICE)


@router.message(EvenOddStates.CHOICE, F.text == "🔙 Geri")
async def cancel_choice(message: Message, state: FSMContext):

    data = await state.get_data()
    bet = data.get("bet")
    owner_id = data.get("owner_id")

    if owner_id != message.from_user.id:
        return

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(User)
            .where(User.tg_id == message.from_user.id)
            .with_for_update()
        )

        user = result.scalar_one_or_none()

        if user is not None and bet:
            user.balance = (user.balance or 0) + bet
            await session.commit()

            balance = user.balance
        else:
            balance = 0

    await state.clear()

    await message.answer(
        "❌ Oyun iptal edildi.\n"
        "💰 Bahsin hesabına iade edildi.\n\n"
        f"🪙 Güncel bakiye: {balance:,.2f} Sanal Kredi",
        reply_markup=games_menu()
    )


@router.message(EvenOddStates.CHOICE, F.text.in_(["Çift", "Tek"]))
async def process_choice(message: Message, state: FSMContext):

    data = await state.get_data()

    bet = data.get("bet")
    owner_id = data.get("owner_id")

    if owner_id != message.from_user.id:
        return

    if not bet:
        await state.clear()
        await message.answer(
            "❌ Oyun bilgileri bulunamadı. Yeniden başlayabilirsin.",
            reply_markup=games_menu()
        )
        return

    number = random.randint(1, 100)
    is_even = number % 2 == 0

    choice = message.text.lower()
    win = (
        (choice == "çift" and is_even)
        or (choice == "tek" and not is_even)
    )

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(User)
            .where(User.tg_id == message.from_user.id)
            .with_for_update()
        )

        user = result.scalar_one_or_none()

        if user is None:
            await state.clear()
            await message.answer(
                "❌ Kullanıcı hesabı bulunamadı.",
                reply_markup=games_menu()
            )
            return

        if win:
            payout = bet * 2
            user.balance = (user.balance or 0) + payout

            result_text = (
                "🎉 TEBRİKLER, KAZANDIN!\n"
                f"💰 Ödeme: {payout:,.2f} Sanal Kredi"
            )

        else:
            result_text = (
                "😔 KAYBETTİN!\n"
                f"💸 Kaybettiğin bahis: {bet:,.2f} Sanal Kredi"
            )

        balance = user.balance or 0

        await session.commit()

    await state.clear()

    await message.answer(
        f"🎲 Gelen sayı: {number}\n"
        f"🎯 Tahminin: {message.text}\n\n"
        f"{result_text}\n\n"
        f"🪙 Güncel bakiye: {balance:,.2f} Sanal Kredi",
        reply_markup=games_menu()
    )

    await check_bankruptcy(
        bot=message.bot,
        telegram_id=message.from_user.id,
        chat_id=message.chat.id,
        chat_type=message.chat.type,
        first_name=message.from_user.first_name
    )

import asyncio
import random
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from db.database import AsyncSessionLocal
from db.models import User
from sqlalchemy import select
from bot.keyboards import games_menu, bet_kb

router = Router()

class CrashStates(StatesGroup):
    BET = State()
    COEFF_INPUT = State()
    FLYING = State()

CRASH_PROBABILITY = 0.025
MULTIPLIER_STEP = 0.01
BASE_MULTIPLIER = 1.00
UPDATE_INTERVAL = 0.1

async def rocket_animation(
    message: Message,
    state: FSMContext,
    stop_event: asyncio.Event
):
    data = await state.get_data()
    current_multiplier = data['multiplier']
    bet = data['bet']
    target_coeff = data.get('target_coeff', None)

    frames = [
        "🚀✨▰▰▰▰▰▰▰▰▰",
        "▰🚀✨▰▰▰▰▰▰▰▰",
        "▰▰🚀✨▰▰▰▰▰▰▰",
        "▰▰▰🚀✨▰▰▰▰▰▰",
        "▰▰▰▰🚀✨▰▰▰▰▰",
        "▰▰▰▰▰🚀✨▰▰▰▰",
        "▰▰▰▰▰▰🚀✨▰▰▰",
        "▰▰▰▰▰▰▰🚀✨▰▰",
        "▰▰▰▰▰▰▰▰🚀✨▰",
        "▰▰▰▰▰▰▰▰▰🚀✨"
    ]

    try:
        msg = await message.answer("Запуск ракеты...")
        while not stop_event.is_set():
            current_multiplier += MULTIPLIER_STEP
            await state.update_data(multiplier=current_multiplier)

            if target_coeff and current_multiplier >= target_coeff:
                stop_event.set()
                await msg.edit_text(
                    f"🎉 Вы достигли целевого множителя x{current_multiplier:.2f}!\n"
                    f"💰 Выигрыш: {bet * current_multiplier:.2f}₽"
                )
                async with AsyncSessionLocal() as session:
                    user = (await session.execute(
                        select(User).where(User.tg_id == message.from_user.id)
                    )).scalar()
                    user.balance += bet * current_multiplier
                    await session.commit()
                await message.answer("Выберите следующую игру:", reply_markup=games_menu())
                await state.clear()
                break

            frame_index = int(current_multiplier * 10) % len(frames)
            frame = frames[frame_index]

            text = (
                f"{frame}\n"
                f"📈 Множитель: x{current_multiplier:.2f}\n"
                f"💰 Потенциальный выигрыш: {bet * current_multiplier:.2f}₽"
            )

            await msg.edit_text(
                text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text=f"🛑 Забрать {current_multiplier:.2f}x",
                        callback_data="cashout"
                    )]
                ])
            )

            if random.random() < CRASH_PROBABILITY:
                await msg.edit_text(f"💥 Ракета разбилась на x{current_multiplier:.2f}!")
                await message.answer("🍀 Повезет в следующий раз!🍀", reply_markup=games_menu())
                await state.clear()
                return

            await asyncio.sleep(UPDATE_INTERVAL)

    except asyncio.CancelledError:
        await msg.edit_text("✅ Игра завершена досрочно")
    finally:
        stop_event.set()

@router.message(F.text == "🚀Ракета🚀")
async def start_crash(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "💰 Введите сумму ставки (или '🔙 Назад' для отмены):",
        reply_markup=bet_kb()
    )
    await state.set_state(CrashStates.BET)

@router.message(CrashStates.BET, F.text == "🔙 Назад")
async def cancel_bet(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Игра отменена",
        reply_markup=games_menu()
    )

@router.message(CrashStates.BET)
async def process_bet(message: Message, state: FSMContext):
    if message.text == "🔙 Назад":
        await cancel_bet(message, state)
        return

    try:
        bet = float(message.text.replace("₽", "").strip())
        if bet <= 0:
            await state.clear()
            await message.answer(
                "❌ Ставка должна быть больше нуля! Игра отменена",
                reply_markup=games_menu()
            )
            return

        async with AsyncSessionLocal() as session:
            user = (await session.execute(
                select(User).where(User.tg_id == message.from_user.id)
            )).scalar()

            if user.balance < bet:
                await state.clear()
                await message.answer(
                    "❌ Недостаточно средств! Игра отменена",
                    reply_markup=games_menu()
                )
                return

            user.balance -= bet
            await session.commit()

            await state.update_data(bet=bet)
            await state.set_state(CrashStates.COEFF_INPUT)

            await message.answer(
                "Введите целевой множитель (например: 1.5, 2.0, 3.2, 5.0) или '🔙 Назад' для отмены:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="Примеры: 1.5 | 2.0 | 3.2", callback_data="example")
                ]])
            )

    except ValueError:
        await state.clear()
        await message.answer(
            "❌ Некорректная сумма! Игра отменена",
            reply_markup=games_menu()
        )

@router.message(CrashStates.COEFF_INPUT, F.text == "🔙 Назад")
async def cancel_coeff_input(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Игра отменена",
        reply_markup=games_menu()
    )

@router.message(CrashStates.COEFF_INPUT)
async def process_coeff(message: Message, state: FSMContext):
    if message.text == "🔙 Назад":
        await cancel_coeff_input(message, state)
        return

    try:
        target_coeff = float(message.text.strip())
        if target_coeff <= 1.0:
            await state.clear()
            await message.answer(
                "❌ Коэффициент должен быть больше 1.0! Игра отменена",
                reply_markup=games_menu()
            )
            return

        await state.update_data(
            target_coeff=target_coeff,
            multiplier=BASE_MULTIPLIER
        )
        await state.set_state(CrashStates.FLYING)

        stop_event = asyncio.Event()
        await state.update_data(stop_event=stop_event)

        await rocket_animation(message, state, stop_event)

    except ValueError:
        await state.clear()
        await message.answer(
            "❌ Некорректный коэффициент! Игра отменена",
            reply_markup=games_menu()
        )

@router.callback_query(CrashStates.FLYING, F.data == "cashout")
async def cashout_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    data['stop_event'].set()

    multiplier = data['multiplier']
    bet = data['bet']
    win_amount = bet * multiplier

    async with AsyncSessionLocal() as session:
        user = (await session.execute(
            select(User).where(User.tg_id == callback.from_user.id)
        )).scalar()
        user.balance += win_amount
        await session.commit()

    await callback.message.edit_text(
        f"🎉 Успешный кэшаут!\n"
        f"🏆 Множитель: x{multiplier:.2f}\n"
        f"💰 Выигрыш: {win_amount:.2f}₽\n"
        f"💵 Текущий баланс: {user.balance:.2f}₽",
        reply_markup=None
    )
    await callback.message.answer("Выберите следующую игру:", reply_markup=games_menu())
    await state.clear()
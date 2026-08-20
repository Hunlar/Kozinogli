# bot/handlers/games/mines.py
import random
import asyncio
from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from db.database import AsyncSessionLocal
from db.models import User
from sqlalchemy import select
from bot.keyboards import games_menu, mines_keyboard, bet_kb

router = Router()

class MinesStates(StatesGroup):
    CHOOSE_BET = State()
    CHOOSE_MINES = State()
    PLAYING = State()

# Конфигурация
GRID_SIZE = 5
EMOJI_HIDDEN = "🟦"
EMOJI_MINE = "💣"
EMOJI_SAFE = "🟩"
BASE_MULTIPLIER = 1.05

async def generate_grid(mines: int) -> tuple[list, list]:
    cells = [EMOJI_MINE] * mines + [EMOJI_SAFE] * (GRID_SIZE * GRID_SIZE - mines)
    random.shuffle(cells)
    grid = [cells[i * GRID_SIZE:(i + 1) * GRID_SIZE] for i in range(GRID_SIZE)]
    return grid, [[False for _ in row] for row in grid]

@router.message(F.text == "💣Мины💣")
async def start_mines(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "💰 Введите сумму ставки (или '🔙 Назад' для отмены):",
        reply_markup=bet_kb()
    )
    await state.set_state(MinesStates.CHOOSE_BET)

@router.message(MinesStates.CHOOSE_BET, F.text == "🔙 Назад")
async def cancel_bet(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Игра отменена",
        reply_markup=games_menu()
    )

@router.message(MinesStates.CHOOSE_BET)
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
            user = await session.execute(select(User).where(User.tg_id == message.from_user.id))
            user = user.scalar()

            if user.balance < bet:
                await state.clear()
                await message.answer(
                    "❌ Недостаточно средств! Игра отменена",
                    reply_markup=games_menu()
                )
                return

            user.balance -= bet
            await session.commit()
            await state.update_data(bet=bet, balance=user.balance)

            await message.answer(
                "💣 Выберите количество мин (3-10) или '🔙 Назад' для отмены:",
                reply_markup=mines_keyboard()
            )
            await state.set_state(MinesStates.CHOOSE_MINES)

    except ValueError:
        await state.clear()
        await message.answer(
            "❌ Некорректная сумма! Игра отменена",
            reply_markup=games_menu()
        )

@router.message(MinesStates.CHOOSE_MINES, F.text == "🔙 Назад")
async def cancel_mines_count(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Игра отменена",
        reply_markup=games_menu()
    )

@router.message(MinesStates.CHOOSE_MINES)
async def process_mines_count(message: Message, state: FSMContext):
    try:
        mines = int(message.text)
        if mines < 3 or mines > 10:
            raise ValueError

        data = await state.get_data()
        grid, opened = await generate_grid(mines)

        await state.update_data(
            grid=grid,
            opened=opened,
            mines=mines,
            safe=0,
            multiplier=1.0,
            won=0.0
        )

        text = (
            f"💣 Игра началась! Мины: {mines}\n"
            f"💵 Ставка: {data['bet']} ₽\n"
            f"📈 Множитель: x{1.0:.2f}\n"
            f"💰 Возможный выигрыш: {data['bet'] * 1.0:.2f} ₽"
        )

        await message.answer(
            text,
            reply_markup=await render_grid(opened, True)
        )
        await state.set_state(MinesStates.PLAYING)

    except ValueError:
        await state.clear()
        await message.answer(
            "❌ Некорректное количество мин! Игра отменена",
            reply_markup=games_menu()
        )

async def render_grid(opened: list, show_controls: bool) -> InlineKeyboardMarkup:
    buttons = []
    for i, row in enumerate(opened):
        button_row = []
        for j, cell in enumerate(row):
            text = EMOJI_HIDDEN if not cell else "🟨"
            button_row.append(InlineKeyboardButton(
                text=text,
                callback_data=f"{i}_{j}"
            ))
        buttons.append(button_row)

    if show_controls:
        buttons.append([
            InlineKeyboardButton(text="🏃 Забрать выигрыш", callback_data="cashout")
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def cashout(callback: CallbackQuery, state: FSMContext, data: dict):
    async with AsyncSessionLocal() as session:
        user = await session.execute(select(User).where(User.tg_id == callback.from_user.id))
        user = user.scalar()
        user.balance += data['won']
        await session.commit()

    grid = data['grid']
    opened = data['opened']
    await callback.message.edit_reply_markup(reply_markup=await reveal_grid(grid, opened))

    await callback.message.answer(
        f"🏆 Вы выиграли: {data['won']:.2f} ₽\n"
        f"💵 Новый баланс: {user.balance:.2f} ₽",
        reply_markup=games_menu()
    )
    await state.clear()

@router.callback_query(MinesStates.PLAYING)
async def process_cell_click(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    grid = data["grid"]
    opened = data["opened"]
    mines = data["mines"]
    safe = data["safe"]
    bet = data["bet"]
    multiplier = data["multiplier"]

    if callback.data == "cashout":
        await cashout(callback, state, data)
        return

    row, col = map(int, callback.data.split("_"))

    if opened[row][col]:
        return

    # Анимация открытия
    for i in range(3):
        await callback.message.edit_text(
            f"💣 Открываем клетку...\n{'🎇' * (i + 1)}",
            reply_markup=callback.message.reply_markup
        )
        await asyncio.sleep(0.3)

    if grid[row][col] == EMOJI_MINE:
        await show_game_over(callback, state, grid, opened, bet)
        return

    opened[row][col] = True
    safe += 1
    multiplier *= BASE_MULTIPLIER
    won = bet * multiplier

    await state.update_data(
        opened=opened,
        safe=safe,
        multiplier=multiplier,
        won=won
    )

    text = (
        f"💣 Осталось мин: {mines}\n"
        f"📈 Открыто клеток: {safe}\n"
        f"🎰 Множитель: x{multiplier:.2f}\n"
        f"💰 Текущий выигрыш: {won:.2f} ₽"
    )

    if safe == GRID_SIZE * GRID_SIZE - mines:
        await cashout(callback, state, data)
        return

    await callback.message.edit_text(
        text,
        reply_markup=await render_grid(opened, True)
    )

async def show_game_over(callback: CallbackQuery, state: FSMContext, grid: list, opened: list, bet: float):
    async with AsyncSessionLocal() as session:
        user = await session.execute(select(User).where(User.tg_id == callback.from_user.id))
        user = user.scalar()
        await session.commit()

    await callback.message.edit_reply_markup(reply_markup=await reveal_grid(grid, opened))

    await callback.message.answer(
        f"💥 Вы нашли мину! Игра окончена.\n"
        f"💸 Потеряно: {bet:.2f} ₽\n"
        f"💵 Текущий баланс: {user.balance:.2f} ₽",
        reply_markup=games_menu()
    )
    await state.clear()

async def reveal_grid(grid: list, opened: list) -> InlineKeyboardMarkup:
    buttons = []
    for i, row in enumerate(grid):
        button_row = []
        for j, cell in enumerate(row):
            text = cell if opened[i][j] else cell
            button_row.append(InlineKeyboardButton(text=text, callback_data=" "))
        buttons.append(button_row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)
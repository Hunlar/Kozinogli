
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

from sqlalchemy import select

from db.database import AsyncSessionLocal
from db.models import User

from bot.keyboards import games_menu, mines_keyboard, bet_kb
from bot.utils.bankruptcy import check_bankruptcy


router = Router()


class MinesStates(StatesGroup):
    CHOOSE_BET = State()
    CHOOSE_MINES = State()
    PLAYING = State()


GRID_SIZE = 5

EMOJI_HIDDEN = "🟦"
EMOJI_MINE = "💣"
EMOJI_SAFE = "🟩"

BASE_MULTIPLIER = 1.25


async def generate_grid(mines: int):
    cells = (
        [EMOJI_MINE] * mines
        + [EMOJI_SAFE] * (GRID_SIZE * GRID_SIZE - mines)
    )

    random.shuffle(cells)

    grid = [
        cells[i * GRID_SIZE:(i + 1) * GRID_SIZE]
        for i in range(GRID_SIZE)
    ]

    opened = [
        [False] * GRID_SIZE
        for _ in range(GRID_SIZE)
    ]

    return grid, opened


@router.message(F.text == "💣 Mayınlar")
async def start_mines(message: Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "💣 **Mayınlar**\n\n"
        "🪙 Bahis miktarını gir:",
        reply_markup=bet_kb(),
        parse_mode="Markdown"
    )

    await state.set_state(MinesStates.CHOOSE_BET)


@router.message(
    MinesStates.CHOOSE_BET,
    F.text == "🔙 Geri"
)
async def cancel_bet(message: Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "Oyun iptal edildi.",
        reply_markup=games_menu()
    )


@router.message(MinesStates.CHOOSE_BET)
async def process_bet(message: Message, state: FSMContext):

    try:
        bet = float(
            message.text.replace(",", ".").strip()
        )

        if bet <= 0:
            raise ValueError

    except (ValueError, AttributeError):
        await message.answer("❌ Geçersiz bahis miktarı.")
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

            return await message.answer(
                "❌ Kullanıcı hesabın bulunamadı.",
                reply_markup=games_menu()
            )

        balance = user.balance or 0

        if balance < bet:
            await state.clear()

            return await message.answer(
                "❌ Yeterli Sanal Kredin yok.",
                reply_markup=games_menu()
            )

        # Bahis mevcut sistemdeki gibi hemen düşülür.
        user.balance = balance - bet

        remaining_balance = user.balance

        await session.commit()

    await state.update_data(
        bet=bet,
        player_id=message.from_user.id,
        balance=remaining_balance
    )

    await message.answer(
        "💣 Kaç mayınla oynamak istiyorsun?",
        reply_markup=mines_keyboard()
    )

    await state.set_state(MinesStates.CHOOSE_MINES)


@router.message(
    MinesStates.CHOOSE_MINES,
    F.text == "🔙 Geri"
)
async def cancel_mines(message: Message, state: FSMContext):
    data = await state.get_data()

    # Mayın sayısı seçilmeden iptal edilirse bahis iade edilir.
    bet = data.get("bet", 0)

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(User)
            .where(User.tg_id == message.from_user.id)
            .with_for_update()
        )

        user = result.scalar_one_or_none()

        if user is not None:
            user.balance = (user.balance or 0) + bet
            await session.commit()

    await state.clear()

    await message.answer(
        "Oyun iptal edildi. Bahsin iade edildi.",
        reply_markup=games_menu()
    )


@router.message(MinesStates.CHOOSE_MINES)
async def process_mines_count(message: Message, state: FSMContext):

    try:
        mines = int(message.text)

        if not 3 <= mines <= 10:
            raise ValueError

    except (ValueError, TypeError):
        await message.answer(
            "❌ Mayın sayısı 3 ile 10 arasında olmalı."
        )
        return

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
        f"💣 Mayın sayısı: {mines}\n"
        f"🪙 Bahis: {data['bet']:,.2f} Sanal Kredi\n"
        f"📈 Çarpan: x1.00\n"
        f"💰 İlk güvenli seçimden sonraki ödeme: "
        f"{data['bet'] * BASE_MULTIPLIER:,.2f} Sanal Kredi\n\n"
        "🟦 Güvenli kareleri aç ve kazancını artır!"
    )

    await message.answer(
        text,
        reply_markup=await render_grid(opened)
    )

    await state.set_state(MinesStates.PLAYING)


async def render_grid(opened, show_controls=True):
    buttons = []

    for i, row in enumerate(opened):
        button_row = []

        for j, is_open in enumerate(row):
            text = "🟩" if is_open else EMOJI_HIDDEN

            button_row.append(
                InlineKeyboardButton(
                    text=text,
                    callback_data=f"{i}_{j}"
                )
            )

        buttons.append(button_row)

    if show_controls:
        buttons.append([
            InlineKeyboardButton(
                text="🏃 Kazancı Al",
                callback_data="cashout"
            )
        ])

    return InlineKeyboardMarkup(
        inline_keyboard=buttons
    )


async def reveal_grid(grid, opened):
    buttons = []

    for i, row in enumerate(grid):
        button_row = []

        for j, cell in enumerate(row):
            text = cell if opened[i][j] else EMOJI_HIDDEN

            button_row.append(
                InlineKeyboardButton(
                    text=text,
                    callback_data="mines_finished"
                )
            )

        buttons.append(button_row)

    return InlineKeyboardMarkup(
        inline_keyboard=buttons
    )


async def cashout(
    callback: CallbackQuery,
    state: FSMContext,
    data: dict
):
    if callback.from_user.id != data.get("player_id"):
        await callback.answer(
            "Bu oyun başka bir oyuncuya ait.",
            show_alert=True
        )
        return

    won = data.get("won", 0)

    if won <= 0:
        await callback.answer(
            "Henüz alabileceğin bir kazanç yok.",
            show_alert=True
        )
        return

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(User)
            .where(User.tg_id == callback.from_user.id)
            .with_for_update()
        )

        user = result.scalar_one_or_none()

        if user is None:
            await callback.answer(
                "Kullanıcı hesabı bulunamadı.",
                show_alert=True
            )
            return

        user.balance = (user.balance or 0) + won

        final_balance = user.balance

        await session.commit()

    grid = data["grid"]
    opened = data["opened"]

    # Oyun bittiğinde bütün mayınlar gösterilir.
    for i in range(GRID_SIZE):
        for j in range(GRID_SIZE):
            opened[i][j] = True

    try:
        await callback.message.edit_reply_markup(
            reply_markup=await reveal_grid(grid, opened)
        )
    except Exception:
        pass

    await state.clear()

    await check_bankruptcy(
        bot=callback.bot,
        telegram_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        chat_type=callback.message.chat.type,
        first_name=callback.from_user.first_name
    )

    await callback.message.answer(
        "🏆 **Kazancı aldın!**\n\n"
        f"🪙 Ödeme: {won:,.2f} Sanal Kredi\n"
        f"💰 Güncel bakiye: {final_balance:,.2f} Sanal Kredi",
        reply_markup=games_menu(),
        parse_mode="Markdown"
    )

    await callback.answer("Kazancın hesabına eklendi!")


@router.callback_query(MinesStates.PLAYING)
async def process_cell(
    callback: CallbackQuery,
    state: FSMContext
):

    data = await state.get_data()

    if not data:
        await callback.answer(
            "Oyun oturumu bulunamadı.",
            show_alert=True
        )
        return

    if callback.from_user.id != data.get("player_id"):
        await callback.answer(
            "Bu oyun başka bir oyuncuya ait.",
            show_alert=True
        )
        return

    if callback.data == "cashout":
        await cashout(callback, state, data)
        return

    try:
        row, col = map(int, callback.data.split("_"))

        if not (
            0 <= row < GRID_SIZE
            and 0 <= col < GRID_SIZE
        ):
            raise ValueError

    except (ValueError, AttributeError):
        await callback.answer("Geçersiz kare.")
        return

    grid = data["grid"]
    opened = data["opened"]
    mines = data["mines"]
    safe = data["safe"]
    bet = data["bet"]
    multiplier = data["multiplier"]

    if opened[row][col]:
        await callback.answer("Bu kare zaten açılmış.")
        return

    await callback.answer()

    # Açılma animasyonu.
    for i in range(3):
        try:
            await callback.message.edit_text(
                f"💣 Kare açılıyor... {'✨' * (i + 1)}",
                reply_markup=callback.message.reply_markup
            )

            await asyncio.sleep(0.2)

        except Exception:
            pass

    # Mayına basılırsa bahis kaybedilir.
    if grid[row][col] == EMOJI_MINE:

        await show_game_over(
            callback,
            state,
            grid,
            opened,
            bet
        )

        return

    # Güvenli kare.
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
        f"💣 Mayın: {mines}\n"
        f"🟩 Açılan güvenli kare: {safe}\n"
        f"📈 Çarpan: x{multiplier:.2f}\n"
        f"🪙 Alabileceğin ödeme: {won:,.2f} Sanal Kredi\n\n"
        "Devam edebilir veya kazancını alabilirsin."
    )

    # Bütün güvenli kareler açıldıysa otomatik ödeme.
    if safe == GRID_SIZE * GRID_SIZE - mines:
        await cashout(
            callback,
            state,
            await state.get_data()
        )
        return

    try:
        await callback.message.edit_text(
            text,
            reply_markup=await render_grid(opened)
        )
    except Exception:
        pass


async def show_game_over(
    callback: CallbackQuery,
    state: FSMContext,
    grid,
    opened,
    bet
):

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(User)
            .where(User.tg_id == callback.from_user.id)
        )

        user = result.scalar_one_or_none()

        balance = user.balance if user else 0

    # Tüm kareleri göster.
    for i in range(GRID_SIZE):
        for j in range(GRID_SIZE):
            opened[i][j] = True

    try:
        await callback.message.edit_reply_markup(
            reply_markup=await reveal_grid(grid, opened)
        )
    except Exception:
        pass

    await state.clear()

    # Bahis zaten düşüldüğü için burada tekrar düşülmez.
    await check_bankruptcy(
        bot=callback.bot,
        telegram_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        chat_type=callback.message.chat.type,
        first_name=callback.from_user.first_name
    )

    await callback.message.answer(
        "💥 **Mayına bastın!**\n\n"
        f"🪙 Kaybedilen bahis: {bet:,.2f} Sanal Kredi\n"
        f"💰 Güncel bakiye: {balance:,.2f} Sanal Kredi",
        reply_markup=games_menu(),
        parse_mode="Markdown"
    )

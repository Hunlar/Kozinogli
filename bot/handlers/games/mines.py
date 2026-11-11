
import random
import asyncio
import math

from aiogram import Router, F
from aiogram.filters import Command
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


@router.message(Command("mines"))
@router.message(F.text == "💣 Mayınlar")
async def start_mines(
    message: Message,
    state: FSMContext
):
    await state.clear()

    owner_id = message.from_user.id

    await state.update_data(
        player_id=owner_id
    )

    await message.answer(
        "💣 **Mayınlar**\n\n"
        "🪙 Bahis miktarını gir:\n\n"
        "İptal etmek için /iptal yaz.",
        parse_mode="Markdown"
    )

    await state.set_state(MinesStates.CHOOSE_BET)


@router.message(
    MinesStates.CHOOSE_BET,
    Command("iptal")
)
@router.message(
    MinesStates.CHOOSE_MINES,
    Command("iptal")
)
async def cancel_mines(
    message: Message,
    state: FSMContext
):
    data = await state.get_data()

    if data.get("player_id") != message.from_user.id:
        return

    bet = float(data.get("bet", 0) or 0)

    if bet > 0:
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
        "❌ Mayınlar oyunu iptal edildi."
        + (
            f"\n🪙 {bet:,.2f} Sanal Kredi iade edildi."
            if bet > 0 else ""
        )
    )


@router.message(MinesStates.CHOOSE_BET)
async def process_bet(
    message: Message,
    state: FSMContext
):
    data = await state.get_data()

    owner_id = data.get("player_id")

    if owner_id != message.from_user.id:
        return

    if not message.text:
        return await message.answer(
            "❌ Lütfen bahis miktarını sayı olarak gir."
        )

    try:
        bet = float(
            message.text.replace(",", ".").strip()
        )

        if not math.isfinite(bet) or bet <= 0:
            raise ValueError

    except (ValueError, AttributeError):
        return await message.answer(
            "❌ Geçerli ve pozitif bir bahis miktarı gir."
        )

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User)
            .where(User.tg_id == owner_id)
            .with_for_update()
        )

        user = result.scalar_one_or_none()

        if user is None:
            await state.clear()

            return await message.answer(
                "❌ Kullanıcı hesabın bulunamadı."
            )

        balance = user.balance or 0

        if balance < bet:
            await state.clear()

            return await message.answer(
                "❌ Yeterli Sanal Kredin yok."
            )

        user.balance = balance - bet

        await session.commit()

    await state.update_data(
        bet=bet,
        player_id=owner_id
    )

    await message.answer(
        "💣 Kaç mayınla oynamak istiyorsun?\n\n"
        "3 ile 10 arasında bir sayı yaz.\n"
        "İptal etmek için /iptal yaz."
    )

    await state.set_state(MinesStates.CHOOSE_MINES)


@router.message(MinesStates.CHOOSE_MINES)
async def process_mines_count(
    message: Message,
    state: FSMContext
):
    data = await state.get_data()

    owner_id = data.get("player_id")

    if owner_id != message.from_user.id:
        return

    try:
        mines = int(message.text.strip())

        if not 3 <= mines <= 10:
            raise ValueError

    except (ValueError, TypeError, AttributeError):
        return await message.answer(
            "❌ Mayın sayısı 3 ile 10 arasında olmalı."
        )

    grid, opened = await generate_grid(mines)

    await state.update_data(
        grid=grid,
        opened=opened,
        mines=mines,
        safe=0,
        multiplier=1.0,
        won=0.0
    )

    bet = data["bet"]

    text = (
        f"💣 Mayın sayısı: {mines}\n"
        f"🪙 Bahis: {bet:,.2f} Sanal Kredi\n"
        f"📈 Çarpan: x1.00\n"
        f"💰 İlk güvenli seçimden sonraki ödeme: "
        f"{bet * BASE_MULTIPLIER:,.2f} Sanal Kredi\n\n"
        "🟦 Güvenli kareleri aç ve kazancını artır!"
    )

    msg = await message.answer(
        text,
        reply_markup=await render_grid(
            opened,
            owner_id
        )
    )

    await state.update_data(
        message_id=msg.message_id
    )

    await state.set_state(MinesStates.PLAYING)


async def render_grid(
    opened,
    owner_id: int,
    show_controls=True
):
    buttons = []

    for i, row in enumerate(opened):
        button_row = []

        for j, is_open in enumerate(row):
            text = "🟩" if is_open else EMOJI_HIDDEN

            button_row.append(
                InlineKeyboardButton(
                    text=text,
                    callback_data=f"mines:{owner_id}:{i}:{j}"
                )
            )

        buttons.append(button_row)

    if show_controls:
        buttons.append([
            InlineKeyboardButton(
                text="🏃 Kazancı Al",
                callback_data=f"mines_cashout:{owner_id}"
            )
        ])

    return InlineKeyboardMarkup(
        inline_keyboard=buttons
    )


async def reveal_grid(
    grid,
    opened,
    owner_id: int
):
    buttons = []

    for i, row in enumerate(grid):
        button_row = []

        for j, cell in enumerate(row):
            text = cell if opened[i][j] else EMOJI_HIDDEN

            button_row.append(
                InlineKeyboardButton(
                    text=text,
                    callback_data=f"mines_finished:{owner_id}"
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
    owner_id = data.get("player_id")

    if callback.from_user.id != owner_id:
        return await callback.answer(
            "Bu oyun başka bir oyuncuya ait.",
            show_alert=True
        )

    won = data.get("won", 0)

    if won <= 0:
        return await callback.answer(
            "Henüz alabileceğin bir kazanç yok.",
            show_alert=True
        )

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User)
            .where(User.tg_id == owner_id)
            .with_for_update()
        )

        user = result.scalar_one_or_none()

        if user is None:
            return await callback.answer(
                "Kullanıcı hesabı bulunamadı.",
                show_alert=True
            )

        user.balance = (user.balance or 0) + won

        final_balance = user.balance

        await session.commit()

    grid = data["grid"]
    opened = data["opened"]

    for i in range(GRID_SIZE):
        for j in range(GRID_SIZE):
            opened[i][j] = True

    try:
        await callback.message.edit_reply_markup(
            reply_markup=await reveal_grid(
                grid,
                opened,
                owner_id
            )
        )
    except Exception:
        pass

    await state.clear()

    await check_bankruptcy(
        bot=callback.bot,
        telegram_id=owner_id,
        chat_id=callback.message.chat.id,
        chat_type=callback.message.chat.type,
        first_name=callback.from_user.first_name
    )

    await callback.message.answer(
        "🏆 **Kazancı aldın!**\n\n"
        f"🪙 Ödeme: {won:,.2f} Sanal Kredi\n"
        f"💰 Güncel bakiye: {final_balance:,.2f} Sanal Kredi",
        parse_mode="Markdown"
    )

    await callback.answer(
        "Kazancın hesabına eklendi!"
    )


@router.callback_query(MinesStates.PLAYING)
async def process_cell(
    callback: CallbackQuery,
    state: FSMContext
):
    data = await state.get_data()

    if not data:
        return await callback.answer(
            "Oyun oturumu bulunamadı.",
            show_alert=True
        )

    owner_id = data.get("player_id")

    if callback.from_user.id != owner_id:
        return await callback.answer(
            "Bu oyun başka bir oyuncuya ait.",
            show_alert=True
        )

    if not callback.message:
        return await callback.answer(
            "Oyun mesajına ulaşılamadı.",
            show_alert=True
        )

    if callback.message.message_id != data.get("message_id"):
        return await callback.answer(
            "Bu oyun mesajı artık geçerli değil.",
            show_alert=True
        )

    if callback.data == f"mines_cashout:{owner_id}":
        await cashout(callback, state, data)
        return

    if callback.data == f"mines_finished:{owner_id}":
        return await callback.answer(
            "Bu oyun tamamlandı.",
            show_alert=True
        )

    try:
        parts = callback.data.split(":")

        if len(parts) != 4 or parts[0] != "mines":
            raise ValueError

        callback_owner = int(parts[1])
        row = int(parts[2])
        col = int(parts[3])

        if callback_owner != owner_id:
            raise ValueError

        if not (
            0 <= row < GRID_SIZE
            and 0 <= col < GRID_SIZE
        ):
            raise ValueError

    except (ValueError, AttributeError):
        return await callback.answer(
            "Geçersiz kare.",
            show_alert=True
        )

    grid = data["grid"]
    opened = data["opened"]
    mines = data["mines"]
    safe = data["safe"]
    bet = data["bet"]
    multiplier = data["multiplier"]

    if opened[row][col]:
        return await callback.answer(
            "Bu kare zaten açılmış."
        )

    await callback.answer()

    for i in range(3):
        try:
            await callback.message.edit_text(
                f"💣 Kare açılıyor... {'✨' * (i + 1)}",
                reply_markup=callback.message.reply_markup
            )

            await asyncio.sleep(0.2)

        except Exception:
            pass

    if grid[row][col] == EMOJI_MINE:
        await show_game_over(
            callback,
            state,
            grid,
            opened,
            bet,
            owner_id
        )
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
        f"💣 Mayın: {mines}\n"
        f"🟩 Açılan güvenli kare: {safe}\n"
        f"📈 Çarpan: x{multiplier:.2f}\n"
        f"🪙 Alabileceğin ödeme: {won:,.2f} Sanal Kredi\n\n"
        "Devam edebilir veya kazancını alabilirsin."
    )

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
            reply_markup=await render_grid(
                opened,
                owner_id
            )
        )
    except Exception:
        pass


async def show_game_over(
    callback: CallbackQuery,
    state: FSMContext,
    grid,
    opened,
    bet,
    owner_id
):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User)
            .where(User.tg_id == owner_id)
        )

        user = result.scalar_one_or_none()

        balance = user.balance if user else 0

    for i in range(GRID_SIZE):
        for j in range(GRID_SIZE):
            opened[i][j] = True

    try:
        await callback.message.edit_reply_markup(
            reply_markup=await reveal_grid(
                grid,
                opened,
                owner_id
            )
        )
    except Exception:
        pass

    await state.clear()

    await check_bankruptcy(
        bot=callback.bot,
        telegram_id=owner_id,
        chat_id=callback.message.chat.id,
        chat_type=callback.message.chat.type,
        first_name=callback.from_user.first_name
    )

    await callback.message.answer(
        "💥 **Mayına bastın!**\n\n"
        f"🪙 Kaybedilen bahis: {bet:,.2f} Sanal Kredi\n"
        f"💰 Güncel bakiye: {balance:,.2f} Sanal Kredi",
        parse_mode="Markdown"
        )
    

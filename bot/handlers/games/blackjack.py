# bot/handlers/games/blackjack.py
import random
import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from db.database import AsyncSessionLocal
from db.models import User
from sqlalchemy import select
from bot.keyboards import games_menu, bet_kb

router = Router()

class BlackjackStates(StatesGroup):
    BET = State()
    PLAYER_TURN = State()

# Эмодзи для карт
CARD_EMOJIS = {
    '♠': '♠️', '♥': '♥️', '♦': '♦️', '♣': '♣️',
    'J': '🃏', 'Q': '👑', 'K': '🤴', 'A': '🅰️'
}

def get_card_emoji(card: tuple) -> str:
    value, suit = card[0][:-1], card[0][-1]
    emoji_value = CARD_EMOJIS.get(value, value)
    return f"{emoji_value}{CARD_EMOJIS[suit]}"

async def calculate_hand(hand: list) -> int:
    total = sum(card[1] for card in hand)
    aces = sum(1 for card in hand if card[0].startswith('A'))

    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total

def create_deck():
    deck = [
        (f"{value}{suit}", 11 if value == 'A' else 10 if value in ('J', 'Q', 'K') else int(value))
        for value in ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        for suit in ['♠', '♥', '♦', '♣']
    ] * 4
    random.shuffle(deck)
    return deck

async def render_hand(hand: list, hide_second: bool = False) -> str:
    parts = []
    if len(hand) >= 1:
        parts.append(get_card_emoji(hand[0]))
    if len(hand) >= 2:
        if hide_second:
            parts.append('🂠')
        else:
            parts.append(get_card_emoji(hand[1]))
    for card in hand[2:]:
        parts.append(get_card_emoji(card))
    return ' '.join(parts)

@router.message(F.text == "🃏Blackjack🃏")
async def start_blackjack(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "💰 Сделайте ставку (или '🔙 Назад' для отмены):",
        reply_markup=bet_kb()
    )
    await state.set_state(BlackjackStates.BET)

@router.message(BlackjackStates.BET, F.text == "🔙 Назад")
async def cancel_bet(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Ставка отменена",
        reply_markup=games_menu()
    )

@router.message(BlackjackStates.BET)
async def process_bet(message: Message, state: FSMContext):
    # Обработка кнопки "Назад"
    if message.text == "🔙 Назад":
        await cancel_bet(message, state)
        return

    # Проверка на число
    try:
        bet = float(message.text.replace("₽", "").strip())
        if bet <= 0:
            await state.clear()
            await message.answer(
                "❌ Ставка должна быть больше нуля! Игра отменена",
                reply_markup=games_menu()
            )
            return
    except ValueError:
        await state.clear()
        await message.answer(
            "❌ Некорректная сумма! Игра отменена",
            reply_markup=games_menu()
        )
        return

    # Проверка баланса
    async with AsyncSessionLocal() as session:
        user = (await session.execute(select(User).where(User.tg_id == message.from_user.id))).scalar()

        if not user:
            await state.clear()
            await message.answer("❌ Вы не зарегистрированы!", reply_markup=games_menu())
            return

        if user.balance < bet:
            await state.clear()
            await message.answer(
                "❌ Недостаточно средств! Игра отменена",
                reply_markup=games_menu()
            )
            return

        deck = create_deck()
        player_hand = [deck.pop(), deck.pop()]
        dealer_hand = [deck.pop(), deck.pop()]

        await state.update_data(
            bet=bet,
            player_hand=player_hand,
            dealer_hand=dealer_hand,
            deck=deck,
            message_id=None
        )

        player_total = await calculate_hand(player_hand)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Взять карту", callback_data="hit")],
            [InlineKeyboardButton(text="⛔ Остановиться", callback_data="stand")]
        ])

        msg = await message.answer(
            f"🃏 Ваши карты:\n{await render_hand(player_hand)}\n"
            f"➖ Сумма: {player_total}\n\n"
            f"💼 Карта дилера:\n{await render_hand(dealer_hand, hide_second=True)}",
            reply_markup=keyboard
        )
        await state.update_data(message_id=msg.message_id)
        await state.set_state(BlackjackStates.PLAYER_TURN)

@router.callback_query(BlackjackStates.PLAYER_TURN, F.data.in_(["hit", "stand"]))
async def player_action(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    player_hand = data["player_hand"]
    deck = data["deck"]

    if callback.data == "hit":
        player_hand.append(deck.pop())
        await state.update_data(player_hand=player_hand, deck=deck)

        player_total = await calculate_hand(player_hand)
        if player_total > 21:
            await end_game(callback, state, busted=True)
            return

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Взять карту", callback_data="hit")],
            [InlineKeyboardButton(text="⛔ Остановиться", callback_data="stand")]
        ])

        await callback.message.edit_text(
            f"🃏 Ваши карты:\n{await render_hand(player_hand)}\n"
            f"➖ Сумма: {player_total}\n\n"
            f"💼 Карта дилера:\n{await render_hand(data['dealer_hand'], hide_second=True)}",
            reply_markup=keyboard
        )
    else:
        dealer_hand = data["dealer_hand"]
        dealer_total = await calculate_hand(dealer_hand)

        while dealer_total < 17:
            dealer_hand.append(deck.pop())
            dealer_total = await calculate_hand(dealer_hand)

        await state.update_data(dealer_hand=dealer_hand)
        await end_game(callback, state)

async def end_game(callback: CallbackQuery, state: FSMContext, busted: bool = False):
    data = await state.get_data()
    player_hand = data["player_hand"]
    dealer_hand = data["dealer_hand"]
    bet = data["bet"]

    player_total = await calculate_hand(player_hand)
    dealer_total = await calculate_hand(dealer_hand)

    result = ""
    payout = 0

    if busted:
        result = "💥 Перебор! Дилер побеждает"
        payout = -bet
    elif dealer_total > 21:
        result = "🎉 Дилер перебрал! Вы победили"
        payout = bet * 1.5
    elif player_total > dealer_total:
        result = "🎉 Вы победили!"
        payout = bet * 1.5
    elif player_total < dealer_total:
        result = "💼 Дилер побеждает"
        payout = -bet
    else:
        result = "🤝 Ничья!"
        payout = 0

    async with AsyncSessionLocal() as session:
        user = (await session.execute(select(User).where(User.tg_id == callback.from_user.id))).scalar()
        user.balance += payout
        await session.commit()

    # Анимация открытия карт дилера
    revealed_cards = []
    for i in range(len(dealer_hand)):
        revealed_cards = dealer_hand[:i + 1]
        await callback.message.edit_text(
            f"💼 Карты дилера:\n{await render_hand(revealed_cards)}\n"
            f"➖ Сумма: {await calculate_hand(revealed_cards) if i > 0 else '?'}\n\n"
            f"🃏 Ваши карты:\n{await render_hand(player_hand)}\n"
            f"➖ Сумма: {player_total}"
        )
        await asyncio.sleep(0.8)

    await callback.message.edit_text(
        f"{result}\n\n"
        f"💼 Карты дилера:\n{await render_hand(dealer_hand)}\n"
        f"➖ Сумма: {dealer_total}\n\n"
        f"🃏 Ваши карты:\n{await render_hand(player_hand)}\n"
        f"➖ Сумма: {player_total}\n\n"
        f"💵 Изменение баланса: {payout:.2f} ₽\n"
        f"💰 Текущий баланс: {user.balance:.2f} ₽",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Играть снова", callback_data="restart")]
        ])
    )
    await state.clear()

@router.callback_query(F.data == "restart")
async def restart_game(callback: CallbackQuery, state: FSMContext):
    await start_blackjack(callback.message, state)

import random
import asyncio

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from sqlalchemy import select

from db.database import AsyncSessionLocal
from db.models import User

from bot.keyboards import games_menu, bet_kb
from bot.utils.bankruptcy import check_bankruptcy


router = Router()


class BlackjackStates(StatesGroup):
    BET = State()
    PLAYER_TURN = State()


CARD_EMOJIS = {
    "♠": "♠️",
    "♥": "♥️",
    "♦": "♦️",
    "♣": "♣️",
    "J": "🃏",
    "Q": "👑",
    "K": "🤴",
    "A": "🅰️"
}


def get_card_emoji(card: tuple) -> str:
    value, suit = card[0][:-1], card[0][-1]

    emoji_value = CARD_EMOJIS.get(value, value)

    return f"{emoji_value}{CARD_EMOJIS[suit]}"


async def calculate_hand(hand: list) -> int:
    total = sum(card[1] for card in hand)

    aces = sum(
        1 for card in hand
        if card[0].startswith("A")
    )

    while total > 21 and aces > 0:
        total -= 10
        aces -= 1

    return total


def create_deck():
    deck = [
        (
            f"{value}{suit}",
            11 if value == "A"
            else 10 if value in ("J", "Q", "K")
            else int(value)
        )
        for value in [
            "2", "3", "4", "5", "6", "7",
            "8", "9", "10", "J", "Q", "K", "A"
        ]
        for suit in ["♠", "♥", "♦", "♣"]
    ] * 4

    random.shuffle(deck)

    return deck


async def render_hand(hand: list, hide_second: bool = False) -> str:
    parts = []

    if len(hand) >= 1:
        parts.append(get_card_emoji(hand[0]))

    if len(hand) >= 2:
        parts.append(
            "🂠" if hide_second
            else get_card_emoji(hand[1])
        )

    for card in hand[2:]:
        parts.append(get_card_emoji(card))

    return " ".join(parts)


def blackjack_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Kart Çek",
                    callback_data="hit"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⛔ Dur",
                    callback_data="stand"
                )
            ]
        ]
    )


def restart_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Tekrar Oyna",
                    callback_data="bj_restart"
                )
            ]
        ]
    )


@router.message(F.text == "🃏 Blackjack")
async def start_blackjack(message: Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "🃏 **Blackjack**\n\n"
        "🪙 Oynamak istediğin bahis miktarını gir:",
        reply_markup=bet_kb(),
        parse_mode="Markdown"
    )

    await state.set_state(BlackjackStates.BET)


@router.message(
    BlackjackStates.BET,
    F.text == "🔙 Geri"
)
async def cancel_bet(message: Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "Oyun iptal edildi.",
        reply_markup=games_menu()
    )


@router.message(BlackjackStates.BET)
async def process_bet(message: Message, state: FSMContext):

    try:
        bet = float(
            message.text.replace(",", ".").strip()
        )

        if bet <= 0:
            raise ValueError

    except (ValueError, AttributeError):
        return await message.answer(
            "❌ Geçersiz bahis miktarı. Tekrar dene."
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

        # Bahis bakiyeden düşülür.
        user.balance = balance - bet

        await session.commit()

    # Kartlar dağıtılır.
    deck = create_deck()

    player_hand = [
        deck.pop(),
        deck.pop()
    ]

    dealer_hand = [
        deck.pop(),
        deck.pop()
    ]

    await state.update_data(
        bet=bet,
        player_hand=player_hand,
        dealer_hand=dealer_hand,
        deck=deck
    )

    player_total = await calculate_hand(player_hand)

    # İlk elde Blackjack kontrolü.
    if player_total == 21:
        await end_game(
            message,
            state,
            instant_blackjack=True
        )
        return

    msg = await message.answer(
        f"🃏 **Kartların:**\n"
        f"{await render_hand(player_hand)}\n"
        f"➖ Toplam: {player_total}\n\n"
        f"💼 **Dağıtıcının kartları:**\n"
        f"{await render_hand(dealer_hand, hide_second=True)}",
        reply_markup=blackjack_keyboard(),
        parse_mode="Markdown"
    )

    await state.update_data(
        message_id=msg.message_id
    )

    await state.set_state(
        BlackjackStates.PLAYER_TURN
    )


@router.callback_query(
    BlackjackStates.PLAYER_TURN,
    F.data.in_(["hit", "stand"])
)
async def player_action(
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

    player_hand = data["player_hand"]
    dealer_hand = data["dealer_hand"]
    deck = data["deck"]

    if callback.data == "hit":

        if not deck:
            await callback.answer(
                "Kart destesi tükendi.",
                show_alert=True
            )
            return

        player_hand.append(deck.pop())

        await state.update_data(
            player_hand=player_hand,
            deck=deck
        )

        player_total = await calculate_hand(player_hand)

        if player_total > 21:
            await callback.answer()

            await end_game(
                callback,
                state,
                busted=True
            )
            return

        await callback.message.edit_text(
            f"🃏 **Kartların:**\n"
            f"{await render_hand(player_hand)}\n"
            f"➖ Toplam: {player_total}\n\n"
            f"💼 **Dağıtıcının kartları:**\n"
            f"{await render_hand(dealer_hand, hide_second=True)}",
            reply_markup=blackjack_keyboard(),
            parse_mode="Markdown"
        )

        await callback.answer()

    else:

        dealer_total = await calculate_hand(dealer_hand)

        while dealer_total < 17 and deck:
            dealer_hand.append(deck.pop())
            dealer_total = await calculate_hand(dealer_hand)

        await state.update_data(
            dealer_hand=dealer_hand,
            deck=deck
        )

        await callback.answer()

        await end_game(
            callback,
            state
        )


async def end_game(
    event,
    state: FSMContext,
    busted: bool = False,
    instant_blackjack: bool = False
):

    data = await state.get_data()

    if not data:
        await state.clear()
        return

    player_hand = data["player_hand"]
    dealer_hand = data["dealer_hand"]
    bet = data["bet"]

    player_total = await calculate_hand(player_hand)
    dealer_total = await calculate_hand(dealer_hand)

    if instant_blackjack:
        result = "🎉 BLACKJACK! x2,5 ödeme!"
        payout = bet * 2.5

    elif busted:
        result = "💥 21'i aştın! Bahsi kaybettin."
        payout = 0

    elif dealer_total > 21:
        result = "🎉 Dağıtıcı 21'i aştı! Kazandın."
        payout = bet * 2

    elif player_total > dealer_total:
        result = "🎉 Kazandın!"
        payout = bet * 2

    elif player_total < dealer_total:
        result = "💼 Dağıtıcı kazandı."
        payout = 0

    else:
        result = "🤝 Berabere! Bahsin iade edildi."
        payout = bet

    # Kazanç veya iade bakiyeye eklenir.
    async with AsyncSessionLocal() as session:

        db_result = await session.execute(
            select(User)
            .where(User.tg_id == event.from_user.id)
            .with_for_update()
        )

        user = db_result.scalar_one_or_none()

        if user is None:
            await state.clear()

            if isinstance(event, CallbackQuery):
                await event.message.answer(
                    "❌ Kullanıcı hesabına ulaşılamadı."
                )
            else:
                await event.answer(
                    "❌ Kullanıcı hesabına ulaşılamadı."
                )

            return

        user.balance = (user.balance or 0) + payout

        final_balance = user.balance

        await session.commit()

    # Oyun sonucunu göstereceğimiz mesaj.
    if isinstance(event, CallbackQuery):
        target_message = event.message

        # Dağıtıcının kartlarını açma animasyonu.
        if not instant_blackjack:

            for i in range(len(dealer_hand)):

                revealed = dealer_hand[:i + 1]

                try:
                    await target_message.edit_text(
                        f"💼 **Dağıtıcının kartları:**\n"
                        f"{await render_hand(revealed)}\n"
                        f"➖ Toplam: "
                        f"{await calculate_hand(revealed)}\n\n"
                        f"🃏 **Senin kartların:**\n"
                        f"{await render_hand(player_hand)}\n"
                        f"➖ Toplam: {player_total}",
                        parse_mode="Markdown"
                    )

                    await asyncio.sleep(0.8)

                except Exception:
                    pass

    else:
        target_message = None

    await state.clear()

    # İflas kontrolü ve gerekiyorsa grup duyurusu.
    await check_bankruptcy(
        bot=event.bot,
        telegram_id=event.from_user.id,
        chat_id=event.chat.id if isinstance(event, Message)
        else event.message.chat.id,
        chat_type=event.chat.type if isinstance(event, Message)
        else event.message.chat.type,
        first_name=event.from_user.first_name
    )

    final_text = (
        f"{result}\n\n"
        f"💼 **Dağıtıcının kartları:**\n"
        f"{await render_hand(dealer_hand)}\n"
        f"➖ Toplam: {dealer_total}\n\n"
        f"🃏 **Senin kartların:**\n"
        f"{await render_hand(player_hand)}\n"
        f"➖ Toplam: {player_total}\n\n"
        f"🪙 Ödeme: {payout:,.2f} Sanal Kredi\n"
        f"💰 Güncel bakiye: {final_balance:,.2f} Sanal Kredi"
    )

    if target_message is not None:

        try:
            await target_message.edit_text(
                final_text,
                reply_markup=restart_keyboard(),
                parse_mode="Markdown"
            )

        except Exception:
            await target_message.answer(
                final_text,
                reply_markup=restart_keyboard(),
                parse_mode="Markdown"
            )

    else:
        await event.answer(
            final_text,
            reply_markup=restart_keyboard(),
            parse_mode="Markdown"
        )


@router.callback_query(F.data == "bj_restart")
async def restart_game(
    callback: CallbackQuery,
    state: FSMContext
):

    await callback.answer()

    await state.clear()

    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.message.answer(
        "🃏 **Blackjack**\n\n"
        "🪙 Yeni bahis miktarını gir:",
        reply_markup=bet_kb(),
        parse_mode="Markdown"
    )

    await state.set_state(BlackjackStates.BET)

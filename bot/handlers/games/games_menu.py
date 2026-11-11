
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardRemove


router = Router()


@router.message(Command("games"))
async def show_games_menu(message: Message):

    await message.answer(
        "🎮 **ÖzVeGas Oyunları**\n\n"
        "🎰 Slot: /slots\n"
        "🎡 Rulet: /roulette\n"
        "🃏 Blackjack: /blackjack\n"
        "💣 Mayınlar: /mines\n"
        "🚀 Roket: /rocket\n"
        "⚖️ Tek / Çift: /evenodd",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )

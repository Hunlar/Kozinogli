
from aiogram import Router, F
from aiogram.types import Message

from bot.keyboards import games_menu

router = Router()


@router.message(F.text == "🎮 Oyunlar")
async def show_games_menu(message: Message):
    await message.answer(
        "🎮 **Oyunlar menüsü**\n\n"
        "Oynamak istediğin oyunu seç:",
        reply_markup=games_menu(),
        parse_mode="Markdown"
    )

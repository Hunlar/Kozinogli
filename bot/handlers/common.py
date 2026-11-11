
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from bot.keyboards import main_menu


router = Router()


@router.message(F.text == "🔙 Geri")
async def back_to_main(
    message: Message,
    state: FSMContext
):
    await state.clear()

    await message.answer(
        "🏠 Ana menü:",
        reply_markup=main_menu(
            user_id=message.from_user.id
        )
    )

from aiogram import Router, F
from aiogram.types import Message
from bot.keyboards import top_up_menu, back_button
from bot.keyboards import main_menu, admin_menu, games_menu
router = Router()


@router.message(F.text == "Пополнить")
async def show_top_up_menu(message: Message):
    """Показывает меню пополнения баланса"""
    await message.answer("Выберите сумму пополнения:", reply_markup=top_up_menu())


@router.message(F.text.in_(["500 ₽", "1000 ₽", "2000 ₽", "5000 ₽"]))
async def process_top_up(message: Message):
    """Обрабатывает выбор суммы пополнения"""
    amount = int(message.text.split(" ")[0])

    # TODO: Здесь добавьте интеграцию с платежной системой (Qiwi, ЮMoney и т.д.)
    # Пример генерации ссылки для оплаты:
    # payment_link = generate_payment_link(user_id, amount)

    await message.answer(
        f"Нужно пополнить: {amount} ₽\n"
        f"ТУТ БУДЕТ КРИПТА\n"
        f"После оплаты нажмите 'Проверить оплату'",
        reply_markup=back_button()
    )
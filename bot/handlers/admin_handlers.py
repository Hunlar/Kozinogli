# bot/handlers/admin_handlers.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, update
from datetime import datetime, timedelta
from db.database import AsyncSessionLocal
from bot.keyboards import main_menu, admin_menu, back_button, games_menu
from settings import ADMINS
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from db.models import User, Coupon, GameSettings, Transaction

router = Router()

@router.message(F.text == "Админ панель", F.from_user.id.in_(ADMINS))
async def show_admin_panel(message: Message):
    await message.answer("Админ-панель:", reply_markup=admin_menu())

# --- Состояния FSM ---
class AdminStates(StatesGroup):
    BROADCAST_MESSAGE = State()
    ADD_BALANCE_USER_ID = State()
    ADD_BALANCE_AMOUNT = State()
    BLOCK_USER = State()
    GAME_MULTIPLIER_NAME = State()
    GAME_MULTIPLIER_VALUE = State()
    CREATE_COUPON_CODE = State()
    CREATE_COUPON_USES = State()
    CREATE_COUPON_DAYS_ADD = State()
    UNBLOCK_USER = State()


# --- Проверка прав администратора ---
async def is_admin(user_id: int) -> bool:
    return user_id in ADMINS

@router.message(F.text == "Выйти из админки")
async def exit_admin(message: Message, state: FSMContext):
    await state.clear()  # Сбросить все состояния
    await message.answer(
        "Главное меню:",
        reply_markup=main_menu(user_id=message.from_user.id)  # Обновить меню
    )

# --- Рассылка ---
@router.message(F.text == "Рассылка")
async def start_broadcast(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return

    # Инструкция без форматирования (теги отображаются как текст)
    instruction = (
        "📌 Доступные форматы:\n"
        "Жирный: <b>текст</b>\n"
        "Курсив: <i>текст</i>\n"
        "Ссылка: <a href='url'>текст</a>\n"
        "Спойлер: <tg-spoiler>текст</tg-spoiler>\n\n"
    )

    # Отправляем без parse_mode (теги не обрабатываются)
    await message.answer(instruction)

    await message.answer(
        "👇 Введите текст для рассылки:",
        reply_markup=back_button()
    )
    await state.set_state(AdminStates.BROADCAST_MESSAGE)


@router.message(AdminStates.BROADCAST_MESSAGE)
async def process_broadcast(message: Message, state: FSMContext, bot):
    # Исправляем замену на правильный HTML-тег для спойлеров
    formatted_text = (
        message.text
        .replace('<tg-spoiler>', '<span class="tg-spoiler">')  # Ключевое изменение
        .replace('</tg-spoiler>', '</span>')
    )

    async with AsyncSessionLocal() as session:
        users = await session.execute(select(User))

        for user in users.scalars():
            try:
                await bot.send_message(
                    chat_id=user.tg_id,
                    text=formatted_text,
                    parse_mode="HTML",
                    disable_web_page_preview=False
                )
            except Exception as e:
                print(f"Ошибка отправки: {e}")

    await message.answer("✅ Рассылка завершена!")
    await state.clear()

# --- Разблокировать ---
@router.message(F.text == "Разблокировать")
async def unblock_user_start(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await message.answer("Введите ID пользователя для разблокировки:", reply_markup=back_button())
    await state.set_state(AdminStates.UNBLOCK_USER)

@router.message(AdminStates.UNBLOCK_USER)
async def process_unblock_user(message: Message, state: FSMContext):
    if message.text == "🔙 Назад":
        await state.clear()
        await message.answer("❌ Отмена разблокировки.", reply_markup=admin_menu())
        return

    try:
        target_user_id = int(message.text)
        async with AsyncSessionLocal() as session:
            # Обновляем статус блокировки
            await session.execute(
                update(User)
                .where(User.tg_id == target_user_id)
                .values(is_blocked=False)
            )
            await session.commit()

            await message.bot.send_message(
                chat_id=target_user_id,
                text="✅ Ваша блокировка снята!"
            )

            await message.answer(f"✅ Пользователь {target_user_id} разблокирован!")
    except ValueError:
        await message.answer("❌ Некорректный ID пользователя!")
    finally:
        await state.clear()

# --- Добавить баланс ---
@router.message(F.text == "Добавить баланс")
async def add_balance_start(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await message.answer("Введите ID пользователя:", reply_markup=back_button())
    await state.set_state(AdminStates.ADD_BALANCE_USER_ID)


@router.message(AdminStates.ADD_BALANCE_USER_ID)
async def add_balance_user_id(message: Message, state: FSMContext):
    await state.update_data(user_id=int(message.text))
    await message.answer("Введите сумму:")
    await state.set_state(AdminStates.ADD_BALANCE_AMOUNT)


@router.message(AdminStates.ADD_BALANCE_AMOUNT)
async def add_balance_amount(message: Message, state: FSMContext):
    data = await state.get_data()
    async with AsyncSessionLocal() as session:
        user = await session.execute(select(User).where(User.tg_id == data["user_id"]))
        user = user.scalar()
        user.balance += float(message.text)
        await session.commit()
    await message.answer("✅ Баланс обновлен!")
    await state.clear()


# --- Блокировка ---
@router.message(F.text == "Заблокировать")
async def block_user_start(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await message.answer("Введите ID пользователя для блокировки:", reply_markup=back_button())
    await state.set_state(AdminStates.BLOCK_USER)


@router.message(AdminStates.BLOCK_USER)
async def block_user_process(message: Message, state: FSMContext):
    try:
        target_user_id = int(message.text)
        async with AsyncSessionLocal() as session:
            # Обновляем статус блокировки
            await session.execute(
                update(User)
                .where(User.tg_id == target_user_id)
                .values(is_blocked=True)
            )
            await session.commit()

            # Отправляем уведомление заблокированному пользователю
            await message.bot.send_message(
                chat_id=target_user_id,
                text="🚫 Вы заблокированы администратором!"
            )

        await message.answer("✅ Пользователь заблокирован!")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
    finally:
        await state.clear()


# --- Статистика ---
@router.message(F.text == "Статистика")
async def show_stats(message: Message):
    if not await is_admin(message.from_user.id):
        return
    async with AsyncSessionLocal() as session:
        users_count = (await session.execute(select(User))).scalars().count()
        topups = (await session.execute(select(Transaction).where(Transaction.type == "topup"))).scalars().all()
        purchases = (await session.execute(select(Transaction).where(Transaction.type == "purchase"))).scalars().all()

        stats_text = (
            f"👥 Пользователи: {users_count}\n"
            f"💰 Пополнений: {len(topups)} на сумму {sum(t.amount for t in topups)} ₽\n"
            f"🛒 Покупок: {len(purchases)} на сумму {sum(t.amount for t in purchases)} ₽"
        )
        await message.answer(stats_text)


# --- Подкрутка ---
@router.message(F.text == "Подкрутка")
async def adjust_multiplier_start(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await message.answer("Введите название игры (слоты/чет-нечет):")
    await state.set_state(AdminStates.GAME_MULTIPLIER_NAME)


@router.message(AdminStates.GAME_MULTIPLIER_NAME)
async def adjust_multiplier_name(message: Message, state: FSMContext):
    await state.update_data(game_name=message.text.lower())
    await message.answer("Введите новый множитель (например 1.5):")
    await state.set_state(AdminStates.GAME_MULTIPLIER_VALUE)


@router.message(AdminStates.GAME_MULTIPLIER_VALUE)
async def adjust_multiplier_value(message: Message, state: FSMContext):
    data = await state.get_data()
    async with AsyncSessionLocal() as session:
        game = await session.execute(
            select(GameSettings).where(GameSettings.game_name == data["game_name"])
        )
        game = game.scalar()
        game.multiplier = float(message.text)
        await session.commit()
    await message.answer("✅ Множитель обновлен!")
    await state.clear()


# --- Создать купон ---
@router.message(F.text == "Создать купон")
async def create_coupon_start(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await message.answer("Введите код купона:")
    await state.set_state(AdminStates.CREATE_COUPON_CODE)

@router.message(AdminStates.CREATE_COUPON_CODE)
async def create_coupon_code(message: Message, state: FSMContext):
    await state.update_data(code=message.text)
    await message.answer("Введите количество использований:")
    await state.set_state(AdminStates.CREATE_COUPON_USES)

@router.message(AdminStates.CREATE_COUPON_USES)
async def create_coupon_uses(message: Message, state: FSMContext):
    await state.update_data(uses=int(message.text))
    await message.answer("На сколько дней продлевать подписку?")
    await state.set_state(AdminStates.CREATE_COUPON_DAYS_ADD)

@router.message(AdminStates.CREATE_COUPON_DAYS_ADD)
async def create_coupon_days_add(message: Message, state: FSMContext):
    data = await state.get_data()
    async with AsyncSessionLocal() as session:
        coupon = Coupon(
            code=data["code"],
            uses_left=data["uses"],
            days_added=int(message.text)  # Сохраняем дни продления
        )
        session.add(coupon)
        await session.commit()
    await message.answer("✅ Купон создан!")
    await state.clear()
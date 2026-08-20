from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from db.models import User
from db.database import AsyncSessionLocal
import bcrypt
from aiogram.filters import Command
from sqlalchemy import select
from settings import ADMINS, MODERATORS
from bot.keyboards import main_menu, admin_menu, games_menu
class RegistrationStates(StatesGroup):
    LOGIN = State()
    PASSWORD = State()

router = Router()



@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    async with AsyncSessionLocal() as session:
        user = await session.execute(
            select(User).where(User.tg_id == user_id)
        )
        user = user.scalar()

        if user:
            await message.answer("Вы уже зарегистрированы!", reply_markup=main_menu(user_id))
            return

        await message.answer("Регистрация:\nВведите логин:")
        await state.set_state(RegistrationStates.LOGIN)


@router.message(RegistrationStates.LOGIN)
async def process_login(message: Message, state: FSMContext):
    login = message.text
    user_id = message.from_user.id

    async with AsyncSessionLocal() as session:
        # Проверка на существование по tg_id
        user = await session.execute(
            select(User).where(User.tg_id == user_id)
        )
        if user.scalar():
            await message.answer("Вы уже зарегистрированы!")
            await state.clear()
            return

        # Проверка уникальности логина
        login_exists = await session.execute(
            select(User).where(User.login == login)
        )
        if login_exists.scalar():
            await message.answer("Такой логин уже существует!")
            return

    await state.update_data(login=login)
    await message.answer("Введите пароль:")
    await state.set_state(RegistrationStates.PASSWORD)


@router.message(RegistrationStates.PASSWORD)
async def process_password(message: Message, state: FSMContext):
    data = await state.get_data()
    login = data.get("login")
    password = message.text.encode('utf-8')
    password_hash = bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')
    user_id = message.from_user.id

    async with AsyncSessionLocal() as session:
        is_admin = user_id in ADMINS
        is_moderator = user_id in MODERATORS


        # Проверка повторной регистрации (на всякий случай)
        existing_user = await session.execute(
            select(User).where(User.tg_id == user_id)
        )
        if existing_user.scalar():
            await message.answer("Вы уже зарегистрированы!")
            await state.clear()
            return

        new_user = User(
            tg_id=message.from_user.id,
            login=login,
            password=message.text,  # Сохраняем пароль в открытом виде
            balance=0.0
        )
        session.add(new_user)

        try:
            await session.commit()
        except Exception as e:
            await message.answer("Ошибка регистрации. Попробуйте позже.")
            await session.rollback()
            return

    await state.clear()
    await message.answer("Вы успешно зарегистрированы!",
                         reply_markup=main_menu(user_id))
    await message.answer("Главное меню:",
                             reply_markup=main_menu(is_admin, is_moderator))
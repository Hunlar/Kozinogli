# bot/handlers/bonuses.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta
import random
from db.database import AsyncSessionLocal
from db.models import User, Coupon
from bot.keyboards import bonuses_menu, roulette_menu, back_button, main_menu, admin_menu, games_menu
from sqlalchemy import select

router = Router()

# Конфигурация рулетки
ROULETTE_OPTIONS = [
    {"text": "1 аккаунт", "chance": 0.5, "multiplier": 0.5},
    {"text": "2 аккаунта", "chance": 0.4, "multiplier": 0.4},
    {"text": "3 аккаунта", "chance": 0.3, "multiplier": 0.3},
    {"text": "1 день", "chance": 0.6, "multiplier": 1.0},
    {"text": "2 дня", "chance": 0.2, "multiplier": 2.0},
    {"text": "3 дня", "chance": 0.1, "multiplier": 3.0}
]

class BonusStates(StatesGroup):
    ACTIVATE_COUPON = State()

@router.message(F.text == "Бонусы")
async def show_bonuses(message: Message):
    await message.answer("🎁 Бонусы:", reply_markup=bonuses_menu())

@router.message(F.text == "Рулетка")
async def spin_roulette(message: Message):
    user_id = message.from_user.id
    async with AsyncSessionLocal() as session:
        user = await session.execute(select(User).where(User.tg_id == user_id))
        user = user.scalar()

        # Проверка времени последнего использования
        if user.last_roulette_spin and (datetime.now() - user.last_roulette_spin).days < 7:
            await message.answer("❌ Рулетка доступна раз в неделю!")
            return

        # Выбор случайного приза по вероятности
        weights = [opt["chance"] for opt in ROULETTE_OPTIONS]
        result = random.choices(ROULETTE_OPTIONS, weights=weights, k=1)[0]

        # Обновление данных пользователя
        user.balance += user.balance * result["multiplier"]
        user.last_roulette_spin = datetime.now()
        await session.commit()

        await message.answer(
            f"🎉 Вы выиграли: {result['text']} (+{result['multiplier']*100}% к балансу)!",
            reply_markup=back_button()
        )

@router.message(F.text == "Активировать купон")
async def activate_coupon_start(message: Message, state: FSMContext):
    await message.answer("Введите код купона:", reply_markup=back_button())
    await state.set_state(BonusStates.ACTIVATE_COUPON)

@router.message(BonusStates.ACTIVATE_COUPON)
async def activate_coupon(message: Message, state: FSMContext):
    coupon_code = message.text.strip()
    user_id = message.from_user.id

    async with AsyncSessionLocal() as session:
        coupon = await session.execute(select(Coupon).where(Coupon.code == coupon_code))
        coupon = coupon.scalar()

        # Проверка валидности
        if not coupon or not coupon.is_active or coupon.uses_left <= 0:
            await message.answer("❌ Недействительный купон!")
            await state.clear()
            return

        # Проверка использования
        if coupon.user_id == user_id:
            await message.answer("❌ Вы уже активировали этот купон!")
            await state.clear()
            return

        # Продление подписки
        user = await session.execute(select(User).where(User.tg_id == user_id))
        user = user.scalar()
        current_end = user.subscription_end or datetime.now()
        user.subscription_end = current_end + timedelta(days=coupon.days_added)

        # Обновление купона
        coupon.uses_left -= 1
        coupon.user_id = user_id
        if coupon.uses_left <= 0:
            coupon.is_active = False

        await session.commit()
        await message.answer(
            f"✅ Купон активирован! Подписка продлена на {coupon.days_added} дней. "
            f"Новая дата окончания: {user.subscription_end.strftime('%d.%m.%Y')}"
        )
        await state.clear()
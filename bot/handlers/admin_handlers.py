
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from sqlalchemy import select, update, func

from db.database import AsyncSessionLocal
from db.models import User, GameSettings
from bot.keyboards import main_menu, admin_menu, back_button
from settings import ADMINS

router = Router()


class AdminStates(StatesGroup):
    BROADCAST_MESSAGE = State()
    ADD_BALANCE_USER_ID = State()
    ADD_BALANCE_AMOUNT = State()
    BLOCK_USER = State()
    UNBLOCK_USER = State()
    GAME_MULTIPLIER_NAME = State()
    GAME_MULTIPLIER_VALUE = State()


async def is_admin(user_id: int) -> bool:
    return user_id in ADMINS


async def check_admin(message: Message) -> bool:
    if not await is_admin(message.from_user.id):
        await message.answer("⛔ Bu işlem için yetkiniz bulunmuyor.")
        return False
    return True


@router.message(F.text == "Admin Paneli")
async def show_admin_panel(message: Message):
    if not await check_admin(message):
        return

    await message.answer(
        "🛠 Admin Paneli:",
        reply_markup=admin_menu()
    )


@router.message(F.text == "Admin Panelinden Çık")
async def exit_admin(message: Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "🏠 Ana menü:",
        reply_markup=main_menu(user_id=message.from_user.id)
    )


# DUYURU

@router.message(F.text == "Duyuru Gönder")
async def start_broadcast(message: Message, state: FSMContext):
    if not await check_admin(message):
        return

    await message.answer(
        "📢 Duyuru metnini gönderin.\nHTML biçimlendirmesi kullanılabilir.",
        reply_markup=back_button()
    )

    await state.set_state(AdminStates.BROADCAST_MESSAGE)


@router.message(AdminStates.BROADCAST_MESSAGE)
async def process_broadcast(message: Message, state: FSMContext, bot):
    if not await check_admin(message):
        await state.clear()
        return

    if message.text == "🔙 Geri":
        await state.clear()
        await message.answer(
            "İşlem iptal edildi.",
            reply_markup=admin_menu()
        )
        return

    if not message.text:
        await message.answer("Lütfen metin biçiminde bir duyuru gönderin.")
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()

        delivered = 0

        for user in users:
            try:
                await bot.send_message(
                    chat_id=user.tg_id,
                    text=message.text,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
                delivered += 1
            except Exception:
                continue

    await message.answer(
        f"✅ Duyuru tamamlandı.\n"
        f"📨 Ulaşan kullanıcı sayısı: {delivered}",
        reply_markup=admin_menu()
    )

    await state.clear()


# KULLANICI ENGELLEMEYİ KALDIRMA

@router.message(F.text == "Engeli Kaldır")
async def unblock_user_start(message: Message, state: FSMContext):
    if not await check_admin(message):
        return

    await message.answer(
        "Engelini kaldırmak istediğiniz kullanıcının Telegram ID'sini girin:",
        reply_markup=back_button()
    )

    await state.set_state(AdminStates.UNBLOCK_USER)


@router.message(AdminStates.UNBLOCK_USER)
async def process_unblock_user(message: Message, state: FSMContext):
    if not await check_admin(message):
        await state.clear()
        return

    if message.text == "🔙 Geri":
        await state.clear()
        await message.answer("İşlem iptal edildi.", reply_markup=admin_menu())
        return

    try:
        target_id = int(message.text)

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                update(User)
                .where(User.tg_id == target_id)
                .values(is_blocked=False)
            )

            await session.commit()

            if result.rowcount == 0:
                await message.answer("❌ Kullanıcı bulunamadı.")
            else:
                try:
                    await message.bot.send_message(
                        target_id,
                        "✅ Hesabınızın engeli kaldırıldı."
                    )
                except Exception:
                    pass

                await message.answer(
                    f"✅ {target_id} ID'li kullanıcının engeli kaldırıldı.",
                    reply_markup=admin_menu()
                )

    except (ValueError, TypeError):
        await message.answer("❌ Geçerli bir Telegram ID'si girin.")
        return

    await state.clear()


# SANAL KREDİ EKLEME

@router.message(F.text == "Sanal Kredi Ekle")
async def add_balance_start(message: Message, state: FSMContext):
    if not await check_admin(message):
        return

    await message.answer(
        "Sanal kredi eklemek istediğiniz kullanıcının Telegram ID'sini girin:",
        reply_markup=back_button()
    )

    await state.set_state(AdminStates.ADD_BALANCE_USER_ID)


@router.message(AdminStates.ADD_BALANCE_USER_ID)
async def add_balance_user_id(message: Message, state: FSMContext):
    if not await check_admin(message):
        await state.clear()
        return

    if message.text == "🔙 Geri":
        await state.clear()
        await message.answer("İşlem iptal edildi.", reply_markup=admin_menu())
        return

    try:
        user_id = int(message.text)

        await state.update_data(user_id=user_id)

        await message.answer(
            "Eklenecek Sanal Kredi miktarını girin:"
        )

        await state.set_state(AdminStates.ADD_BALANCE_AMOUNT)

    except (ValueError, TypeError):
        await message.answer("❌ Geçerli bir Telegram ID'si girin.")


@router.message(AdminStates.ADD_BALANCE_AMOUNT)
async def add_balance_amount(message: Message, state: FSMContext):
    if not await check_admin(message):
        await state.clear()
        return

    if message.text == "🔙 Geri":
        await state.clear()
        await message.answer("İşlem iptal edildi.", reply_markup=admin_menu())
        return

    try:
        amount = float(message.text)

        if not 0 < amount < float("inf"):
            await message.answer("❌ Pozitif ve geçerli bir miktar girin.")
            return

        data = await state.get_data()

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User).where(User.tg_id == data["user_id"])
            )

            user = result.scalar_one_or_none()

            if not user:
                await message.answer(
                    "❌ Kullanıcı bulunamadı.",
                    reply_markup=admin_menu()
                )
                await state.clear()
                return

            user.balance += amount
            new_balance = user.balance

            await session.commit()

        await message.answer(
            f"✅ Sanal kredi eklendi!\n\n"
            f"👤 Kullanıcı: {data['user_id']}\n"
            f"🪙 Eklenen: {amount:g} Sanal Kredi\n"
            f"💰 Yeni bakiye: {new_balance:g} Sanal Kredi",
            reply_markup=admin_menu()
        )

    except (ValueError, TypeError):
        await message.answer("❌ Geçerli bir miktar girin.")
        return

    await state.clear()


# KULLANICI ENGELLEME

@router.message(F.text == "Kullanıcıyı Engelle")
async def block_user_start(message: Message, state: FSMContext):
    if not await check_admin(message):
        return

    await message.answer(
        "Engellemek istediğiniz kullanıcının Telegram ID'sini girin:",
        reply_markup=back_button()
    )

    await state.set_state(AdminStates.BLOCK_USER)


@router.message(AdminStates.BLOCK_USER)
async def block_user_process(message: Message, state: FSMContext):
    if not await check_admin(message):
        await state.clear()
        return

    if message.text == "🔙 Geri":
        await state.clear()
        await message.answer("İşlem iptal edildi.", reply_markup=admin_menu())
        return

    try:
        target_id = int(message.text)

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                update(User)
                .where(User.tg_id == target_id)
                .values(is_blocked=True)
            )

            await session.commit()

            if result.rowcount == 0:
                await message.answer("❌ Kullanıcı bulunamadı.")
            else:
                try:
                    await message.bot.send_message(
                        target_id,
                        "🚫 Hesabınız yönetici tarafından engellendi."
                    )
                except Exception:
                    pass

                await message.answer(
                    f"✅ {target_id} ID'li kullanıcı engellendi.",
                    reply_markup=admin_menu()
                )

    except (ValueError, TypeError):
        await message.answer("❌ Geçerli bir Telegram ID'si girin.")
        return

    await state.clear()


# İSTATİSTİK

@router.message(F.text == "İstatistikler")
async def show_stats(message: Message):
    if not await check_admin(message):
        return

    async with AsyncSessionLocal() as session:
        total_users = await session.scalar(
            select(func.count(User.id))
        )

        blocked_users = await session.scalar(
            select(func.count(User.id)).where(User.is_blocked.is_(True))
        )

        total_balance = await session.scalar(
            select(func.coalesce(func.sum(User.balance), 0))
        )

        stats_text = (
            "📊 **ÖzVeGas İstatistikleri**\n\n"
            f"👥 Toplam kullanıcı: {total_users or 0}\n"
            f"🚫 Engellenen kullanıcı: {blocked_users or 0}\n"
            f"🪙 Dağıtılmış toplam Sanal Kredi: {total_balance or 0:g}"
        )

    await message.answer(
        stats_text,
        reply_markup=admin_menu(),
        parse_mode="Markdown"
    )


# OYUN ÇARPANI AYARI

@router.message(F.text == "Oyun Çarpanları")
async def adjust_multiplier_start(message: Message, state: FSMContext):
    if not await check_admin(message):
        return

    await message.answer(
        "Çarpanını düzenlemek istediğiniz oyunun adını girin:\n\n"
        "slots / even_odd / roulette / blackjack / mines / crash",
        reply_markup=back_button()
    )

    await state.set_state(AdminStates.GAME_MULTIPLIER_NAME)


@router.message(AdminStates.GAME_MULTIPLIER_NAME)
async def adjust_multiplier_name(message: Message, state: FSMContext):
    if not await check_admin(message):
        await state.clear()
        return

    if message.text == "🔙 Geri":
        await state.clear()
        await message.answer("İşlem iptal edildi.", reply_markup=admin_menu())
        return

    valid_games = [
        "slots",
        "even_odd",
        "roulette",
        "blackjack",
        "mines",
        "crash"
    ]

    game = message.text.lower().strip()

    if game not in valid_games:
        await message.answer(
            f"❌ Geçersiz oyun. Kullanılabilir oyunlar: {', '.join(valid_games)}"
        )
        return

    await state.update_data(game_name=game)

    await message.answer(
        "Yeni çarpan değerini girin (örnek: 1.0):"
    )

    await state.set_state(AdminStates.GAME_MULTIPLIER_VALUE)


@router.message(AdminStates.GAME_MULTIPLIER_VALUE)
async def adjust_multiplier_value(message: Message, state: FSMContext):
    if not await check_admin(message):
        await state.clear()
        return

    if message.text == "🔙 Geri":
        await state.clear()
        await message.answer("İşlem iptal edildi.", reply_markup=admin_menu())
        return

    try:
        multiplier = float(message.text)

        if not 0 < multiplier < float("inf"):
            await message.answer("❌ Geçerli ve pozitif bir çarpan girin.")
            return

        data = await state.get_data()

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(GameSettings).where(
                    GameSettings.game_name == data["game_name"]
                )
            )

            game = result.scalar_one_or_none()

            if not game:
                game = GameSettings(
                    game_name=data["game_name"],
                    multiplier=1.0
                )
                session.add(game)

            game.multiplier = multiplier
            await session.commit()

        await message.answer(
            f"✅ {data['game_name']} oyununun kayıtlı çarpanı: {multiplier}",
            reply_markup=admin_menu()
        )

    except (ValueError, TypeError):
        await message.answer("❌ Sayısal bir değer girin.")
        return

    await state.clear()

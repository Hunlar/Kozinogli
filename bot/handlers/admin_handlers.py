
import math

from aiogram import Router
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.types import Message
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from sqlalchemy import select, update, func

from db.database import AsyncSessionLocal
from db.models import User, GameSettings
from settings import ADMINS


router = Router()

BANKRUPTCY_LIMIT = 4000


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
        await message.answer(
            "⛔ Bu işlem için yönetici yetkin bulunmuyor."
        )
        return False

    return True


def valid_positive_number(value: str) -> float:
    amount = float(value.replace(",", ".").strip())

    if not math.isfinite(amount) or amount <= 0:
        raise ValueError

    return amount


@router.message(Command("admin"))
async def show_admin_panel(message: Message):
    if not await check_admin(message):
        return

    await message.answer(
        "🛠 **ÖzVeGas Yönetici Komutları**\n\n"
        "/broadcast — Duyuru gönder\n"
        "/credit — Kullanıcıya kredi ekle\n"
        "/ban — Kullanıcıyı engelle\n"
        "/unban — Kullanıcının engelini kaldır\n"
        "/stats — İstatistikleri görüntüle\n"
        "/multiplier — Oyun çarpanını düzenle\n\n"
        "İşlemleri iptal etmek için /iptal yaz.",
        parse_mode="Markdown"
    )


@router.message(Command("iptal"), StateFilter(
    AdminStates.BROADCAST_MESSAGE,
    AdminStates.ADD_BALANCE_USER_ID,
    AdminStates.ADD_BALANCE_AMOUNT,
    AdminStates.BLOCK_USER,
    AdminStates.UNBLOCK_USER,
    AdminStates.GAME_MULTIPLIER_NAME,
    AdminStates.GAME_MULTIPLIER_VALUE
))
async def cancel_admin_action(
    message: Message,
    state: FSMContext
):
    await state.clear()
    await message.answer("❌ Yönetici işlemi iptal edildi.")


# --------------------------------------------------
# DUYURU
# --------------------------------------------------

@router.message(Command("broadcast"))
async def start_broadcast(
    message: Message,
    state: FSMContext
):
    if not await check_admin(message):
        return

    await state.clear()
    await state.set_state(AdminStates.BROADCAST_MESSAGE)

    await message.answer(
        "📢 **Duyuru Gönderme**\n\n"
        "Göndermek istediğin duyuru metnini yaz.\n"
        "HTML biçimlendirmesi kullanabilirsin.\n\n"
        "İptal etmek için /iptal yaz.",
        parse_mode="Markdown"
    )


@router.message(AdminStates.BROADCAST_MESSAGE)
async def process_broadcast(
    message: Message,
    state: FSMContext
):
    if not await check_admin(message):
        await state.clear()
        return

    if not message.text:
        await message.answer(
            "❌ Lütfen metin biçiminde bir duyuru gönder."
        )
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User.tg_id))
        user_ids = result.scalars().all()

    delivered = 0
    failed = 0

    for user_id in user_ids:
        try:
            await message.bot.send_message(
                chat_id=user_id,
                text=message.text,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            delivered += 1
        except Exception:
            failed += 1

    await state.clear()

    await message.answer(
        "📢 **DUYURU TAMAMLANDI**\n\n"
        f"✅ Ulaşan kullanıcı: {delivered}\n"
        f"❌ Ulaşmayan kullanıcı: {failed}\n"
        f"👥 Toplam kullanıcı: {len(user_ids)}",
        parse_mode="Markdown"
    )


# --------------------------------------------------
# KULLANICIYA KREDİ EKLEME
# --------------------------------------------------

@router.message(Command("credit"))
async def add_balance_start(
    message: Message,
    state: FSMContext
):
    if not await check_admin(message):
        return

    await state.clear()
    await state.set_state(AdminStates.ADD_BALANCE_USER_ID)

    await message.answer(
        "🪙 Kredi eklenecek kullanıcının Telegram ID'sini gir.\n"
        "İptal etmek için /iptal yaz."
    )


@router.message(AdminStates.ADD_BALANCE_USER_ID)
async def add_balance_user_id(
    message: Message,
    state: FSMContext
):
    if not await check_admin(message):
        await state.clear()
        return

    try:
        user_id = int(message.text)

        if user_id <= 0:
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        await message.answer("❌ Geçerli bir Telegram ID'si gir.")
        return

    await state.update_data(user_id=user_id)
    await state.set_state(AdminStates.ADD_BALANCE_AMOUNT)

    await message.answer("🪙 Eklenecek Sanal Kredi miktarını gir.")


@router.message(AdminStates.ADD_BALANCE_AMOUNT)
async def add_balance_amount(
    message: Message,
    state: FSMContext
):
    if not await check_admin(message):
        await state.clear()
        return

    try:
        amount = valid_positive_number(message.text)
    except (ValueError, TypeError, AttributeError):
        await message.answer("❌ Pozitif ve geçerli bir miktar gir.")
        return

    data = await state.get_data()
    target_id = data.get("user_id")

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User)
            .where(User.tg_id == target_id)
            .with_for_update()
        )
        user = result.scalar_one_or_none()

        if user is None:
            await state.clear()
            await message.answer("❌ Kullanıcı bulunamadı.")
            return

        user.balance = (user.balance or 0) + amount

        if user.balance >= BANKRUPTCY_LIMIT:
            user.is_bankrupt = False
            user.bankruptcy_announced = False
            user.bankruptcy_chat_id = None

        new_balance = user.balance
        await session.commit()

    await state.clear()

    await message.answer(
        "✅ **SANAL KREDİ EKLENDİ**\n\n"
        f"👤 Kullanıcı ID: {target_id}\n"
        f"🪙 Eklenen: +{amount:,.2f} Sanal Kredi\n"
        f"💰 Yeni bakiye: {new_balance:,.2f} Sanal Kredi",
        parse_mode="Markdown"
    )


# --------------------------------------------------
# KULLANICI ENGELLEME
# --------------------------------------------------

@router.message(Command("ban"))
async def block_user_start(
    message: Message,
    state: FSMContext
):
    if not await check_admin(message):
        return

    await state.clear()
    await state.set_state(AdminStates.BLOCK_USER)

    await message.answer(
        "🚫 Engellenecek kullanıcının Telegram ID'sini gir.\n"
        "İptal etmek için /iptal yaz."
    )


@router.message(AdminStates.BLOCK_USER)
async def block_user_process(
    message: Message,
    state: FSMContext
):
    if not await check_admin(message):
        await state.clear()
        return

    try:
        target_id = int(message.text)

        if target_id <= 0:
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        await message.answer("❌ Geçerli bir Telegram ID'si gir.")
        return

    if target_id in ADMINS:
        await message.answer(
            "⛔ Başka bir yöneticiyi engelleyemezsin."
        )
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            update(User)
            .where(User.tg_id == target_id)
            .values(is_blocked=True)
        )
        found = result.rowcount > 0
        await session.commit()

    await state.clear()

    if not found:
        await message.answer("❌ Kullanıcı bulunamadı.")
        return

    try:
        await message.bot.send_message(
            target_id,
            "🚫 Hesabın yönetici tarafından engellendi."
        )
    except Exception:
        pass

    await message.answer(
        f"✅ {target_id} ID'li kullanıcı engellendi."
    )


# --------------------------------------------------
# KULLANICI ENGELİNİ KALDIRMA
# --------------------------------------------------

@router.message(Command("unban"))
async def unblock_user_start(
    message: Message,
    state: FSMContext
):
    if not await check_admin(message):
        return

    await state.clear()
    await state.set_state(AdminStates.UNBLOCK_USER)

    await message.answer(
        "🔓 Engeli kaldırılacak kullanıcının Telegram ID'sini gir.\n"
        "İptal etmek için /iptal yaz."
    )


@router.message(AdminStates.UNBLOCK_USER)
async def process_unblock_user(
    message: Message,
    state: FSMContext
):
    if not await check_admin(message):
        await state.clear()
        return

    try:
        target_id = int(message.text)

        if target_id <= 0:
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        await message.answer("❌ Geçerli bir Telegram ID'si gir.")
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            update(User)
            .where(User.tg_id == target_id)
            .values(is_blocked=False)
        )
        found = result.rowcount > 0
        await session.commit()

    await state.clear()

    if not found:
        await message.answer("❌ Kullanıcı bulunamadı.")
        return

    try:
        await message.bot.send_message(
            target_id,
            "✅ Hesabının engeli yönetici tarafından kaldırıldı."
        )
    except Exception:
        pass

    await message.answer(
        f"✅ {target_id} ID'li kullanıcının engeli kaldırıldı."
    )


# --------------------------------------------------
# İSTATİSTİKLER
# --------------------------------------------------

@router.message(Command("stats"))
async def show_stats(message: Message):
    if not await check_admin(message):
        return

    async with AsyncSessionLocal() as session:
        total_users = await session.scalar(
            select(func.count(User.id))
        )

        blocked_users = await session.scalar(
            select(func.count(User.id))
            .where(User.is_blocked.is_(True))
        )

        total_balance = await session.scalar(
            select(func.coalesce(func.sum(User.balance), 0))
        )

        bankrupt_users = await session.scalar(
            select(func.count(User.id))
            .where(User.is_bankrupt.is_(True))
        )

    await message.answer(
        "📊 **ÖZVEGAS İSTATİSTİKLERİ**\n\n"
        f"👥 Toplam kullanıcı: {total_users or 0}\n"
        f"🚫 Engellenen kullanıcı: {blocked_users or 0}\n"
        f"💸 İflas eden kullanıcı: {bankrupt_users or 0}\n"
        f"🪙 Dağıtılmış toplam Sanal Kredi: "
        f"{(total_balance or 0):,.2f}",
        parse_mode="Markdown"
    )


# --------------------------------------------------
# OYUN ÇARPANLARI
# --------------------------------------------------

@router.message(Command("multiplier"))
async def adjust_multiplier_start(
    message: Message,
    state: FSMContext
):
    if not await check_admin(message):
        return

    await state.clear()
    await state.set_state(AdminStates.GAME_MULTIPLIER_NAME)

    await message.answer(
        "🎮 Çarpanını düzenlemek istediğin oyunun adını gir:\n\n"
        "slots\n"
        "even_odd\n"
        "roulette\n"
        "blackjack\n"
        "mines\n"
        "crash\n\n"
        "İptal etmek için /iptal yaz."
    )


@router.message(AdminStates.GAME_MULTIPLIER_NAME)
async def adjust_multiplier_name(
    message: Message,
    state: FSMContext
):
    if not await check_admin(message):
        await state.clear()
        return

    valid_games = [
        "slots",
        "even_odd",
        "roulette",
        "blackjack",
        "mines",
        "crash"
    ]

    game_name = (message.text or "").lower().strip()

    if game_name not in valid_games:
        await message.answer(
            "❌ Geçersiz oyun adı.\n"
            f"Kullanılabilir oyunlar: {', '.join(valid_games)}"
        )
        return

    await state.update_data(game_name=game_name)
    await state.set_state(AdminStates.GAME_MULTIPLIER_VALUE)

    await message.answer("Yeni çarpan değerini gir. Örnek: 1.5")


@router.message(AdminStates.GAME_MULTIPLIER_VALUE)
async def adjust_multiplier_value(
    message: Message,
    state: FSMContext
):
    if not await check_admin(message):
        await state.clear()
        return

    try:
        multiplier = valid_positive_number(message.text)
    except (ValueError, TypeError, AttributeError):
        await message.answer("❌ Pozitif ve geçerli bir çarpan gir.")
        return

    data = await state.get_data()
    game_name = data.get("game_name")

    if game_name is None:
        await state.clear()
        await message.answer(
            "❌ Oyun bilgisi bulunamadı. İşlemi yeniden başlat."
        )
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(GameSettings)
            .where(GameSettings.game_name == game_name)
            .with_for_update()
        )

        game = result.scalar_one_or_none()

        if game is None:
            game = GameSettings(
                game_name=game_name,
                multiplier=multiplier
            )
            session.add(game)
        else:
            game.multiplier = multiplier

        await session.commit()

    await state.clear()

    await message.answer(
        "✅ **OYUN ÇARPANI KAYDEDİLDİ**\n\n"
        f"🎮 Oyun: {game_name}\n"
        f"📈 Yeni çarpan: {multiplier:g}",
        parse_mode="Markdown"
        )
        

import asyncio
import random
import uuid

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select

from db.database import AsyncSessionLocal
from db.models import User


router = Router()

PRIZE = 200_000
MIN_NUMBER = 1
MAX_NUMBER = 100
GAME_TIMEOUT = 300  # 5 dakika

# Her grup için ayrı oyun
ACTIVE_GAMES = {}
GAME_LOCKS = {}


def get_game_lock(chat_id: int):
    if chat_id not in GAME_LOCKS:
        GAME_LOCKS[chat_id] = asyncio.Lock()

    return GAME_LOCKS[chat_id]


@router.message(Command("sayi"))
async def start_number_game(message: Message):

    if message.chat.type not in ("group", "supergroup"):
        await message.answer(
            "Bu oyun yalnızca gruplarda oynanabilir."
        )
        return

    chat_id = message.chat.id
    lock = get_game_lock(chat_id)

    async with lock:

        if chat_id in ACTIVE_GAMES:
            await message.answer(
                "⚠️ Bu grupta zaten devam eden bir sayı oyunu var!"
            )
            return

        game_id = str(uuid.uuid4())
        secret_number = random.randint(MIN_NUMBER, MAX_NUMBER)

        ACTIVE_GAMES[chat_id] = {
            "id": game_id,
            "number": secret_number,
        }

    await message.answer(
        "🎯 <b>SAYI TAHMİN OYUNU BAŞLADI!</b>\n\n"
        "1 ile 100 arasında bir sayı tuttum.\n"
        "Herkes tahminini gruba yazabilir.\n\n"
        "⬆️ Daha yüksek\n"
        "⬇️ Daha düşük\n\n"
        "🏆 İlk doğru tahmini yapan:\n"
        "💰 <b>200.000 SANAL KREDİ</b> kazanacak!\n\n"
        "⏳ Süre: 5 dakika",
        parse_mode="HTML",
    )

    asyncio.create_task(
        end_game_after_timeout(chat_id, game_id, message.bot)
    )


async def end_game_after_timeout(chat_id: int, game_id: str, bot):

    await asyncio.sleep(GAME_TIMEOUT)

    lock = get_game_lock(chat_id)

    async with lock:

        game = ACTIVE_GAMES.get(chat_id)

        if not game or game["id"] != game_id:
            return

        ACTIVE_GAMES.pop(chat_id, None)
        secret_number = game["number"]

    await bot.send_message(
        chat_id,
        f"⏰ <b>SÜRE DOLDU!</b>\n\n"
        f"🔢 Tutulan sayı: <b>{secret_number}</b>\n\n"
        "Yeni oyun için /sayi yazabilirsiniz.",
        parse_mode="HTML",
    )


@router.message(F.text.regexp(r"^\d{1,3}$"))
async def guess_number(message: Message):

    if message.chat.type not in ("group", "supergroup"):
        return

    if not message.from_user:
        return

    guess = int(message.text)

    if guess < MIN_NUMBER or guess > MAX_NUMBER:
        return

    chat_id = message.chat.id
    lock = get_game_lock(chat_id)

    async with lock:

        game = ACTIVE_GAMES.get(chat_id)

        if not game:
            return

        secret_number = game["number"]

        if guess < secret_number:
            await message.answer("⬆️ Daha yüksek!")
            return

        if guess > secret_number:
            await message.answer("⬇️ Daha düşük!")
            return

        # Doğru tahmin yapan oyuncuyu veritabanında bul.
        async with AsyncSessionLocal() as session:

            result = await session.execute(
                select(User).where(
                    User.tg_id == message.from_user.id
                )
            )

            user = result.scalar_one_or_none()

            if user is None:
                await message.answer(
                    "❌ Ödülü alabilmek için önce bota özelden "
                    "/start vermelisin."
                )
                return

            # Kazanana 200.000 kredi ekle.
            user.balance += PRIZE

            await session.commit()

        # Oyunu kapat.
        ACTIVE_GAMES.pop(chat_id, None)

        winner_name = message.from_user.full_name

    await message.answer(
        "🎉 <b>DOĞRU TAHMİN!</b>\n\n"
        f"🏆 Kazanan: <b>{winner_name}</b>\n"
        f"🔢 Doğru sayı: <b>{guess}</b>\n\n"
        f"💰 Ödül: <b>{PRIZE:,} kredi</b>\n\n"
        "Yeni oyun için /sayi yazabilirsiniz.",
        parse_mode="HTML",
    )

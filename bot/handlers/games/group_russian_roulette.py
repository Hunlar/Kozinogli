import asyncio
import math
import random
import re
import secrets
from html import escape

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from sqlalchemy import select

from db.database import AsyncSessionLocal
from db.models import User
from bot.utils.bankruptcy import check_bankruptcy


router = Router()

# OYUN AYARLARI
INVITE_SECONDS = 60
BETTING_SECONDS = 60
ANNOUNCEMENT_INTERVAL = 15

# OYUN VERİLERİ
GAMES = {}
SEEN_USERS = {}
PENDING_BETS = {}
LOCK = asyncio.Lock()

OUTCOMES = {
    "a_alive": "🟢 A yaşar",
    "b_alive": "🟢 B yaşar",
    "both_die": "💀 İkisi de ölür",
    "both_live": "❤️ İkisi de yaşar",
}

OUTCOME_RESULTS = {
    "a_alive": "🟢 Yalnızca A hayatta kaldı!",
    "b_alive": "🟢 Yalnızca B hayatta kaldı!",
    "both_die": "💀 İki oyuncu da elendi!",
    "both_live": "❤️ İki oyuncu da hayatta kaldı!",
}


def fmt_amount(value):
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def outcome_label(game, choice):
    if choice == "a_alive":
        return f"🟢 {game['creator_name']} yaşar"
    if choice == "b_alive":
        return f"🟢 {game['opponent_name']} yaşar"
    return OUTCOMES[choice]


def outcome_result(game, choice):
    if choice == "a_alive":
        return (
            f"🟢 Yalnızca "
            f"{escape(game['creator_name'])} hayatta kaldı!"
        )
    if choice == "b_alive":
        return (
            f"🟢 Yalnızca "
            f"{escape(game['opponent_name'])} hayatta kaldı!"
        )
    return OUTCOME_RESULTS[choice]


def invite_keyboard(game_id):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🤝 KABUL ET",
            callback_data=f"rr:accept:{game_id}"
        ),
        InlineKeyboardButton(
            text="🏃 KORKTUM",
            callback_data=f"rr:decline:{game_id}"
        ),
    ]])


def betting_keyboard(game_id, creator_name, opponent_name):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"🟢 {creator_name} yaşar",
                callback_data=f"rr:pick:{game_id}:a_alive"
            ),
            InlineKeyboardButton(
                text=f"🟢 {opponent_name} yaşar",
                callback_data=f"rr:pick:{game_id}:b_alive"
            ),
        ],
        [
            InlineKeyboardButton(
                text="💀 İkisi de ölür",
                callback_data=f"rr:pick:{game_id}:both_die"
            ),
            InlineKeyboardButton(
                text="❤️ İkisi de yaşar",
                callback_data=f"rr:pick:{game_id}:both_live"
            ),
        ],
    ])


def bet_join_keyboard(game_id):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="💰 BAHİS YAP",
            callback_data=f"rr:join:{game_id}"
        )
    ]])


async def locked_user(session, telegram_id):
    result = await session.execute(
        select(User)
        .where(User.tg_id == telegram_id)
        .with_for_update()
    )
    return result.scalar_one_or_none()


def remember_group_user(message: Message):
    if message.chat.type not in ("group", "supergroup"):
        return

    user = message.from_user

    if not user or user.is_bot or not user.username:
        return

    chat_users = SEEN_USERS.setdefault(message.chat.id, {})

    chat_users[user.username.lower()] = {
        "id": user.id,
        "name": user.full_name,
    }


def active_player(game, user_id):
    return (
        user_id == game.get("creator")
        or user_id == game.get("opponent")
    )


@router.message(Command("kayit"))
async def register_group_username(message: Message):
    remember_group_user(message)

    if message.chat.type not in ("group", "supergroup"):
        await message.answer(
            "Bu komut yalnızca grupta kullanılabilir."
        )
        return

    if not message.from_user or not message.from_user.username:
        await message.answer(
            "❌ Telegram kullanıcı adın (@username) bulunmuyor."
        )
        return

    await message.answer(
        f"✅ @{escape(message.from_user.username)} "
        "Rus Ruleti davetleri için kaydedildi."
    )


@router.message(Command("rulet"))
async def create_duel(message: Message):
    remember_group_user(message)

    if message.chat.type not in ("group", "supergroup"):
        await message.answer(
            "🔫 Bu komut yalnızca gruplarda kullanılabilir."
        )
        return

    if not message.from_user or message.from_user.is_bot:
        return

    parts = (message.text or "").split(maxsplit=1)

    if len(parts) != 2:
        await message.answer(
            "Kullanım: /rulet @username"
        )
        return

    username = parts[1].strip().split()[0]

    if not re.fullmatch(r"@?[A-Za-z0-9_]{5,32}", username):
        await message.answer(
            "❌ Geçerli bir kullanıcı adı yaz. "
            "Örnek: /rulet @username"
        )
        return

    username = username.lstrip("@").lower()

    target = SEEN_USERS.get(
        message.chat.id, {}
    ).get(username)

    if target is None:
        await message.answer(
            f"❌ @{username} kullanıcısını henüz bu grupta göremedim.\n"
            "Önce gruba bir mesaj yazmasını iste, sonra tekrar dene."
        )
        return

    creator_id = message.from_user.id
    target_id = target["id"]

    if target_id == creator_id:
        await message.answer(
            "😈 Kendine meydan okuyamazsın!"
        )
        return

    async with LOCK:
        for game in GAMES.values():
            if game["status"] in (
                "open", "betting", "settling"
            ) and (
                active_player(game, creator_id)
                or active_player(game, target_id)
            ):
                await message.answer(
                    "❌ Senin veya seçtiğin oyuncunun "
                    "zaten devam eden bir düellosu var."
                )
                return

    async with AsyncSessionLocal() as session:
        creator_result = await session.execute(
            select(User).where(User.tg_id == creator_id)
        )
        target_result = await session.execute(
            select(User).where(User.tg_id == target_id)
        )

        creator = creator_result.scalar_one_or_none()
        target_user = target_result.scalar_one_or_none()

        if creator is None or target_user is None:
            await message.answer(
                "❌ İki oyuncunun da önce botu özelden "
                "/start komutuyla başlatıp hesap oluşturması gerekiyor."
            )
            return

    game_id = secrets.token_hex(4)

    game = {
        "chat_id": message.chat.id,
        "chat_type": message.chat.type,
        "message_id": None,
        "bet_announcement_id": None,
        "creator": creator_id,
        "creator_name": message.from_user.full_name,
        "opponent": target_id,
        "opponent_name": target["name"],
        "status": "open",
        "bets": {},
        "choices": {},
    }

    sent = await message.answer(
        "🔫 <b>RUS RULETİ DÜELLOSU</b>\n\n"
        f"<b>{escape(message.from_user.full_name)} VS "
        f"{escape(target['name'])}</b>\n\n"
        f"{escape(target['name'])}, seni Rus Ruletine davet ediyor!\n"
        "Kabul edecek misin, yoksa korkup gidecek misin? 😈",
        reply_markup=invite_keyboard(game_id),
        parse_mode="HTML",
    )

    game["message_id"] = sent.message_id
    GAMES[game_id] = game

    asyncio.create_task(
        expire_invite(game_id, message.bot)
    )


async def expire_invite(game_id, bot):
    await asyncio.sleep(INVITE_SECONDS)

    async with LOCK:
        game = GAMES.get(game_id)

        if not game or game["status"] != "open":
            return

        game["status"] = "closed"
        chat_id = game["chat_id"]
        message_id = game["message_id"]

        GAMES.pop(game_id, None)

    try:
        await bot.edit_message_text(
            "⌛ Düello davetinin süresi doldu. "
            "Yeni bir davet gönderebilirsiniz.",
            chat_id=chat_id,
            message_id=message_id,
        )
    except Exception:
        pass


async def publish_betting_messages(game_id, bot):
    """
    Her 15 saniyede bir eski duyuruyu siler,
    yenisini gönderir. Bahis süresince tekrarlar.
    """

    for _ in range(BETTING_SECONDS // ANNOUNCEMENT_INTERVAL):
        game = GAMES.get(game_id)

        if not game or game["status"] != "betting":
            return

        chat_id = game["chat_id"]
        old_message_id = game.get("bet_announcement_id")

        if old_message_id:
            try:
                await bot.delete_message(
                    chat_id=chat_id,
                    message_id=old_message_id,
                )
            except Exception:
                pass

        game = GAMES.get(game_id)

        if not game or game["status"] != "betting":
            return

        try:
            sent = await bot.send_message(
                chat_id=chat_id,
                text=(
                    "🔫 <b>BİRBİRLERİNE SİLAH ÇEKEN KULLANICILAR!</b>\n\n"
                    f"⚔️ <b>{escape(game['creator_name'])} VS "
                    f"{escape(game['opponent_name'])}</b>\n\n"
                    "🎯 Düellonun sonucunu tahmin et!\n"
                    "💰 Bahis yapmak için aşağıdaki butona bas.\n\n"
                    "⏳ Bahis süresi: 60 saniye"
                ),
                reply_markup=bet_join_keyboard(game_id),
                parse_mode="HTML",
            )

            game["bet_announcement_id"] = sent.message_id

        except Exception:
            pass

        await asyncio.sleep(ANNOUNCEMENT_INTERVAL)


@router.callback_query(F.data.startswith("rr:"))
async def roulette_callback(callback: CallbackQuery):
    if not callback.message:
        await callback.answer(
            "Bu işlem kullanılamıyor.",
            show_alert=True
        )
        return

    parts = (callback.data or "").split(":")

    if len(parts) < 3:
        await callback.answer(
            "Geçersiz işlem.",
            show_alert=True
        )
        return

    action = parts[1]
    game_id = parts[2]

    game = GAMES.get(game_id)

    if not game or game["chat_id"] != callback.message.chat.id:
        await callback.answer(
            "Bu oyun artık geçerli değil.",
            show_alert=True
        )
        return

    uid = callback.from_user.id

    # DÜELLOYU KABUL ETME / REDDETME
    if action in ("accept", "decline"):
        async with LOCK:
            game = GAMES.get(game_id)

            if not game or game["status"] != "open":
                await callback.answer(
                    "Bu davet artık açık değil.",
                    show_alert=True
                )
                return

            if uid != game["opponent"]:
                await callback.answer(
                    "Bu davet yalnızca davet edilen oyuncuya ait.",
                    show_alert=True
                )
                return

            if action == "decline":
                game["status"] = "closed"
                GAMES.pop(game_id, None)

                await callback.message.edit_text(
                    f"🏃 {escape(game['opponent_name'])} "
                    "düellodan korkup kaçtı!",
                    parse_mode="HTML",
                )

                await callback.answer(
                    "Düelloyu reddettin."
                )
                return

            async with AsyncSessionLocal() as session:
                opponent = await locked_user(session, uid)
                creator = await locked_user(
                    session, game["creator"]
                )

                if opponent is None or creator is None:
                    await callback.answer(
                        "İki oyuncunun da botta hesabı bulunmalı. "
                        "Önce özelden /start yazın.",
                        show_alert=True,
                    )
                    return

            game["status"] = "betting"
            game["bets"] = {}
            game["choices"] = {}

            await callback.message.edit_text(
                "🔫 <b>DÜELLO KABUL EDİLDİ!</b>\n\n"
                f"<b>{escape(game['creator_name'])} VS "
                f"{escape(game['opponent_name'])}</b>\n\n"
                "📢 Bahisler başladı!\n"
                "💰 Gruptaki herkes bahis yapabilir.\n"
                f"⏳ Bahis süresi: {BETTING_SECONDS} saniye",
                parse_mode="HTML",
            )

        asyncio.create_task(
            publish_betting_messages(game_id, callback.bot)
        )
        asyncio.create_task(
            close_betting(game_id, callback.bot)
        )

        await callback.answer(
            "Düello kabul edildi! Bahisler başladı."
        )
        return

    # BAHİS YAP BUTONU
    if action == "join":
        if game["status"] != "betting":
            await callback.answer(
                "Bahis süresi sona erdi!",
                show_alert=True
            )
            return

        await callback.message.answer(
            "🔫 <b>HANGİ SONUCA BAHİS YAPIYORSUN?</b>\n\n"
            f"🟢 {escape(game['creator_name'])} yaşar\n"
            f"🟢 {escape(game['opponent_name'])} yaşar\n"
            "💀 İkisi de ölür\n"
            "❤️ İkisi de yaşar",
            reply_markup=betting_keyboard(
                game_id,
                game["creator_name"],
                game["opponent_name"],
            ),
            parse_mode="HTML",
        )

        await callback.answer(
            "Tahminini seç!"
        )
        return

    # SONUÇ SEÇİMİ
    if action == "pick":
        if len(parts) != 4:
            await callback.answer(
                "Geçersiz bahis seçimi.",
                show_alert=True
            )
            return

        choice = parts[3]

        if choice not in OUTCOMES:
            await callback.answer(
                "Geçersiz sonuç.",
                show_alert=True
            )
            return

        async with LOCK:
            game = GAMES.get(game_id)

            if not game or game["status"] != "betting":
                await callback.answer(
                    "Bahis süresi sona erdi.",
                    show_alert=True
                )
                return

            previous_choice = game["choices"].get(uid)

            if previous_choice and previous_choice != choice:
                await callback.answer(
                    "Bir kez sonuç seçebilirsin. "
                    "Seçimini değiştiremezsin!",
                    show_alert=True,
                )
                return

            game["choices"][uid] = choice

            PENDING_BETS[(game["chat_id"], uid)] = {
                "game_id": game_id,
                "choice": choice,
            }

        await callback.answer(
            "Sonuç seçildi."
        )

        await callback.message.answer(
            f"{escape(callback.from_user.full_name)}, "
            f"seçimin: {outcome_label(game, choice)}\n"
            "Yatırmak istediğin toplam bahis miktarını şimdi yaz.\n"
            "Bahis miktarı mevcut en yüksek bahisten yüksek olmalıdır."
        )
        return

    await callback.answer(
        "Bilinmeyen işlem.",
        show_alert=True
    )


@router.message()
async def handle_bet_amount(message: Message):
    remember_group_user(message)

    if message.chat.type not in ("group", "supergroup"):
        return

    if not message.from_user:
        return

    pending_key = (
        message.chat.id,
        message.from_user.id
    )

    pending = PENDING_BETS.get(pending_key)

    if not pending:
        return

    text = (message.text or "").strip()

    if not text or text.startswith("/"):
        return

    try:
        amount = float(text.replace(",", "."))

        if not math.isfinite(amount) or amount <= 0:
            raise ValueError

        amount = round(amount, 2)

    except ValueError:
        await message.answer(
            "❌ Geçerli bir pozitif bahis miktarı yaz. "
            "Örnek: 250 veya 250,50"
        )
        return

    async with LOCK:
        game = GAMES.get(pending["game_id"])

        if not game or game["status"] != "betting":
            PENDING_BETS.pop(pending_key, None)
            await message.answer(
                "⌛ Bahis süresi sona ermiş."
            )
            return

        choice = pending["choice"]
        old_bet = game["bets"].get(message.from_user.id)

        if old_bet and old_bet["choice"] != choice:
            PENDING_BETS.pop(pending_key, None)
            await message.answer(
                "❌ Daha önce başka bir sonuç seçtin. "
                "Seçimini değiştiremezsin."
            )
            return

        highest = max(
            (
                bet["amount"]
                for bet in game["bets"].values()
            ),
            default=0.0,
        )

        if amount <= highest:
            await message.answer(
                "❌ <b>BAHİS KABUL EDİLMEDİ!</b>\n\n"
                f"📈 Şu anki en yüksek bahis: "
                f"<b>{fmt_amount(highest)} Sanal Kredi</b>\n"
                "Daha yüksek bir miktar yazmalısın.",
                parse_mode="HTML",
            )
            return

        old_amount = (
            old_bet["amount"] if old_bet else 0.0
        )

        if amount <= old_amount:
            await message.answer(
                f"❌ Bahsini artırmalısın. "
                f"Mevcut bahsin: {fmt_amount(old_amount)} "
                "Sanal Kredi."
            )
            return

        difference = round(amount - old_amount, 2)

        async with AsyncSessionLocal() as session:
            user = await locked_user(
                session,
                message.from_user.id
            )

            if user is None:
                await message.answer(
                    "❌ Önce botu özelden /start komutuyla "
                    "başlatıp hesap oluşturmalısın."
                )
                return

            balance = user.balance or 0.0

            if balance < difference:
                await message.answer(
                    f"❌ Yetersiz bakiye. "
                    f"Gerekli ek miktar: {fmt_amount(difference)} | "
                    f"Bakiyen: {fmt_amount(balance)} Sanal Kredi"
                )
                return

            user.balance = balance - difference
            await session.commit()

        game["bets"][message.from_user.id] = {
            "choice": choice,
            "amount": amount,
            "name": message.from_user.full_name,
        }

        PENDING_BETS.pop(pending_key, None)

        await message.answer(
            f"✅ {escape(message.from_user.full_name)} "
            "bahsi kabul edildi!\n"
            f"🎯 Seçim: <b>{outcome_label(game, choice)}</b>\n"
            f"💰 Toplam bahsin: "
            f"<b>{fmt_amount(amount)} Sanal Kredi</b>",
            parse_mode="HTML",
)
async def close_betting(game_id, bot):
    await asyncio.sleep(BETTING_SECONDS)

    async with LOCK:
        game = GAMES.get(game_id)

        if not game or game["status"] != "betting":
            return

        game["status"] = "settling"

        bets = dict(game["bets"])
        chat_id = game["chat_id"]
        message_id = game["message_id"]
        announcement_id = game.get("bet_announcement_id")

        result_key = random.choice(list(OUTCOMES.keys()))

    # Son bahis duyurusunu sil
    if announcement_id:
        try:
            await bot.delete_message(
                chat_id=chat_id,
                message_id=announcement_id,
            )
        except Exception:
            pass

    # Tüm bahisleri kuruşa çevirerek hesapla
    total_cents = sum(
        int(round(bet["amount"] * 100))
        for bet in bets.values()
    )

    winners = {
        uid: bet
        for uid, bet in bets.items()
        if bet["choice"] == result_key
    }

    payouts = {}

    # Kazanan varsa havuzu kazananlara oranlı dağıt
    if bets and winners:
        winning_cents = sum(
            int(round(bet["amount"] * 100))
            for bet in winners.values()
        )

        distributed = 0
        winner_ids = sorted(winners)

        for uid in winner_ids[:-1]:
            stake_cents = int(
                round(winners[uid]["amount"] * 100)
            )

            share = (
                total_cents * stake_cents
            ) // winning_cents

            payouts[uid] = share
            distributed += share

        # Kuruş farkını son kazanana ver
        if winner_ids:
            last_uid = winner_ids[-1]
            payouts[last_uid] = total_cents - distributed

    # Hiç kazanan yoksa herkesin bahsini iade et
    elif bets:
        for uid, bet in bets.items():
            payouts[uid] = int(
                round(bet["amount"] * 100)
            )

    # Kazançları veya iadeleri hesaplara yatır
    async with AsyncSessionLocal() as session:
        for uid, cents in payouts.items():
            if cents <= 0:
                continue

            user = await locked_user(session, uid)

            if user is not None:
                current_balance = user.balance or 0.0
                user.balance = round(
                    current_balance + (cents / 100),
                    2,
                )

        await session.commit()

    # Sonuç mesajını hazırla
    result_text = outcome_result(game, result_key)

    if not bets:
        betting_text = (
            "💰 Bu düelloya bahis yapan olmadı."
        )
    elif not winners:
        betting_text = (
            "😮 Hiç kimse doğru tahmin edemedi!\n"
            "💰 Herkesin bahsi iade edildi."
        )
    else:
        winner_lines = []

        for uid, bet in winners.items():
            paid = payouts.get(uid, 0) / 100

            winner_lines.append(
                f"🏆 {escape(bet['name'])}: "
                f"+{fmt_amount(paid)} Sanal Kredi"
            )

        betting_text = (
            "🏆 <b>KAZANAN BAHİSLER</b>\n"
            + "\n".join(winner_lines)
        )

    final_text = (
        "🔫 <b>RUS RULETİ SONUÇLANDI!</b>\n\n"
        f"⚔️ <b>{escape(game['creator_name'])} VS "
        f"{escape(game['opponent_name'])}</b>\n\n"
        f"<b>{result_text}</b>\n\n"
        f"{betting_text}\n\n"
        f"💰 Toplam bahis havuzu: "
        f"<b>{fmt_amount(total_cents / 100)} Sanal Kredi</b>"
    )

    try:
        await bot.edit_message_text(
            final_text,
            chat_id=chat_id,
            message_id=message_id,
            parse_mode="HTML",
        )
    except Exception:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=final_text,
                parse_mode="HTML",
            )
        except Exception:
            pass

    # Bu oyuna ait bekleyen bahis seçimlerini temizle
    for key, pending in list(PENDING_BETS.items()):
        if pending.get("game_id") == game_id:
            PENDING_BETS.pop(key, None)

    # Oyunu kapat
    async with LOCK:
        game = GAMES.get(game_id)

        if game:
            game["status"] = "closed"
            GAMES.pop(game_id, None)

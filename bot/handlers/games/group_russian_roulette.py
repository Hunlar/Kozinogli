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

# Ayarlar
INVITE_SECONDS = 60
BETTING_SECONDS = 60

# Oyun verileri bellekte tutulur. Bot yeniden başlatılırsa devam eden oyunlar sıfırlanır.
GAMES = {}
SEEN_USERS = {}       # {chat_id: {username: {"id": ..., "name": ...}}}
PENDING_BETS = {}     # {(chat_id, user_id): {"game_id": ..., "choice": ...}}
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


def invite_keyboard(game_id):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🤝 KABUL ET", callback_data=f"rr:accept:{game_id}"),
        InlineKeyboardButton(text="🏃 KORKTUM", callback_data=f"rr:decline:{game_id}"),
    ]])


def betting_keyboard(game_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🟢 A yaşar", callback_data=f"rr:pick:{game_id}:a_alive"),
            InlineKeyboardButton(text="🟢 B yaşar", callback_data=f"rr:pick:{game_id}:b_alive"),
        ],
        [
            InlineKeyboardButton(text="💀 İkisi de ölür", callback_data=f"rr:pick:{game_id}:both_die"),
            InlineKeyboardButton(text="❤️ İkisi de yaşar", callback_data=f"rr:pick:{game_id}:both_live"),
        ],
    ])


async def locked_user(session, telegram_id):
    result = await session.execute(
        select(User).where(User.tg_id == telegram_id).with_for_update()
    )
    return result.scalar_one_or_none()


def remember_group_user(message: Message):
    """Grupta daha önce mesaj gönderen kullanıcıların @kullanıcı adlarını tanır."""
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
    return user_id == game.get("creator") or user_id == game.get("opponent")


@router.message(Command("kayit"))
async def register_group_username(message: Message):
    """@username ile davet edilebilmek için kullanıcıyı bu grupta tanıtır."""
    remember_group_user(message)
    if message.chat.type not in ("group", "supergroup"):
        await message.answer("Bu komut yalnızca grupta kullanılabilir.")
        return
    if not message.from_user or not message.from_user.username:
        await message.answer("❌ Telegram kullanıcı adın (@username) bulunmuyor.")
        return
    await message.answer(
        f"✅ @{escape(message.from_user.username)} Rus Ruleti davetleri için kaydedildi."
    )


@router.message(Command("rulet"))
async def create_duel(message: Message):
    remember_group_user(message)

    if message.chat.type not in ("group", "supergroup"):
        await message.answer("🔫 Bu komut yalnızca gruplarda kullanılabilir.")
        return

    if not message.from_user or message.from_user.is_bot:
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("Kullanım: /rulet @username")
        return

    username = parts[1].strip().split()[0]
    if not re.fullmatch(r"@?[A-Za-z0-9_]{5,32}", username):
        await message.answer("❌ Geçerli bir kullanıcı adı yaz. Örnek: /rulet @username")
        return

    username = username.lstrip("@").lower()
    target = SEEN_USERS.get(message.chat.id, {}).get(username)
    if target is None:
        await message.answer(
            f"❌ @{username} kullanıcısını henüz bu grupta göremedim.\n"
            "Önce gruba bir mesaj yazmasını iste, sonra tekrar dene."
        )
        return

    creator_id = message.from_user.id
    target_id = target["id"]

    if target_id == creator_id:
        await message.answer("😈 Kendine meydan okuyamazsın!")
        return

    async with LOCK:
        for game in GAMES.values():
            if game["status"] in ("open", "betting", "settling") and (
                active_player(game, creator_id) or active_player(game, target_id)
            ):
                await message.answer("❌ Senin veya seçtiğin oyuncunun zaten devam eden bir düellosu var.")
                return

    async with AsyncSessionLocal() as session:
        creator_result = await session.execute(select(User).where(User.tg_id == creator_id))
        target_result = await session.execute(select(User).where(User.tg_id == target_id))
        creator = creator_result.scalar_one_or_none()
        target_user = target_result.scalar_one_or_none()

        if creator is None or target_user is None:
            await message.answer(
                "❌ İki oyuncunun da önce botu özelden /start komutuyla başlatıp hesap oluşturması gerekiyor."
            )
            return

    game_id = secrets.token_hex(4)
    game = {
        "chat_id": message.chat.id,
        "chat_type": message.chat.type,
        "message_id": None,
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
        f"<b>{escape(message.from_user.full_name)} VS {escape(target['name'])}</b>\n\n"
        f"{escape(target['name'])}, seni Rus Ruletine davet ediyor!\n"
        "Kabul edecek misin, yoksa korkup gidecek misin? 😈",
        reply_markup=invite_keyboard(game_id),
        parse_mode="HTML",
    )

    game["message_id"] = sent.message_id
    GAMES[game_id] = game
    asyncio.create_task(expire_invite(game_id, message.bot))


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
            "⌛ Düello davetinin süresi doldu. Yeni bir davet gönderebilirsiniz.",
            chat_id=chat_id,
            message_id=message_id,
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("rr:"))
async def roulette_callback(callback: CallbackQuery):
    if not callback.message:
        await callback.answer("Bu işlem kullanılamıyor.", show_alert=True)
        return

    parts = (callback.data or "").split(":")
    if len(parts) < 3:
        await callback.answer("Geçersiz işlem.", show_alert=True)
        return

    action, game_id = parts[1], parts[2]
    game = GAMES.get(game_id)

    if not game or game["chat_id"] != callback.message.chat.id:
        await callback.answer("Bu oyun artık geçerli değil.", show_alert=True)
        return

    uid = callback.from_user.id

    if action in ("accept", "decline"):
        async with LOCK:
            game = GAMES.get(game_id)
            if not game or game["status"] != "open":
                await callback.answer("Bu davet artık açık değil.", show_alert=True)
                return

            if uid != game["opponent"]:
                await callback.answer("Bu davet yalnızca davet edilen oyuncuya ait.", show_alert=True)
                return

            if action == "decline":
                game["status"] = "closed"
                GAMES.pop(game_id, None)
                await callback.message.edit_text(
                    f"🏃 {escape(game['opponent_name'])} düellodan korkup kaçtı!"
                    , parse_mode="HTML"
                )
                await callback.answer("Düelloyu reddettin.")
                return

            async with AsyncSessionLocal() as session:
                opponent = await locked_user(session, uid)
                creator = await locked_user(session, game["creator"])
                if opponent is None or creator is None:
                    await callback.answer(
                        "İki oyuncunun da botta hesabı bulunmalı. Önce özelden /start yazın.",
                        show_alert=True,
                    )
                    return

            game["status"] = "betting"
            game["bets"] = {}
            await callback.message.edit_text(
                "🔫 <b>DÜELLO KABUL EDİLDİ!</b>\n\n"
                f"<b>{escape(game['creator_name'])} VS {escape(game['opponent_name'])}</b>\n\n"
                "📢 Bahisler açıldı! Herkes aşağıdaki dört sonuçtan yalnızca birini seçebilir.\n"
                f"⏳ Bahis süresi: {BETTING_SECONDS} saniye\n\n"
                "💰 Yeni bahis, mevcut en yüksek bahisten yüksek olmalıdır.\n"
                "Bahis miktarını artırırken aynı sonucu seçip yeni toplam miktarı yazın.\n\n"
                "👇 Bahis yapmak için sonucunu seç:",
                reply_markup=betting_keyboard(game_id),
                parse_mode="HTML",
            )
            asyncio.create_task(close_betting(game_id, callback.bot))
            await callback.answer("Düelloyu kabul ettin! Bahisler başladı.")
            return

    if action == "pick":
        if len(parts) != 4:
            await callback.answer("Geçersiz bahis seçimi.", show_alert=True)
            return

        choice = parts[3]
        if choice not in OUTCOMES:
            await callback.answer("Geçersiz sonuç.", show_alert=True)
            return

        async with LOCK:
            game = GAMES.get(game_id)
            if not game or game["status"] != "betting":
                await callback.answer("Bahis süresi sona erdi.", show_alert=True)
                return

            previous_choice = game["choices"].get(uid)
            if previous_choice and previous_choice != choice:
                await callback.answer(
                    "Bir kez sonuç seçebilirsin. Seçimini değiştiremezsin!",
                    show_alert=True,
                )
                return

            game["choices"][uid] = choice
            PENDING_BETS[(game["chat_id"], uid)] = {
                "game_id": game_id,
                "choice": choice,
            }

        await callback.answer("Sonuç seçildi.")
        await callback.message.answer(
            f"{callback.from_user.full_name}, seçimin: {OUTCOMES[choice]}\n"
            "Yatırmak istediğin toplam bahis miktarını şimdi yaz.\n"
            "Bahis miktarı mevcut en yüksek bahisten yüksek olmalıdır."
        )
        return

    await callback.answer("Bilinmeyen işlem.", show_alert=True)


@router.message()
async def handle_bet_amount(message: Message):
    # Bu genel mesaj yakalayıcısı, grup kullanıcı adlarını da tanımaya yarar.
    remember_group_user(message)

    if message.chat.type not in ("group", "supergroup") or not message.from_user:
        return

    pending_key = (message.chat.id, message.from_user.id)
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
        await message.answer("❌ Geçerli bir pozitif bahis miktarı yaz. Örnek: 250 veya 250,50")
        return

    async with LOCK:
        game = GAMES.get(pending["game_id"])
        if not game or game["status"] != "betting":
            PENDING_BETS.pop(pending_key, None)
            await message.answer("⌛ Bahis süresi sona ermiş.")
            return

        choice = pending["choice"]
        old_bet = game["bets"].get(message.from_user.id)
        if old_bet and old_bet["choice"] != choice:
            PENDING_BETS.pop(pending_key, None)
            await message.answer("❌ Daha önce başka bir sonuç seçtin. Seçimini değiştiremezsin.")
            return

        highest = max(
            (bet["amount"] for bet in game["bets"].values()),
            default=0.0,
        )

        if amount <= highest:
            await message.answer(
                "❌ <b>BAHİS KABUL EDİLMEDİ!</b>\n\n"
                f"📈 Şu anki en yüksek bahis: <b>{fmt_amount(highest)} Sanal Kredi</b>\n"
                f"Bu bahse katılmak veya bahsini yükseltmek için "
                f"<b>{fmt_amount(highest)} Sanal Kredi'den daha yüksek</b> bir miktar yazmalısın.",
                parse_mode="HTML",
            )
            return

        old_amount = old_bet["amount"] if old_bet else 0.0
        if amount <= old_amount:
            await message.answer(
                f"❌ Bahsini artırmalısın. Mevcut bahsin: {fmt_amount(old_amount)} Sanal Kredi."
            )
            return

        difference = round(amount - old_amount, 2)

        async with AsyncSessionLocal() as session:
            user = await locked_user(session, message.from_user.id)
            if user is None:
                await message.answer("❌ Önce botu özelden /start komutuyla başlatıp hesap oluşturmalısın.")
                return

            balance = user.balance or 0.0
            if balance < difference:
                await message.answer(
                    f"❌ Yetersiz bakiye. Gerekli ek miktar: {fmt_amount(difference)} | "
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
            f"✅ {escape(message.from_user.full_name)} bahsi kabul edildi!\n"
            f"🎯 Seçim: <b>{OUTCOMES[choice]}</b>\n"
            f"💰 Toplam bahsin: <b>{fmt_amount(amount)} Sanal Kredi</b>",
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
        result_key = random.choice(list(OUTCOMES.keys()))

    total_cents = sum(int(round(bet["amount"] * 100)) for bet in bets.values())
    winners = {
        uid: bet for uid, bet in bets.items()
        if bet["choice"] == result_key
    }

    payouts = {}
    if bets and winners:
        winning_cents = sum(int(round(bet["amount"] * 100)) for bet in winners.values())
        distributed = 0
        winner_ids = sorted(winners)
        for uid in winner_ids[:-1]:
            stake_cents = int(round(winners[uid]["amount"] * 100))
            share = total_cents * stake_cents // winning_cents
            payouts[uid] = share
            distributed += share
        payouts[winner_ids[-1]] = total_cents - distributed
    elif bets:
        # Hiç kimse doğru sonucu tahmin edemezse herkesin bahsi iade edilir.
        payouts = {
            uid: int(round(bet["amount"] * 100))
            for uid, bet in bets.items()
        }

    final_balances = {}
    try:
        if payouts:
            async with AsyncSessionLocal() as session:
                ids = sorted(payouts)
                result = await session.execute(
                    select(User)
                    .where(User.tg_id.in_(ids))
                    .order_by(User.tg_id)
                    .with_for_update()
                )
                users = {user.tg_id: user for user in result.scalars().all()}

                missing = set(ids) - set(users)
                if missing:
                    raise RuntimeError(f"Bahis hesabı bulunamayan kullanıcılar: {missing}")

                for uid, cents in payouts.items():
                    user = users[uid]
                    user.balance = (user.balance or 0.0) + (cents / 100)
                    final_balances[uid] = user.balance

                await session.commit()

        result_text = OUTCOME_RESULTS[result_key]
        lines = [
            "🔫 <b>RUS RULETİ SONUÇLANDI!</b>",
            "",
            f"<b>{escape(game['creator_name'])} VS {escape(game['opponent_name'])}</b>",
            result_text,
            "",
            f"📊 Toplam bahis havuzu: <b>{fmt_amount(total_cents / 100)} Sanal Kredi</b>",
        ]

        if not bets:
            lines.extend(["", "Bu düelloda bahis yapan olmadı."])
        elif winners:
            lines.extend(["", "🏆 <b>Doğru tahmin edenler:</b>"])
            for uid, bet in winners.items():
                paid = payouts.get(uid, 0) / 100
                lines.append(
                    f"• {escape(bet['name'])}: +{fmt_amount(paid)} Sanal Kredi"
                )
            lines.append("\nKazanan bahisçiler havuzu bahisleri oranında paylaştı.")
        else:
            lines.extend([
                "",
                "😮 Bu sonucu doğru tahmin eden olmadı.",
                "Yatırılan bahisler sahiplerine iade edildi.",
            ])

        await bot.edit_message_text(
            "\n".join(lines),
            chat_id=chat_id,
            message_id=message_id,
            parse_mode="HTML",
        )

        for uid, bet in bets.items():
            try:
                await check_bankruptcy(
                    bot=bot,
                    telegram_id=uid,
                    chat_id=chat_id,
                    chat_type=game["chat_type"],
                    first_name=bet["name"],
                )
            except Exception:
                pass

    except Exception as exc:
        # Para hareketinde hata olursa oyunu kapatmadan hata mesajı bırak.
        try:
            await bot.send_message(
                chat_id,
                "❌ Bahisler sonuçlandırılırken bir hata oluştu. Yönetici kontrolü gerekiyor."
            )
        except Exception:
            pass
        game["status"] = "error"
        raise exc

    async with LOCK:
        game = GAMES.pop(game_id, None)
        if game:
            for key, value in list(PENDING_BETS.items()):
                if value.get("game_id") == game_id:
                    PENDING_BETS.pop(key, None)
              

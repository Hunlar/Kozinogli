
import logging

from aiogram import Bot
from sqlalchemy import select

from db.database import AsyncSessionLocal
from db.models import User


BANKRUPTCY_LIMIT = 4000

logger = logging.getLogger(__name__)


async def check_bankruptcy(
    bot: Bot,
    telegram_id: int,
    chat_id: int,
    chat_type: str,
    first_name: str
):

    should_notify = False
    balance = 0

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(User)
            .where(User.tg_id == telegram_id)
            .with_for_update()
        )

        user = result.scalar_one_or_none()

        if user is None:
            return

        balance = user.balance or 0

        if balance >= BANKRUPTCY_LIMIT:
            user.is_bankrupt = False
            user.bankruptcy_announced = False
            user.bankruptcy_chat_id = None
            await session.commit()
            return

        # İlk kez iflas ediyorsa bildirimi hazırla.
        if not user.is_bankrupt:
            user.is_bankrupt = True

            if not user.bankruptcy_announced:
                user.bankruptcy_announced = True
                should_notify = True

        await session.commit()

    if not should_notify:
        return

    text = (
        "🚨 <b>ÖZVEGAS İFLAS BİLDİRİMİ</b>\n\n"
        "💸 Hesabın iflas etti!\n\n"
        f"🪙 Mevcut bakiyen: <b>{balance:,.2f}</b>\n"
        f"📉 İflas sınırı: <b>{BANKRUPTCY_LIMIT:,}</b>\n\n"
        "Yeni oyunlara başlayabilmek için "
        "ÖzVeGas kasasından borç almalısın.\n\n"
        "🏦 Borç almak için: /borc\n"
        "📋 Borçlarını görmek için: /borclarim"
    )

    try:
        # Yalnızca iflas eden kullanıcıya özel mesaj.
        await bot.send_message(
            chat_id=telegram_id,
            text=text,
            parse_mode="HTML"
        )

    except Exception:
        logger.exception(
            "Özel iflas bildirimi gönderilemedi: %s",
            telegram_id
        )

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User).where(
                    User.tg_id == telegram_id
                )
            )

            user = result.scalar_one_or_none()

            if user is not None:
                user.bankruptcy_announced = False
                await session.commit()
                


import os
import logging
import html

from aiogram import Bot
from sqlalchemy import select

from db.database import AsyncSessionLocal
from db.models import User


BANKRUPTCY_LIMIT = 4000

BANKRUPTCY_VIDEO_FILE_ID = os.getenv(
    "BANKRUPTCY_VIDEO_FILE_ID",
    ""
)

logger = logging.getLogger(__name__)


async def check_bankruptcy(
    bot: Bot,
    telegram_id: int,
    chat_id: int,
    chat_type: str,
    first_name: str
):
    announcement_chat_id = None
    should_announce = False
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

        if not user.is_bankrupt:
            user.is_bankrupt = True

            if chat_type in ("group", "supergroup"):
                user.bankruptcy_chat_id = chat_id

        announcement_chat_id = user.bankruptcy_chat_id

        if (
            announcement_chat_id is not None
            and not user.bankruptcy_announced
        ):
            user.bankruptcy_announced = True
            should_announce = True

        await session.commit()

    if not should_announce:
        return

    safe_name = html.escape(first_name or "Oyuncu")

    text = (
        "🚨 <b>ÖZVEGAS İFLAS HABERİ!</b> 🚨\n\n"
        f"🎭 <a href=\"tg://user?id={telegram_id}\">{safe_name}</a> "
        "oyun masasında iflas etti!\n\n"
        f"💸 Kalan bakiye: <b>{balance:,.2f} Sanal Kredi</b>\n"
        "🏦 Kurtuluş için ÖzVeGas kasasından borç alması gerekiyor.\n\n"
        "😂 Kolpaçino ekibi bu iflası unutmayacak!"
    )

    try:
        await bot.send_message(
            chat_id=announcement_chat_id,
            text=text,
            parse_mode="HTML"
        )

        if BANKRUPTCY_VIDEO_FILE_ID:
            await bot.send_video(
                chat_id=announcement_chat_id,
                video=BANKRUPTCY_VIDEO_FILE_ID,
                caption="🎬 ÖzVeGas iflas arşivinden özel gösterim!"
            )

    except Exception:
        logger.exception(
            "İflas duyurusu gönderilemedi: %s",
            announcement_chat_id
        )

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User).where(User.tg_id == telegram_id)
            )
            user = result.scalar_one_or_none()

            if user is not None:
                user.bankruptcy_announced = False
                await session.commit()
      

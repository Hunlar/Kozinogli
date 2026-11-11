
import asyncio
import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import update, func

from db.database import AsyncSessionLocal
from db.models import User


ISTANBUL = ZoneInfo("Europe/Istanbul")
DAILY_CREDIT = 20_000
BANKRUPTCY_LIMIT = 4_000

logger = logging.getLogger(__name__)


async def grant_daily_credits():
    today = datetime.now(ISTANBUL).date()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            update(User)
            .where(
                (User.daily_credit_date.is_(None))
                | (User.daily_credit_date < today)
            )
            .values(
                balance=func.coalesce(User.balance, 0) + DAILY_CREDIT,
                daily_credit_date=today
            )
        )

        await session.commit()

        # Günlük kredi sonrası iflas durumunu düzelt.
        await session.execute(
            update(User)
            .where(
                User.balance >= BANKRUPTCY_LIMIT,
                User.is_bankrupt.is_(True)
            )
            .values(
                is_bankrupt=False,
                bankruptcy_announced=False,
                bankruptcy_chat_id=None
            )
        )

        await session.commit()

        logger.info(
            "Günlük kredi dağıtımı tamamlandı. "
            "Dağıtım yapılan kullanıcı: %s",
            result.rowcount
        )


async def daily_credit_loop():
    while True:
        now = datetime.now(ISTANBUL)
        tomorrow = now.date() + timedelta(days=1)

        next_midnight = datetime.combine(
            tomorrow,
            time.min,
            tzinfo=ISTANBUL
        )

        seconds = (next_midnight - now).total_seconds()

        await asyncio.sleep(max(seconds, 1))
        await grant_daily_credits()


import asyncio
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import update, func

from db.database import AsyncSessionLocal
from db.models import User


ISTANBUL = ZoneInfo("Europe/Istanbul")
DAILY_CREDIT = 20_000


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

        print(
            f"Günlük kredi dağıtımı tamamlandı. "
            f"Dağıtım yapılan kullanıcı: {result.rowcount}"
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
      

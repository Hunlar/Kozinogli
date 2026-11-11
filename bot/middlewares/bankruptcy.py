
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select

from db.database import AsyncSessionLocal
from db.models import User


BANKRUPTCY_LIMIT = 4000


# Bahis yatırıldıktan sonra tamamlanmasına izin verilen oyun durumları.
ACTIVE_GAME_STATES = {
    # Blackjack
    "BlackjackStates:PLAYER_TURN",

    # Mayınlar
    "MinesStates:CHOOSE_MINES",
    "MinesStates:PLAYING",

    # Roket
    "CrashStates:COEFF_INPUT",
    "CrashStates:FLYING",

    # Çift / Tek
    "EvenOddStates:CHOICE",
}


class BankruptcyMiddleware(BaseMiddleware):

    async def __call__(self, handler, event, data):

        telegram_user = getattr(event, "from_user", None)

        if telegram_user is None:
            return await handler(event, data)

        # Devam eden oyunun tamamlanmasına izin ver.
        fsm_state = data.get("state")

        if fsm_state is not None:
            try:
                current_state = await fsm_state.get_state()

                if current_state in ACTIVE_GAME_STATES:
                    return await handler(event, data)

            except Exception:
                # FSM kontrolü başarısız olursa bakiye kontrolüne devam et.
                pass

        async with AsyncSessionLocal() as session:

            result = await session.execute(
                select(User).where(
                    User.tg_id == telegram_user.id
                )
            )

            user = result.scalar_one_or_none()

            if user is None:
                return await handler(event, data)

            balance = user.balance or 0

        if balance < BANKRUPTCY_LIMIT:

            warning = (
                "💸 İFLAS ETTİN!\n\n"
                f"🪙 Mevcut bakiyen: {balance:,.2f} "
                "Sanal Kredi\n"
                f"📉 İflas sınırı: {BANKRUPTCY_LIMIT:,} "
                "Sanal Kredi\n\n"
                "Yeni oyunlara başlayabilmek için "
                "ÖzVeGas kasasından borç almalısın.\n\n"
                "🏦 Borç işlemi: /borc\n"
                "📋 Borçlarını görüntüle: /borclarim"
            )

            if isinstance(event, Message):
                await event.answer(warning)

            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "💸 İflas ettin! Yeni oyunlara "
                    "başlamak için borç almalısın.",
                    show_alert=True
                )

            return

        return await handler(event, data)

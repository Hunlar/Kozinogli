
import logging

from aiogram import Router, BaseMiddleware
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from settings import ADMINS

router = Router()
logger = logging.getLogger(__name__)

REQUIRED_CHANNEL = -1004326403524
CHANNEL_USERNAME = "@sancakmain"

def subscription_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Kanalımıza Katıl",
                    url="https://t.me/sancakmain"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Üyeliğimi Kontrol Et",
                    callback_data="check_subscription"
                )
            ]
        ]
    )


async def check_membership(bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(
            chat_id=REQUIRED_CHANNEL,
            user_id=user_id
        )

        if member.status in ("creator", "administrator", "member"):
            return True

        if member.status == "restricted" and member.is_member:
            return True

        return False

    except Exception:
        logger.exception(
            "Kanal üyeliği kontrol edilemedi: %s",
            user_id
        )
        return False


class SubscriptionMiddleware(BaseMiddleware):

    async def __call__(self, handler, event, data):

        user = getattr(event, "from_user", None)

        if user is None:
            return await handler(event, data)

        chat_type = None

        if isinstance(event, Message):
            chat_type = event.chat.type

        elif isinstance(event, CallbackQuery):
            if event.message:
                chat_type = event.message.chat.type

        if chat_type in ("group", "supergroup"):
            return await handler(event, data)

        if chat_type != "private":
            return await handler(event, data)

        # Adminler zorunlu abonelikten muaftır.
        if user.id in ADMINS:
            return await handler(event, data)

        if (
            isinstance(event, CallbackQuery)
            and event.data == "check_subscription"
        ):
            return await handler(event, data)

        bot = data["bot"]

        if await check_membership(bot, user.id):
            return await handler(event, data)

        text = (
            "🔒 **ÖzVeGas'a Devam Etmek İçin**\n\n"
            "Devam etmek için @sancakmain kanalımıza "
            "katılmalısın.\n\n"
            "Katıldıktan sonra üyeliğini kontrol et."
        )

        if isinstance(event, Message):
            await event.answer(
                text,
                reply_markup=subscription_keyboard(),
                parse_mode="Markdown"
            )

        elif isinstance(event, CallbackQuery):
            if event.message:
                await event.message.answer(
                    text,
                    reply_markup=subscription_keyboard(),
                    parse_mode="Markdown"
                )

            await event.answer()

        return None


@router.callback_query(
    lambda callback: callback.data == "check_subscription"
)
async def verify_subscription(callback: CallbackQuery):

    if (
        callback.message is None
        or callback.message.chat.type != "private"
    ):
        await callback.answer()
        return

    if callback.from_user.id in ADMINS:
        await callback.answer(
            "Admin erişimi açık.",
            show_alert=True
        )
        return

    is_member = await check_membership(
        callback.bot,
        callback.from_user.id
    )

    if is_member:
        await callback.answer(
            "Üyelik doğrulandı!",
            show_alert=True
        )

        await callback.message.edit_text(
            "✅ @sancakmain kanal üyeliğin doğrulandı!\n\n"
            "ÖzVeGas'ı kullanmak için /start komutunu gönder."
        )

    else:
        await callback.answer(
            "❌ Henüz kanala katılmamışsın.",
            show_alert=True
        )
        


from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from settings import TECH_SUPPORT_USER_ID
from bot.keyboards import back_button, main_menu


router = Router()


class SupportStates(StatesGroup):
    AWAITING_DESCRIPTION = State()


@router.message(F.text == "🛠 Destek")
async def start_support_request(
    message: Message,
    state: FSMContext
):
    await state.clear()

    await message.answer(
        "🛠 **ÖzVeGas Destek Merkezi**\n\n"
        "📨 Yaşadığın sorunu ayrıntılı şekilde anlat.\n\n"
        "Metin, fotoğraf, video, belge veya sesli mesaj "
        "gönderebilirsin.\n\n"
        "Ekibimiz talebini inceleyip en kısa sürede "
        "seninle iletişime geçecektir.\n\n"
        "❌ İşlemi iptal etmek için Geri butonuna bas.",
        reply_markup=back_button()
    )

    await state.set_state(
        SupportStates.AWAITING_DESCRIPTION
    )


@router.message(
    SupportStates.AWAITING_DESCRIPTION,
    F.text == "🔙 Geri"
)
async def cancel_support_request(
    message: Message,
    state: FSMContext
):
    await state.clear()

    await message.answer(
        "❌ Destek talebi iptal edildi.",
        reply_markup=main_menu(message.from_user.id)
    )


@router.message(SupportStates.AWAITING_DESCRIPTION)
async def forward_to_support(
    message: Message,
    state: FSMContext,
    bot
):
    if not TECH_SUPPORT_USER_ID:
        await message.answer(
            "❌ Destek sistemi şu anda yapılandırılmamış. "
            "Lütfen daha sonra tekrar dene.",
            reply_markup=main_menu(message.from_user.id)
        )
        await state.clear()
        return

    username = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else "Kullanıcı adı bulunmuyor"
    )

    user_info = (
        "🛠 **YENİ DESTEK TALEBİ**\n\n"
        f"👤 Kullanıcı: {message.from_user.full_name}\n"
        f"🔗 Kullanıcı adı: {username}\n"
        f"🆔 Telegram ID: `{message.from_user.id}`\n"
        f"💬 Sohbet ID: `{message.chat.id}`"
    )

    try:
        # Önce destek ekibine kullanıcı bilgilerini gönder.
        await bot.send_message(
            chat_id=TECH_SUPPORT_USER_ID,
            text=user_info,
            parse_mode="Markdown"
        )

        # Kullanıcının gönderdiği mesajı tüm medya
        # türleriyle birlikte destek hesabına kopyala.
        await bot.copy_message(
            chat_id=TECH_SUPPORT_USER_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id
        )

    except Exception:
        await message.answer(
            "❌ Destek talebin gönderilemedi.\n"
            "Lütfen daha sonra tekrar dene.",
            reply_markup=back_button()
        )
        return

    await state.clear()

    await message.answer(
        "✅ Destek talebin başarıyla gönderildi!\n\n"
        "Ekibimiz başvurunu inceleyecek ve seninle "
        "en kısa sürede iletişime geçecektir.",
        reply_markup=main_menu(message.from_user.id)
    )

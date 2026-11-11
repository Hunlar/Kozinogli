
import math
from datetime import datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import CommandObject

from sqlalchemy import select

from db.database import AsyncSessionLocal
from db.models import User, Debt, BankAccount


router = Router()

BANK_NAME = "OzVeGas Kasa"
BANK_OWNER_TG_ID = 8658946296
BANKRUPTCY_LIMIT = 4000


class DebtStates(StatesGroup):
    waiting_for_amount = State()


def reset_bankruptcy_if_recovered(user: User):
    if (user.balance or 0) >= BANKRUPTCY_LIMIT:
        user.is_bankrupt = False
        user.bankruptcy_announced = False
        user.bankruptcy_chat_id = None


def update_bankruptcy_status(user: User):
    if (user.balance or 0) < BANKRUPTCY_LIMIT:
        user.is_bankrupt = True
    else:
        reset_bankruptcy_if_recovered(user)


async def get_bank_owner(session):
    result = await session.execute(
        select(User)
        .where(User.tg_id == BANK_OWNER_TG_ID)
        .with_for_update()
    )

    owner = result.scalar_one_or_none()

    if owner is None:
        owner = User(tg_id=BANK_OWNER_TG_ID)
        session.add(owner)
        await session.flush()

    return owner


async def give_loan(message: Message, amount: float):

    if not math.isfinite(amount) or amount <= 0:
        await message.answer(
            "❌ Geçerli ve sıfırdan büyük bir miktar gir."
        )
        return

    if message.from_user.id == BANK_OWNER_TG_ID:
        await message.answer(
            "🏦 Kendi kasandan borç alamazsın."
        )
        return

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(User)
            .where(User.tg_id == message.from_user.id)
            .with_for_update()
        )

        user = result.scalar_one_or_none()

        if user is None:
            await message.answer(
                "Önce /start komutunu kullanmalısın."
            )
            return

        balance = user.balance or 0

        if balance < BANKRUPTCY_LIMIT:
            required = BANKRUPTCY_LIMIT - balance

            if amount < required:
                await message.answer(
                    "❌ İflastan çıkmak için en az "
                    f"{required:,.2f} Sanal Kredi almalısın."
                )
                return

        owner = await get_bank_owner(session)

        bank_result = await session.execute(
            select(BankAccount)
            .where(BankAccount.name == BANK_NAME)
            .with_for_update()
        )

        bank = bank_result.scalar_one_or_none()

        if bank is None:
            bank = BankAccount(
                name=BANK_NAME,
                balance=0,
                is_unlimited=True
            )
            session.add(bank)
            await session.flush()

        if not bank.is_unlimited:
            await message.answer(
                "❌ Kasa şu anda kredi veremiyor."
            )
            return

        user.balance = balance + amount

        reset_bankruptcy_if_recovered(user)

        debt = Debt(
            lender_id=owner.id,
            borrower_id=user.id,
            amount=amount,
            is_paid=False
        )

        session.add(debt)

        await session.commit()
        await session.refresh(debt)

        new_balance = user.balance
        debt_id = debt.id

    await message.answer(
        "🏦 **ÖzVeGas Kasasından kredi aldın!**\n\n"
        f"🪙 Verilen kredi: {amount:,.2f} Sanal Kredi\n"
        f"📄 Borç numarası: #{debt_id}\n"
        f"💰 Yeni bakiyen: {new_balance:,.2f} Sanal Kredi\n\n"
        "Borçlarını görmek için /borclarim komutunu kullan.",
        parse_mode="Markdown"
    )


# --------------------------------------------------
# DOĞRUDAN KREDİ TRANSFERİ
# --------------------------------------------------

@router.message(Command("borcver"))
async def transfer_credit(
    message: Message,
    command: CommandObject
):

    if not message.reply_to_message:
        await message.answer(
            "❌ Kredi göndermek istediğin kullanıcının "
            "mesajına yanıt vererek komutu kullan.\n\n"
            "Örnek: /borcver 5000"
        )
        return

    if not command.args:
        await message.answer(
            "❌ Göndermek istediğin miktarı belirt.\n"
            "Örnek: /borcver 5000"
        )
        return

    try:
        amount = float(
            command.args.replace(",", ".").strip()
        )

        if not math.isfinite(amount) or amount <= 0:
            raise ValueError

    except ValueError:
        await message.answer(
            "❌ Geçerli ve pozitif bir miktar gir."
        )
        return

    sender_id = message.from_user.id
    replied_user = message.reply_to_message.from_user

    if replied_user is None:
        await message.answer(
            "❌ Hedef kullanıcı belirlenemedi."
        )
        return

    receiver_id = replied_user.id

    if sender_id == receiver_id:
        await message.answer(
            "❌ Kendine kredi gönderemezsin."
        )
        return

    if sender_id == BANK_OWNER_TG_ID:
        await message.answer(
            "🏦 Kasa hesabından bu yöntemle kredi gönderemezsin."
        )
        return

    if receiver_id == BANK_OWNER_TG_ID:
        await message.answer(
            "❌ Kasaya bu yöntemle kredi gönderemezsin."
        )
        return

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(User)
            .where(
                User.tg_id.in_([sender_id, receiver_id])
            )
            .order_by(User.id)
            .with_for_update()
        )

        users = {
            user.tg_id: user
            for user in result.scalars().all()
        }

        sender = users.get(sender_id)
        receiver = users.get(receiver_id)

        if sender is None:
            await message.answer(
                "❌ Önce /start komutunu kullanmalısın."
            )
            return

        if receiver is None:
            await message.answer(
                "❌ Alıcının ÖzVeGas hesabı bulunamadı."
            )
            return

        if sender.is_blocked:
            await message.answer(
                "🚫 Hesabın engelli olduğu için transfer yapamazsın."
            )
            return

        if receiver.is_blocked:
            await message.answer(
                "❌ Bu kullanıcıya kredi gönderilemiyor."
            )
            return

        sender_balance = sender.balance or 0

        if sender_balance < amount:
            await message.answer(
                "❌ Yetersiz bakiye.\n\n"
                f"💰 Bakiyen: {sender_balance:,.2f}\n"
                f"🪙 Göndermek istediğin: {amount:,.2f}"
            )
            return

        sender.balance = sender_balance - amount
        receiver.balance = (receiver.balance or 0) + amount

        update_bankruptcy_status(sender)
        reset_bankruptcy_if_recovered(receiver)

        await session.commit()

        new_sender_balance = sender.balance
        new_receiver_balance = receiver.balance

    await message.answer(
        "✅ **Kredi transferi başarılı!**\n\n"
        f"👤 Alıcı: {replied_user.full_name}\n"
        f"🪙 Gönderilen: {amount:,.2f} Sanal Kredi\n"
        f"💰 Yeni bakiyen: {new_sender_balance:,.2f} Sanal Kredi",
        parse_mode="Markdown"
    )

    try:
        await message.bot.send_message(
            receiver_id,
            "🎁 **Kredi aldın!**\n\n"
            f"👤 Gönderen: {message.from_user.full_name}\n"
            f"🪙 Gelen kredi: +{amount:,.2f} Sanal Kredi\n"
            f"💰 Yeni bakiyen: {new_receiver_balance:,.2f} Sanal Kredi",
            parse_mode="Markdown"
        )
    except Exception:
        pass


# --------------------------------------------------
# KASADAN BORÇ ALMA
# --------------------------------------------------

@router.message(Command("borc"))
async def borrow_command(
    message: Message,
    state: FSMContext,
    command: CommandObject
):

    if command.args:
        try:
            amount = float(
                command.args.replace(",", ".").strip()
            )
        except ValueError:
            await message.answer(
                "❌ Kullanım: /borc 10000"
            )
            return

        await give_loan(message, amount)
        return

    await state.set_state(
        DebtStates.waiting_for_amount
    )

    await message.answer(
        "🏦 ÖzVeGas Kasasından ne kadar "
        "Sanal Kredi almak istiyorsun?\n\n"
        "Örnek: 10000\n\n"
        "İptal etmek için /iptal yaz."
    )


@router.message(Command("iptal"), DebtStates.waiting_for_amount)
async def cancel_loan(
    message: Message,
    state: FSMContext
):
    await state.clear()
    await message.answer(
        "❌ Borç alma işlemi iptal edildi."
    )


@router.message(DebtStates.waiting_for_amount)
async def receive_loan_amount(
    message: Message,
    state: FSMContext
):

    try:
        amount = float(
            message.text.replace(",", ".").strip()
        )
    except (ValueError, AttributeError):
        await message.answer(
            "❌ Sadece geçerli bir sayı gir."
        )
        return

    await state.clear()
    await give_loan(message, amount)


# --------------------------------------------------
# BORÇLARI LİSTELEME
# --------------------------------------------------

@router.message(Command("borclarim"))
async def list_debts(message: Message):

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(User).where(
                User.tg_id == message.from_user.id
            )
        )

        user = result.scalar_one_or_none()

        if user is None:
            await message.answer(
                "Önce /start komutunu kullanmalısın."
            )
            return

        result = await session.execute(
            select(Debt)
            .where(
                Debt.borrower_id == user.id,
                Debt.is_paid.is_(False)
            )
            .order_by(Debt.id)
        )

        debts = result.scalars().all()

    if not debts:
        await message.answer(
            "✅ Ödenmemiş borcun bulunmuyor."
        )
        return

    lines = ["📄 **Ödenmemiş Borçların**\n"]

    for debt in debts:
        lines.append(
            f"📌 Borç No: #{debt.id}\n"
            f"🪙 Miktar: {debt.amount:,.2f} Sanal Kredi\n"
            f"💳 Ödeme: `/borcodeme {debt.id}`"
        )

    await message.answer(
        "\n\n".join(lines),
        parse_mode="Markdown"
    )


# --------------------------------------------------
# BORÇ ÖDEME
# --------------------------------------------------

@router.message(Command("borcodeme"))
async def repay_debt(
    message: Message,
    command: CommandObject
):

    if (
        not command.args
        or not command.args.strip().isdigit()
    ):
        await message.answer(
            "❌ Kullanım: /borcodeme BORÇ_NO\n\n"
            "Borçlarını görmek için /borclarim yaz."
        )
        return

    debt_id = int(command.args.strip())

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(User)
            .where(User.tg_id == message.from_user.id)
            .with_for_update()
        )

        user = result.scalar_one_or_none()

        if user is None:
            await message.answer(
                "Kullanıcı kaydın bulunamadı."
            )
            return

        result = await session.execute(
            select(Debt)
            .where(
                Debt.id == debt_id,
                Debt.borrower_id == user.id
            )
            .with_for_update()
        )

        debt = result.scalar_one_or_none()

        if debt is None or debt.is_paid:
            await message.answer(
                "❌ Bu numaraya ait ödenmemiş "
                "bir borç bulunamadı."
            )
            return

        balance = user.balance or 0

        if balance < debt.amount:
            await message.answer(
                "❌ Bakiyen bu borcu ödemek için yetersiz.\n\n"
                f"🪙 Borç: {debt.amount:,.2f} Sanal Kredi\n"
                f"💰 Bakiyen: {balance:,.2f} Sanal Kredi"
            )
            return

        lender = None

        if debt.lender_id is not None:
            lender_result = await session.execute(
                select(User)
                .where(User.id == debt.lender_id)
                .with_for_update()
            )
            lender = lender_result.scalar_one_or_none()

        user.balance = balance - debt.amount

        if lender is not None:
            lender.balance = (
                (lender.balance or 0) + debt.amount
            )

        debt.is_paid = True
        debt.paid_at = datetime.now()

        reset_bankruptcy_if_recovered(user)

        await session.commit()

        new_balance = user.balance
        paid_amount = debt.amount

    await message.answer(
        "✅ Borcun tamamen ödendi!\n\n"
        f"🪙 Ödenen: {paid_amount:,.2f} Sanal Kredi\n"
        f"💰 Kalan bakiye: {new_balance:,.2f} Sanal Kredi"
    )
    

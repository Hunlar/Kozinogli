
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
BANKRUPTCY_LIMIT = 4000


class DebtStates(StatesGroup):
    waiting_for_amount = State()


async def give_loan(message: Message, amount: float):
    if not math.isfinite(amount) or amount <= 0:
        await message.answer("❌ Geçerli ve sıfırdan büyük bir miktar gir.")
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User)
            .where(User.tg_id == message.from_user.id)
            .with_for_update()
        )
        user = result.scalar_one_or_none()

        if user is None:
            await message.answer("Önce /start komutunu kullanmalısın.")
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

        bank_result = await session.execute(
            select(BankAccount).where(
                BankAccount.name == BANK_NAME
            )
        )
        bank = bank_result.scalar_one_or_none()

        if bank is None:
            bank = BankAccount(
                name=BANK_NAME,
                balance=0,
                is_unlimited=True
            )
            session.add(bank)

        if not bank.is_unlimited:
            await message.answer("❌ Kasa şu anda kredi veremiyor.")
            return

        user.balance = balance + amount

        debt = Debt(
            lender_id=None,
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
        "🏦 **ÖzVeGas Kasası**\n\n"
        f"🪙 Verilen kredi: {amount:,.2f}\n"
        f"📄 Borç numarası: #{debt_id}\n"
        f"💰 Yeni bakiyen: {new_balance:,.2f}\n\n"
        "Borçlarını görmek için /borclarim komutunu kullan.",
        parse_mode="Markdown"
    )


@router.message(Command("borc"))
async def borrow_command(
    message: Message,
    state: FSMContext,
    command: CommandObject
):
    if command.args:
        try:
            amount = float(command.args.replace(",", "."))
        except ValueError:
            await message.answer(
                "Kullanım: /borc 10000"
            )
            return

        await give_loan(message, amount)
        return

    await state.set_state(DebtStates.waiting_for_amount)
    await message.answer(
        "🏦 ÖzVeGas Kasasından ne kadar Sanal Kredi almak istiyorsun?\n\n"
        "Örnek: 10000"
    )


@router.message(DebtStates.waiting_for_amount)
async def receive_loan_amount(
    message: Message,
    state: FSMContext
):
    try:
        amount = float(message.text.replace(",", "."))
    except (ValueError, AttributeError):
        await message.answer("❌ Sadece geçerli bir sayı gir.")
        return

    await state.clear()
    await give_loan(message, amount)


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
            await message.answer("Önce /start komutunu kullanmalısın.")
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
        await message.answer("✅ Ödenmemiş borcun bulunmuyor.")
        return

    lines = ["📄 **Ödenmemiş Borçların**\n"]

    for debt in debts:
        lines.append(
            f"Borç No: #{debt.id} — "
            f"{debt.amount:,.2f} Sanal Kredi\n"
            f"Ödeme: `/borcodeme {debt.id}`"
        )

    await message.answer(
        "\n\n".join(lines),
        parse_mode="Markdown"
    )


@router.message(Command("borcodeme"))
async def repay_debt(
    message: Message,
    command: CommandObject
):
    if not command.args or not command.args.strip().isdigit():
        await message.answer(
            "Kullanım: /borcodeme BORÇ_NO\n"
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
            await message.answer("Kullanıcı kaydın bulunamadı.")
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
                "❌ Bu numaraya ait ödenmemiş bir borç bulunamadı."
            )
            return

        if (user.balance or 0) < debt.amount:
            await message.answer(
                "❌ Bakiyen bu borcu ödemek için yetersiz.\n"
                f"Borç: {debt.amount:,.2f}\n"
                f"Bakiyen: {(user.balance or 0):,.2f}"
            )
            return

        user.balance -= debt.amount
        debt.is_paid = True
        debt.paid_at = datetime.now()

        await session.commit()

        new_balance = user.balance
        paid_amount = debt.amount

    await message.answer(
        "✅ Borcun tamamen ödendi!\n\n"
        f"🪙 Ödenen: {paid_amount:,.2f} Sanal Kredi\n"
        f"💰 Kalan bakiye: {new_balance:,.2f}"
    )

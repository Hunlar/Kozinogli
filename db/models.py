
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Float,
    DateTime,
    Boolean,
    ForeignKey,
    Date
)
from sqlalchemy.orm import declarative_base
from datetime import datetime


Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    tg_id = Column(BigInteger, unique=True, nullable=False)
    is_blocked = Column(Boolean, default=False)
    login = Column(String(50), unique=True)
    password = Column(String(100))

    balance = Column(Float, default=0.0)
    current_bet = Column(Float, default=0.0)

    daily_credit_date = Column(Date, nullable=True)

    # İflas sistemi
    is_bankrupt = Column(Boolean, default=False)
    bankruptcy_announced = Column(Boolean, default=False)
    bankruptcy_chat_id = Column(BigInteger, nullable=True)

    # Eski alanlar
    subscription_end = Column(DateTime, nullable=True)
    last_roulette_spin = Column(DateTime, nullable=True)


class Coupon(Base):
    __tablename__ = "coupons"

    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True)
    uses_left = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    days_added = Column(Integer)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)


class GameSettings(Base):
    __tablename__ = "game_settings"

    id = Column(Integer, primary_key=True)
    game_name = Column(String(50), unique=True)
    multiplier = Column(Float, default=1.0)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Float)
    type = Column(String(20))
    created_at = Column(DateTime, default=datetime.now)


class BankAccount(Base):
    __tablename__ = "bank_accounts"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    balance = Column(Float, default=0.0)
    is_unlimited = Column(Boolean, default=True)


class Debt(Base):
    __tablename__ = "debts"

    id = Column(Integer, primary_key=True)

    lender_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True
    )

    borrower_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    amount = Column(Float, nullable=False)
    is_paid = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.now)
    paid_at = Column(DateTime, nullable=True)

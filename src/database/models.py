from sqlalchemy import (
    BigInteger,
    Column,
    String,
    DateTime,
    Boolean,
    func,
    ForeignKey,
    Float,
    Integer,
    JSON,
    Enum as PgEnum,
)
from sqlalchemy.orm import relationship
import enum
from src.database.base import Base


class TransactionType(enum.Enum):
    """Tipos de transação financeira."""

    SALE = "sale"
    FEE_PLATFORM = "fee_plat"
    FEE_SERVICE = "fee_serv"
    WITHDRAWAL = "withdrawal"
    WITHDRAWAL_FEE = "w_fee"


class WithdrawalStatus(enum.Enum):
    """Status de solicitações de saque."""

    PENDING = "pending"
    PROCESSING = "processing"
    PAID = "paid"
    FAILED = "failed"
    REJECTED = "rejected"


class User(Base):
    """Usuário proprietário de bots."""

    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, index=True)
    full_name = Column(String, nullable=True)
    username = Column(String, nullable=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    bots = relationship("Bot", back_populates="owner")


class Bot(Base):
    """Bot gerenciado por um usuário."""

    __tablename__ = "bots"

    id = Column(BigInteger, primary_key=True, index=True)
    owner_id = Column(BigInteger, ForeignKey("users.id"))
    token = Column(String, unique=True, nullable=False)
    name = Column(String)
    username = Column(String)
    group_id = Column(BigInteger, nullable=True)
    group_name = Column(String, nullable=True)
    description = Column(String, default="🤖 Bem-vindo ao Bot VIP.")
    welcome_message = Column(String, default="Olá! Este é o canal oficial de vendas.")
    welcome_media_id = Column(String, nullable=True)
    welcome_media_type = Column(String, nullable=True)
    followups = Column(JSON, default=list)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    owner = relationship("User", back_populates="bots")
    plans = relationship("Plan", back_populates="bot", cascade="all, delete-orphan")
    leads = relationship("Lead", back_populates="bot", cascade="all, delete-orphan")


class Plan(Base):
    """Plano de assinatura vinculado a um bot."""

    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_id = Column(BigInteger, ForeignKey("bots.id"))
    name = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    days = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    bot = relationship("Bot", back_populates="plans")


class Subscriber(Base):
    """Cliente (ou Lead) que interagiu com o bot."""

    __tablename__ = "subscribers"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String)
    username = Column(String, nullable=True)
    document = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Subscription(Base):
    """Vínculo entre assinante, bot e plano."""

    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_id = Column(BigInteger, ForeignKey("bots.id"))
    plan_id = Column(Integer, ForeignKey("plans.id"))
    subscriber_id = Column(BigInteger, ForeignKey("subscribers.id"))
    start_date = Column(DateTime(timezone=True), server_default=func.now())
    end_date = Column(DateTime(timezone=True), nullable=True)  # Null = vitalício
    is_active = Column(Boolean, default=True)


class Transaction(Base):
    """Registro de transação financeira (livro caixa)."""

    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"))
    bot_id = Column(BigInteger, ForeignKey("bots.id"), nullable=True)
    external_id = Column(String, nullable=True)
    type = Column(PgEnum(TransactionType), nullable=False)
    description = Column(String)
    amount = Column(Float, nullable=False)  # Positivo = entrada, negativo = saída
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    followup_sent = Column(Boolean, default=False)


class Withdrawal(Base):
    """Solicitação de saque."""

    __tablename__ = "withdrawals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"))
    amount_requested = Column(Float, nullable=False)
    fee_total = Column(Float, nullable=False)
    amount_final = Column(Float, nullable=False)
    pix_key = Column(String, nullable=False)
    pix_type = Column(String, default="CPF")
    status = Column(PgEnum(WithdrawalStatus), default=WithdrawalStatus.PENDING)
    ggpix_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)


class Lead(Base):
    """
    Rastreia visitantes e leads em potencial.
    Usado para enviar mensagens de recuperação (remarketing).
    """

    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("subscribers.id"))
    bot_id = Column(BigInteger, ForeignKey("bots.id"))

    first_name = Column(String, nullable=True)
    username = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Controle de Follow-up
    last_interaction = Column(DateTime(timezone=True), server_default=func.now())
    followup_sent = Column(Boolean, default=False)
    is_converted = Column(
        Boolean, default=False
    )  # True se já comprou (não enviar mais msg)

    bot = relationship("Bot", back_populates="leads")

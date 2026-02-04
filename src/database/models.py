from sqlalchemy import BigInteger, Column, String, DateTime, Boolean, func, ForeignKey, Float, Integer, JSON, Enum as PgEnum
from sqlalchemy.orm import relationship
import enum
from src.database.base import Base

# Enums
class TransactionType(enum.Enum):
    SALE = "sale"                # Venda bruta
    FEE_PLATFORM = "fee_plat"    # Taxa GGPIX
    FEE_SERVICE = "fee_serv"     # Sua taxa (Lucro)
    WITHDRAWAL = "withdrawal"    # Saque
    WITHDRAWAL_FEE = "w_fee"     # Taxa do saque

class WithdrawalStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PAID = "paid"
    FAILED = "failed"
    REJECTED = "rejected"

class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True, index=True)
    full_name = Column(String, nullable=True)
    username = Column(String, nullable=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    bots = relationship("Bot", back_populates="owner")
class Bot(Base):
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

class Plan(Base):
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
    """Cliente final que comprou o plano"""
    __tablename__ = "subscribers"
    id = Column(BigInteger, primary_key=True, index=True) # ID Telegram ou CPF
    name = Column(String)
    document = Column(String, nullable=True) # CPF
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Subscription(Base):
    """Vínculo de assinatura"""
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_id = Column(BigInteger, ForeignKey("bots.id"))
    plan_id = Column(Integer, ForeignKey("plans.id"))
    subscriber_id = Column(BigInteger, ForeignKey("subscribers.id"))
    
    start_date = Column(DateTime(timezone=True), server_default=func.now())
    end_date = Column(DateTime(timezone=True), nullable=True) # Null = Vitalício
    is_active = Column(Boolean, default=True)

class Transaction(Base):
    """Livro Caixa (Extrato Financeiro)"""
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    user_id = Column(BigInteger, ForeignKey("users.id")) # Dono do Bot (quem recebe/paga)
    bot_id = Column(BigInteger, ForeignKey("bots.id"), nullable=True) # Origem
    
    external_id = Column(String, nullable=True) # ID na GGPIX
    type = Column(PgEnum(TransactionType), nullable=False)
    description = Column(String)
    amount = Column(Float, nullable=False) # Positivo (Entrada) / Negativo (Saída)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Withdrawal(Base):
    """Solicitações de Saque"""
    __tablename__ = "withdrawals"
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    user_id = Column(BigInteger, ForeignKey("users.id"))
    
    amount_requested = Column(Float, nullable=False) # Quanto ele quer receber
    fee_total = Column(Float, nullable=False)        # Total de taxas descontadas
    amount_final = Column(Float, nullable=False)     # Quanto sai do saldo (amount + fee)
    
    pix_key = Column(String, nullable=False)
    pix_type = Column(String, default="CPF")
    
    status = Column(PgEnum(WithdrawalStatus), default=WithdrawalStatus.PENDING)
    ggpix_id = Column(String, nullable=True) # ID da transação na GGPIX
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)

class Lead(Base):
    """
    Registra que um usuário (Subscriber) iniciou um Bot específico.
    Usado para o sistema de Remarketing saber pra quem mandar mensagem.
    """
    __tablename__ = "leads"
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    user_id = Column(BigInteger, ForeignKey("subscribers.id")) # O cliente
    bot_id = Column(BigInteger, ForeignKey("bots.id"))         # O bot que ele entrou
    
    created_at = Column(DateTime(timezone=True), server_default=func.now()) # Data do /start
    last_remarketing_at = Column(DateTime(timezone=True), nullable=True)
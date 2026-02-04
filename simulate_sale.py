import asyncio
import uuid
import httpx
from sqlalchemy.future import select
from src.database.base import AsyncSessionLocal
from src.database.models import User, Bot, Plan, Transaction, TransactionType, Subscriber

# CONFIGURAÇÕES DO TESTE
TEST_USER_ID = 1790032262 
SERVER_URL = "http://localhost:8080" 

async def prepare_data():
    """
    Prepara o terreno: Cria Bot, Plano e Transação Pendente no banco.
    """
    print("🛠 Preparando dados no banco...")
    async with AsyncSessionLocal() as session:
        # 1. Busca ou Cria Bot
        result = await session.execute(select(Bot).filter(Bot.owner_id == TEST_USER_ID))
        bot = result.scalars().first()
        if not bot:
            print("❌ Erro: Crie um bot primeiro pelo Telegram!")
            return None, None
        
        # 2. Busca ou Cria Plano de R$ 100,00
        result = await session.execute(select(Plan).filter(Plan.bot_id == bot.id, Plan.price == 100.0))
        plan = result.scalars().first()
        if not plan:
            print("➕ Criando plano de R$ 100,00...")
            plan = Plan(bot_id=bot.id, name="Plano Teste 100", price=100.0, days=30, is_active=True)
            session.add(plan)
            await session.commit()
            await session.refresh(plan)
        
        # 3. Cria Transação Pendente (Simula o clique em 'Comprar')
        external_id = f"{uuid.uuid4()}|{plan.id}|{TEST_USER_ID}"
        
        print(f"💳 Criando transação pendente (R$ 0,00) para o plano '{plan.name}'...")
        transaction = Transaction(
            user_id=TEST_USER_ID,
            bot_id=bot.id,
            external_id=external_id,
            type=TransactionType.SALE,
            description=f"(Pendente) {plan.name} - Simulação",
            amount=0.0 
        )
        session.add(transaction)
        await session.commit()
        
        return external_id, plan.price

async def simulate_webhook(external_id, price):
    """
    Finge ser a GGPIX enviando o Webhook de confirmação.
    """
    if not external_id:
        return

    # Cálculo reverso da GGPIX (Desconta 3% na fonte)
    amount_cents = int(price * 100)
    fee_platform = int(amount_cents * 0.03) # 3%
    net_amount = amount_cents - fee_platform

    payload = {
        "type": "PIX_IN",
        "status": "COMPLETE",
        "externalId": external_id,
        "amount": amount_cents,    
        "netAmount": net_amount,   
        "pixKey": "teste",
        "paymentDate": "2023-10-27T10:00:00Z"
    }

    print(f"\n🚀 Disparando Webhook Fake para {SERVER_URL}/payment-webhook...")
    print(f"💰 Dados: Venda R$ {price:.2f} | Líquido GGPIX: R$ {net_amount/100:.2f}")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{SERVER_URL}/payment-webhook",
                json=payload,
                headers={"X-Webhook-Signature": ""}
            )
            print(f"📡 Resposta do Servidor: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ Erro ao conectar no servidor: {e}")

async def check_balance():
    """
    Confere o saldo final no banco.
    """
    print("\n🧐 Conferindo saldo final...")
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Transaction)
            .filter(Transaction.user_id == TEST_USER_ID)
            .order_by(Transaction.id.desc())
            .limit(2)
        )
        transactions = result.scalars().all()
        
        total = 0
        print("-" * 30)
        for t in transactions:
            print(f"📝 ID {t.id} | {t.description} | R$ {t.amount:.2f}")
            total += t.amount
        print("-" * 30)
        
        print(f"💵 Impacto no Saldo: R$ {total:.2f}")

# --- A CORREÇÃO ESTÁ AQUI ---
async def main():
    # Roda tudo dentro do MESMO loop
    ext_id, price = await prepare_data()
    
    if ext_id:
        await simulate_webhook(ext_id, price)
        # Espera um pouquinho pro servidor processar o banco
        await asyncio.sleep(1) 
        await check_balance()

if __name__ == "__main__":
    asyncio.run(main())
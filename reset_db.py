import asyncio
from src.database.base import engine, Base
from src.database.models import User, Bot, Plan, Subscriber, Subscription, Transaction, Withdrawal, Lead

async def reset_database():
    print("🔥 Apagando banco de dados...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Banco recriado com sucesso! Todas as tabelas estão prontas.")

if __name__ == "__main__":
    asyncio.run(reset_database())
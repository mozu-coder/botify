import logging
from datetime import datetime, timedelta
from sqlalchemy.future import select
from telegram import Bot as TgBot
from telegram.error import Forbidden, BadRequest

from src.database.base import AsyncSessionLocal
from src.database.models import Transaction, Bot, TransactionType

logger = logging.getLogger(__name__)
DELAY_MINUTES = 30


async def check_abandoned_carts():
    """
    Verifica carrinhos abandonados (vendas pendentes) e envia mensagens de recuperação.
    Executado periodicamente pelo scheduler.
    """
    logger.info("⏰ Scheduler: Verificando carrinhos abandonados...")

    try:
        async with AsyncSessionLocal() as session:
            cutoff_time = datetime.now() - timedelta(minutes=DELAY_MINUTES)

            query = select(Transaction).where(
                Transaction.type == TransactionType.SALE,
                Transaction.amount == 0,
                Transaction.created_at < cutoff_time,
                Transaction.followup_sent == False,
            )

            result = await session.execute(query)
            transactions = result.scalars().all()

            if not transactions:
                return

            logger.info(f"🔎 Encontradas {len(transactions)} vendas para recuperar.")

            for tx in transactions:
                bot_res = await session.execute(select(Bot).filter(Bot.id == tx.bot_id))
                db_bot = bot_res.scalars().first()

                if not db_bot or not db_bot.is_active:
                    continue

                try:
                    bot = TgBot(db_bot.token)
                    msg = (
                        "Olá! 👋\n\n"
                        "Notamos que seu pedido de acesso ao <b>Grupo VIP</b> ainda não foi concluído.\n\n"
                        "⏳ As vagas podem acabar a qualquer momento.\n"
                        "Se tiver dúvidas sobre o pagamento, responda aqui!"
                    )
                    await bot.send_message(
                        chat_id=tx.user_id, text=msg, parse_mode="HTML"
                    )
                    logger.info(f"✅ Follow-up enviado para User {tx.user_id}")

                    tx.followup_sent = True

                except Forbidden:
                    logger.warning(f"🚫 User {tx.user_id} bloqueou o bot.")
                    tx.followup_sent = True
                except Exception as e:
                    logger.error(f"❌ Erro envio: {e}")

            await session.commit()

    except Exception as e:
        logger.error(f"❌ Erro fatal no Scheduler: {e}")

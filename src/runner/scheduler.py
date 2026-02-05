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


import logging
from datetime import datetime, timedelta
from sqlalchemy.future import select
from telegram import Bot as TgBot
from telegram.error import Forbidden, BadRequest

from src.database.base import AsyncSessionLocal
from src.database.models import Lead, Bot

logger = logging.getLogger(__name__)
DELAY_MINUTES = 30  # Tempo sem interação antes de mandar a mensagem


async def check_abandoned_carts():
    """
    Verifica LEADS (visitantes) que interagiram mas não converteram,
    e envia mensagem de recuperação.
    """
    logger.info("⏰ Scheduler: Verificando leads pendentes...")

    try:
        async with AsyncSessionLocal() as session:
            cutoff_time = datetime.now() - timedelta(minutes=DELAY_MINUTES)

            # Busca leads que:
            # 1. Mexeram no bot antes do tempo de corte
            # 2. Ainda não compraram (is_converted = False)
            # 3. Ainda não receberam follow-up
            query = select(Lead).where(
                Lead.last_interaction < cutoff_time,
                Lead.is_converted == False,
                Lead.followup_sent == False,
            )

            result = await session.execute(query)
            leads = result.scalars().all()

            if not leads:
                return

            logger.info(f"🔎 Encontrados {len(leads)} leads para recuperar.")

            for lead in leads:
                bot_res = await session.execute(
                    select(Bot).filter(Bot.id == lead.bot_id)
                )
                db_bot = bot_res.scalars().first()

                if not db_bot or not db_bot.is_active:
                    continue

                try:
                    bot = TgBot(db_bot.token)

                    first_name = lead.first_name or "Visitante"

                    msg = (
                        f"Olá, {first_name}! 👋\n\n"
                        "Vi que você acessou nosso bot mas ainda não finalizou sua entrada no <b>Grupo VIP</b>.\n\n"
                        "🤔 <b>Ficou com alguma dúvida?</b>\n"
                        "As vagas são limitadas e o conteúdo exclusivo já está rolando lá dentro.\n\n"
                        "👇 <b>Clique abaixo para ver os planos novamente:</b>\n"
                        "/start"
                    )

                    await bot.send_message(
                        chat_id=lead.user_id, text=msg, parse_mode="HTML"
                    )
                    logger.info(f"✅ Follow-up enviado para Lead {lead.user_id}")

                    lead.followup_sent = True

                except Forbidden:
                    logger.warning(f"🚫 User {lead.user_id} bloqueou o bot.")
                    lead.followup_sent = True
                except Exception as e:
                    logger.error(f"❌ Erro envio: {e}")

            await session.commit()

    except Exception as e:
        logger.error(f"❌ Erro fatal no Scheduler: {e}")

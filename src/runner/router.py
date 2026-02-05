from fastapi import APIRouter, Request, BackgroundTasks, Response
from telegram import Update, Bot as TgBot
from telegram.ext import Application
from sqlalchemy.future import select
from datetime import datetime, timedelta

from src.database.base import AsyncSessionLocal
from src.database.models import (
    Bot,
    Transaction,
    TransactionType,
    Subscription,
    Plan,
    Lead,
)
from src.runner.logic import RunnerLogic
from src.services.payment_service import PaymentService
from src.core.config import settings

runner_router = APIRouter()


async def process_update_task(token: str, update_data: dict):
    """Processa atualizações do Telegram em background para bots gerenciados."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Bot).filter(Bot.token == token))
        db_bot = result.scalars().first()

        if not db_bot or not db_bot.is_active:
            return

    try:
        app = Application.builder().token(token).build()
        await app.initialize()

        update = Update.de_json(update_data, app.bot)

        if (
            update.message
            and update.message.text
            and update.message.text.startswith("/start")
        ):
            await RunnerLogic.process_start(update, app.bot, db_bot)

        elif update.callback_query:
            data = update.callback_query.data
            if data.startswith("buy_plan_"):
                await RunnerLogic.process_purchase(update, app.bot, db_bot, data)

        await app.shutdown()

    except Exception as e:
        print(f"Erro Runner ({db_bot.name}): {e}")


@runner_router.post("/runner-webhook/{token}")
async def runner_webhook(
    token: str, request: Request, background_tasks: BackgroundTasks
):
    """Recebe webhooks dos bots gerenciados e processa em background."""
    update_data = await request.json()
    background_tasks.add_task(process_update_task, token, update_data)
    return {"status": "queued"}


@runner_router.post("/payment-webhook")
async def payment_webhook(request: Request):
    """
    Processa confirmações de pagamento da GGPIX.
    Atualiza transações, calcula taxas, libera acesso E MARCA LEAD COMO CONVERTIDO.
    """
    raw_body = await request.body()
    signature = request.headers.get("X-Webhook-Signature", "")

    if not PaymentService.validate_webhook_signature(raw_body, signature):
        return Response(status_code=401)

    data = await request.json()

    if data.get("type") == "PIX_IN" and data.get("status") == "COMPLETE":
        external_id = data.get("externalId")

        if not external_id:
            return {"status": "ignored_no_id"}

        amount_cents = data.get("amount", 0)
        net_amount_cents = data.get("netAmount", 0)

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Transaction).filter(Transaction.external_id == external_id)
            )
            transaction = result.scalars().first()

            if not transaction:
                return {"status": "ignored_not_found"}

            if transaction.amount > 0:
                return {"status": "already_processed"}

            amount_real = amount_cents / 100
            fee_profit = amount_real * settings.FEE_IN_PROFIT

            transaction.amount = (net_amount_cents / 100) - fee_profit
            transaction.description = transaction.description.replace("(Pendente) ", "")

            t_fee = Transaction(
                user_id=transaction.user_id,
                bot_id=transaction.bot_id,
                type=TransactionType.FEE_SERVICE,
                description="Taxa de Serviço da Plataforma (5%)",
                amount=-fee_profit,
            )
            session.add(t_fee)

            parts = str(external_id).split("|")

            if len(parts) >= 3:
                plan_id = int(parts[1])
                subscriber_id = int(parts[2])

                bot_res = await session.execute(
                    select(Bot).filter(Bot.id == transaction.bot_id)
                )
                bot = bot_res.scalars().first()

                plan_res = await session.execute(
                    select(Plan).filter(Plan.id == plan_id)
                )
                plan = plan_res.scalars().first()

                days = plan.days
                end_date = None
                if days < 36000:
                    end_date = datetime.now() + timedelta(days=days)

                sub = Subscription(
                    bot_id=bot.id,
                    plan_id=plan.id,
                    subscriber_id=subscriber_id,
                    end_date=end_date,
                )
                session.add(sub)

                # --- NOVO: MARCA O LEAD COMO CONVERTIDO ---
                # Isso impede que o Scheduler mande mensagem de "volte aqui"
                lead_res = await session.execute(
                    select(Lead).filter(
                        Lead.user_id == subscriber_id, Lead.bot_id == bot.id
                    )
                )
                lead = lead_res.scalars().first()
                if lead:
                    lead.is_converted = True
                # ------------------------------------------

                try:
                    tg_bot = TgBot(bot.token)
                    invite = await tg_bot.create_chat_invite_link(
                        chat_id=bot.group_id,
                        member_limit=1,
                        name=f"Venda {str(external_id)[:8]}",
                    )

                    await tg_bot.send_message(
                        chat_id=subscriber_id,
                        text=f"✅ <b>Pagamento Confirmado!</b>\n\nAqui está seu link de acesso exclusivo:\n{invite.invite_link}",
                        parse_mode="HTML",
                    )
                except Exception as e:
                    print(f"Erro entrega VIP: {e}")

            await session.commit()

    return {"received": True}

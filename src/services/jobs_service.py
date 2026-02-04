import asyncio
import random
from datetime import datetime, timedelta
from sqlalchemy.future import select
from telegram import Bot as TgBot
from telegram.error import TelegramError

from src.database.base import AsyncSessionLocal
from src.database.models import Subscription, Bot, Lead

class JobsService:
    """
    Serviço responsável pelas tarefas automáticas (Cronjobs).
    Apenas manutenção de assinaturas (Kick) e Remarketing.
    Pagamentos são manuais.
    """

    @staticmethod
    async def check_expired_subscriptions():
        """
        Busca assinaturas vencidas e ativas, remove do grupo e marca como inativa.
        """
        async with AsyncSessionLocal() as session:
            now = datetime.now()
            query = select(Subscription).join(Bot).filter(
                Subscription.end_date < now,
                Subscription.is_active == True
            )
            result = await session.execute(query)
            expired_subs = result.scalars().all()
            
            for sub in expired_subs:
                bot = await session.get(Bot, sub.bot_id)
                if not bot:
                    continue
                
                try:
                    tg_bot = TgBot(bot.token)
                    await tg_bot.ban_chat_member(chat_id=bot.group_id, user_id=sub.subscriber_id)
                    await tg_bot.unban_chat_member(chat_id=bot.group_id, user_id=sub.subscriber_id)
                    
                    await tg_bot.send_message(
                        chat_id=sub.subscriber_id,
                        text="<b>⛔ Seu plano venceu!</b>\n\nVocê foi removido do Grupo VIP. Renove agora para voltar.",
                        parse_mode="HTML"
                    )
                except TelegramError as e:
                    print(f"Erro ao remover user {sub.subscriber_id}: {e}")
                
                sub.is_active = False
            
            if expired_subs:
                await session.commit()

    @staticmethod
    async def send_remarketing():
        """
        Envia mensagens de recuperação para leads antigos sem assinatura ativa.
        """
        async with AsyncSessionLocal() as session:
            now = datetime.now()
            limit_time = now - timedelta(hours=2)
            
            query = select(Lead).where(
                Lead.created_at < limit_time,
                (Lead.last_remarketing_at == None) | (Lead.last_remarketing_at < (now - timedelta(hours=24)))
            ).limit(50)
            
            result = await session.execute(query)
            leads = result.scalars().all()
            
            for lead in leads:
                sub_query = select(Subscription).where(
                    Subscription.subscriber_id == lead.user_id,
                    Subscription.bot_id == lead.bot_id,
                    Subscription.is_active == True
                )
                sub_res = await session.execute(sub_query)
                if sub_res.scalars().first():
                    continue
                
                bot = await session.get(Bot, lead.bot_id)
                if not bot or not bot.followups:
                    continue
                
                message_text = random.choice(bot.followups)
                
                if not message_text.strip():
                    continue

                try:
                    tg_bot = TgBot(bot.token)
                    await tg_bot.send_message(
                        chat_id=lead.user_id,
                        text=message_text,
                        parse_mode="HTML"
                    )
                    
                    lead.last_remarketing_at = now
                    
                except TelegramError as e:
                    print(f"Erro Remarketing (Bot {bot.id} -> User {lead.user_id}): {e}")
            
            if leads:
                await session.commit()
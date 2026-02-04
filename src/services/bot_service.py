import httpx
from telegram import Bot as TgBot
from telegram.error import TelegramError
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError

from src.database.base import AsyncSessionLocal
from src.database.models import Bot
from src.core.config import settings


class BotService:

    @staticmethod
    async def _get_bot(token: str) -> TgBot:
        """Cria e inicializa uma instância do Bot."""
        bot = TgBot(token)
        await bot.initialize()
        return bot

    @staticmethod
    async def validate_token(token: str):
        """Valida se o token existe e retorna info do bot."""
        try:
            bot = await BotService._get_bot(token)
            return await bot.get_me()
        except TelegramError:
            return None

    @staticmethod
    async def reset_bot_connection(token: str):
        """Remove qualquer webhook existente para que updates fiquem na fila de Long Polling."""
        try:
            bot = await BotService._get_bot(token)
            await bot.delete_webhook(drop_pending_updates=False)
        except Exception as e:
            print(f"Aviso ao limpar webhook: {e}")

    @staticmethod
    async def detect_group_addition(token: str):
        """Busca updates recentes via Long Polling para detectar em qual grupo o bot foi adicionado."""
        try:
            bot = await BotService._get_bot(token)
            await bot.delete_webhook(drop_pending_updates=False)
            
            updates = await bot.get_updates(
                limit=20, 
                allowed_updates=["my_chat_member", "message", "chat_member"]
            )
            
            for update in reversed(updates):
                # Evento de mudança de status (mais confiável)
                if update.my_chat_member:
                    chat = update.my_chat_member.chat
                    status = update.my_chat_member.new_chat_member.status
                    
                    if chat.type in ["group", "supergroup"] and status in ["administrator", "member"]:
                        return {"id": chat.id, "title": chat.title}
                
                # Mensagem de serviço "Bot foi adicionado"
                if update.message and update.message.chat.type in ["group", "supergroup"]:
                    if update.message.new_chat_members:
                        for member in update.message.new_chat_members:
                            bot_info = await bot.get_me()
                            if member.id == bot_info.id:
                                return {"id": update.message.chat.id, "title": update.message.chat.title}
                    
                    if update.message.group_chat_created:
                        return {"id": update.message.chat.id, "title": update.message.chat.title}
                    
                    return {"id": update.message.chat.id, "title": update.message.chat.title}

            return None
            
        except Exception as e:
            print(f"Erro ao detectar grupo: {e}")
            return None

    @staticmethod
    async def create_bot(owner_id: int, token: str, bot_info, group_info):
        """Salva o bot no banco de dados."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Bot).filter(Bot.token == token))
            if result.scalars().first():
                raise ValueError("Este bot já está cadastrado!")

            new_bot = Bot(
                owner_id=owner_id,
                token=token,
                username=bot_info.username,
                name=bot_info.first_name,
                group_id=group_info['id'],
                group_name=group_info['title'],
                is_active=True
            )
            session.add(new_bot)
            
            try:
                await session.commit()
            except IntegrityError:
                raise ValueError("Erro ao salvar bot.")

    @staticmethod
    async def set_runner_webhook(token: str):
        """Configura o webhook do bot filho para produção."""
        bot = await BotService._get_bot(token)
        webhook_url = f"{settings.WEBHOOK_URL}/runner-webhook/{token}"
        
        await bot.set_webhook(
            url=webhook_url,
            allowed_updates=["message", "callback_query", "my_chat_member", "chat_member"],
            drop_pending_updates=False
        )
        print(f"✅ Webhook ativado: {webhook_url}")
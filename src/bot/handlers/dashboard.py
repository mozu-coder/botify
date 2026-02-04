from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from src.database.base import AsyncSessionLocal
from src.database.models import Bot, Plan
from src.utils.chat_manager import ChatManager
from src.utils.formatters import TextUtils
from src.bot.keyboards.dashboard import my_bots_list_keyboard, bot_management_keyboard, plans_list_keyboard

async def list_my_bots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    async with AsyncSessionLocal() as session:
        # Busca bots do usuário
        result = await session.execute(select(Bot).filter(Bot.owner_id == user_id))
        bots = result.scalars().all()
        
        text = TextUtils.pad_message(
            "<b>🤖 Seus Bots</b>\n\n"
            "Selecione um bot abaixo para gerenciar planos, mensagens e configurações."
        )
        
        if not bots:
            text = TextUtils.pad_message("<b>Você ainda não tem bots!</b>\nCrie um no menu principal.")
            
        await ChatManager.render_view(update, context, text, my_bots_list_keyboard(bots))

async def open_bot_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # Extrai o ID do bot do callback "manage_bot_123"
    bot_id = int(query.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Bot).filter(Bot.id == bot_id))
        bot = result.scalars().first()
        
        if not bot:
            await query.answer("Bot não encontrado!", show_alert=True)
            return

        text = TextUtils.pad_message(
            f"<b>⚙️ Gerenciando: {bot.name}</b>\n"
            f"@{bot.username}\n\n"
            f"Escolha o que deseja configurar:"
        )
        
        await ChatManager.render_view(update, context, text, bot_management_keyboard(bot))

# --- Handlers de Planos (Visualização) ---
async def view_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    bot_id = int(query.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        # Carrega planos do bot
        result = await session.execute(select(Plan).filter(Plan.bot_id == bot_id))
        plans = result.scalars().all()
        
        text = TextUtils.pad_message(
            "<b>💎 Planos de Assinatura</b>\n\n"
            "Aqui estão os planos ativos para este bot.\n"
            "Clique em um plano para editar ou crie um novo."
        )
        
        await ChatManager.render_view(update, context, text, plans_list_keyboard(plans, bot_id))

# Exporta os handlers para o main.py
dashboard_handlers = [
    CallbackQueryHandler(list_my_bots, pattern="^my_bots_list$"),
    CallbackQueryHandler(open_bot_manager, pattern="^manage_bot_"),
    CallbackQueryHandler(view_plans, pattern="^manage_plans_")
]
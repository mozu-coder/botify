from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler
from sqlalchemy.future import select

from src.database.base import AsyncSessionLocal
from src.database.models import Bot
from src.utils.chat_manager import ChatManager
from src.utils.formatters import TextUtils
from src.utils.ui import UI
from src.services.bot_service import BotService
from src.bot.keyboards.dashboard import bot_management_keyboard, my_bots_list_keyboard

# Estado para o wizard de troca de grupo
WAITING_NEW_GROUP = 1

# --- Lógica de Toggle (Ativar/Desativar) ---
async def toggle_bot_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    bot_id = int(query.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Bot).filter(Bot.id == bot_id))
        bot = result.scalars().first()
        
        if bot:
            bot.is_active = not bot.is_active
            await session.commit()
            
            status_msg = "ativado" if bot.is_active else "desativado"
            await UI.show_toast(update, f"Bot {status_msg} com sucesso!")
            
            # Recarrega o menu
            text = TextUtils.pad_message(
                f"<b>⚙️ Gerenciando: {bot.name}</b>\n"
                f"@{bot.username}\n\n"
                f"Escolha o que deseja configurar:"
            )
            await ChatManager.render_view(update, context, text, bot_management_keyboard(bot))

# --- Lógica de Exclusão ---
async def confirm_delete_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_id = int(update.callback_query.data.split("_")[2])
    
    text = TextUtils.pad_message(
        "<b>⚠️ ZONA DE PERIGO</b>\n\n"
        "Você tem certeza que deseja <b>EXCLUIR</b> este bot?\n"
        "• Todos os planos serão apagados.\n"
        "• O histórico de vendas será perdido.\n"
        "• Essa ação não pode ser desfeita."
    )
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Sim, Excluir Definitivamente", callback_data=f"real_del_bot_{bot_id}")],
        [InlineKeyboardButton("🔙 Cancelar", callback_data=f"manage_bot_{bot_id}")]
    ])
    
    await ChatManager.render_view(update, context, text, kb)

async def action_delete_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_id = int(update.callback_query.data.split("_")[3]) # real_del_bot_ID
    user_id = update.effective_user.id
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Bot).filter(Bot.id == bot_id))
        bot = result.scalars().first()
        
        if bot:
            await session.delete(bot)
            await session.commit()
            await UI.show_toast(update, "Bot excluído com sucesso!", alert=True)
            
        # Redireciona para a lista de bots
        # Recarregando a lista manualmente para evitar dependência circular
        result_list = await session.execute(select(Bot).filter(Bot.owner_id == user_id))
        bots = result_list.scalars().all()
        
        text = TextUtils.pad_message("<b>🤖 Seus Bots</b>\n\nSelecione um bot abaixo.")
        await ChatManager.render_view(update, context, text, my_bots_list_keyboard(bots))


# --- Lógica de Troca de Grupo (Wizard) ---
async def start_change_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_id = int(update.callback_query.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Bot).filter(Bot.id == bot_id))
        bot = result.scalars().first()
        
        if not bot:
            await UI.show_toast(update, "Bot não encontrado!", alert=True)
            return ConversationHandler.END

        # Salva no contexto para o próximo passo
        context.user_data['edit_bot_id'] = bot.id
        context.user_data['edit_bot_token'] = bot.token

        perms = "change_info+delete_messages+restrict_members+invite_users+pin_messages"
        add_group_url = f"https://t.me/{bot.username}?startgroup=setup&admin={perms}"

        text = TextUtils.pad_message(
            f"<b>🔄 Trocar Grupo Vinculado</b>\n\n"
            f"Atualmente vinculado a: <b>{bot.group_name}</b>\n\n"
            "1. Remova o bot do grupo antigo (opcional).\n"
            "2. Adicione o bot no <b>NOVO Grupo</b> usando o botão abaixo.\n"
            "3. Clique em 'Verificar Novo Grupo'."
        )
        
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add no Novo Grupo", url=add_group_url)],
            [InlineKeyboardButton("🔄 Verificar Novo Grupo", callback_data="check_new_group")],
            [InlineKeyboardButton("🔙 Cancelar", callback_data=f"manage_bot_{bot.id}")]
        ])
        
        await ChatManager.render_view(update, context, text, kb)
        return WAITING_NEW_GROUP

async def check_new_group_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    token = context.user_data.get('edit_bot_token')
    bot_id = context.user_data.get('edit_bot_id')
    
    await UI.show_toast(update, "🔍 Buscando novo grupo...")
    
    # Reutiliza o serviço de detecção
    group_info = await BotService.detect_group_addition(token)
    
    if not group_info:
        await UI.show_toast(update, "❌ Não detectei o bot em um novo grupo admin recentemente.", alert=True)
        return WAITING_NEW_GROUP
    
    # Atualiza no Banco
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Bot).filter(Bot.id == bot_id))
        bot = result.scalars().first()
        
        if bot:
            bot.group_id = group_info['id']
            bot.group_name = group_info['title']
            await session.commit()
            
            # Sucesso
            text = TextUtils.pad_message(
                f"<b>✅ Grupo Atualizado!</b>\n\n"
                f"O bot <b>{bot.name}</b> agora administra o grupo:\n"
                f"📢 <b>{bot.group_name}</b>"
            )
            await ChatManager.render_view(update, context, text, bot_management_keyboard(bot))
            
    return ConversationHandler.END

async def cancel_change_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Volta para o menu do bot
    bot_id = context.user_data.get('edit_bot_id')
    if not bot_id:
        # Fallback se perdeu o ID, volta pro menu principal
        query = update.callback_query
        query.data = "my_bots_list"
        from src.bot.handlers.dashboard import list_my_bots
        await list_my_bots(update, context)
        return ConversationHandler.END

    # Recupera o bot e mostra menu
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Bot).filter(Bot.id == bot_id))
        bot = result.scalars().first()
        text = TextUtils.pad_message(f"<b>⚙️ Gerenciando: {bot.name}</b>\nEscolha o que deseja configurar:")
        await ChatManager.render_view(update, context, text, bot_management_keyboard(bot))
    
    return ConversationHandler.END


# Wizard de Troca de Grupo
change_group_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_change_group, pattern="^change_group_")],
    states={
        WAITING_NEW_GROUP: [
            CallbackQueryHandler(check_new_group_step, pattern="^check_new_group$"),
            CallbackQueryHandler(cancel_change_group, pattern="^manage_bot_") 
        ]
    },
    fallbacks=[CallbackQueryHandler(cancel_change_group, pattern="^manage_bot_")]
)

# Handlers simples (Toggle e Delete)
bot_action_handlers = [
    CallbackQueryHandler(toggle_bot_status, pattern="^toggle_bot_"),
    CallbackQueryHandler(confirm_delete_bot, pattern="^delete_bot_"),
    CallbackQueryHandler(action_delete_bot, pattern="^real_del_bot_")
]
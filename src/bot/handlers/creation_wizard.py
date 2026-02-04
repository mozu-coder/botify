from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters

from src.utils.chat_manager import ChatManager
from src.utils.formatters import TextUtils
from src.utils.ui import UI
from src.services.bot_service import BotService
from src.bot.keyboards.menus import main_menu_keyboard

WAITING_TOKEN = 1
WAITING_GROUP_CONFIRMATION = 2


async def start_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia o wizard de criação de bot (Passo 1: solicita token)."""
    text = TextUtils.pad_message(
        "<b>🛠 Passo 1/2: Token do Bot</b>\n\n"
        "Envie o <b>Token de API</b> do seu bot criado no @BotFather."
    )
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancelar", callback_data="cancel_wizard")]])
    await ChatManager.render_view(update, context, text, keyboard)
    return WAITING_TOKEN


async def receive_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recebe e valida o token do bot (Passo 1 -> Passo 2)."""
    await ChatManager.clear_user_message(update, context)
    token = update.message.text.strip()
    
    bot_info = await BotService.validate_token(token)

    if not bot_info:
        error_text = TextUtils.pad_message("<b>❌ Token Inválido!</b> Tente novamente.")
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancelar", callback_data="cancel_wizard")]])
        await ChatManager.render_view(update, context, error_text, keyboard)
        return WAITING_TOKEN

    await BotService.reset_bot_connection(token)

    context.user_data['temp_bot_token'] = token
    context.user_data['temp_bot_info'] = bot_info

    perms = "change_info+delete_messages+restrict_members+invite_users+pin_messages"
    add_group_url = f"https://t.me/{bot_info.username}?startgroup=setup&admin={perms}"

    text = TextUtils.pad_message(
        f"<b>✅ Bot Identificado: {bot_info.first_name}</b>\n\n"
        "<b>📂 Passo 2/2: Vincular Grupo VIP</b>\n\n"
        "1. Clique no botão <b>'Adicionar no Grupo'</b> abaixo.\n"
        "2. Selecione seu grupo e confirme.\n"
        "3. Volte aqui e clique em <b>'Verificar Grupo'</b>."
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Adicionar no Grupo (Admin)", url=add_group_url)],
        [InlineKeyboardButton("🔄 Verificar Grupo", callback_data="check_group_connection")],
        [InlineKeyboardButton("🔙 Cancelar", callback_data="cancel_wizard")]
    ])
    
    await ChatManager.render_view(update, context, text, keyboard)
    return WAITING_GROUP_CONFIRMATION


async def check_group_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verifica se o bot foi adicionado a um grupo e finaliza o cadastro."""
    await update.callback_query.answer()

    token = context.user_data.get('temp_bot_token')
    bot_info = context.user_data.get('temp_bot_info')
    
    await UI.show_toast(update, "🔍 Procurando grupo...")
    
    group_info = await BotService.detect_group_addition(token)
    
    if not group_info:
        await UI.show_toast(update, "❌ Nenhum grupo encontrado!", alert=True)
        return WAITING_GROUP_CONFIRMATION
        
    try:
        user_id = update.effective_user.id
        await BotService.create_bot(user_id, token, bot_info, group_info)
        await BotService.set_runner_webhook(token)
        
        success_text = TextUtils.pad_message(
            f"<b>🎉 Configuração Concluída!</b>\n\n"
            f"🤖 <b>Bot:</b> {bot_info.first_name}\n"
            f"📢 <b>Grupo Vinculado:</b> {group_info['title']}\n\n"
            "Seu sistema de assinatura já está pronto para ser configurado."
        )
        
        await ChatManager.render_view(update, context, success_text, main_menu_keyboard())
        return ConversationHandler.END

    except ValueError as e:
        await UI.show_toast(update, f"Erro: {str(e)}", alert=True)
        return ConversationHandler.END


async def cancel_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela o wizard e retorna ao menu principal."""
    await update.callback_query.answer()
    
    text = TextUtils.pad_message("<b>❌ Operação Cancelada</b>")
    await ChatManager.render_view(update, context, text, main_menu_keyboard())
    return ConversationHandler.END


creation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_creation, pattern="^wizard_new_bot$")],
    states={
        WAITING_TOKEN: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_token),
            CallbackQueryHandler(cancel_wizard, pattern="^cancel_wizard$")
        ],
        WAITING_GROUP_CONFIRMATION: [
            CallbackQueryHandler(check_group_step, pattern="^check_group_connection$"),
            CallbackQueryHandler(cancel_wizard, pattern="^cancel_wizard$")
        ]
    },
    fallbacks=[CallbackQueryHandler(cancel_wizard, pattern="^cancel_wizard$")]
)
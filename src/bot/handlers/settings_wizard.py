from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    CommandHandler,
    filters,
)
from sqlalchemy.future import select

from src.database.base import AsyncSessionLocal
from src.database.models import Bot
from src.utils.chat_manager import ChatManager
from src.utils.formatters import TextUtils
from src.bot.keyboards.dashboard import bot_management_keyboard
from src.bot.handlers.start import start_command
from src.services.bot_service import BotService

WAITING_DESCRIPTION = 1
WAITING_WELCOME = 2


async def start_edit_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia a edição da descrição/bio do bot no Telegram."""
    query = update.callback_query
    bot_id = int(query.data.split("_")[2])
    context.user_data["settings_bot_id"] = bot_id

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Bot).filter(Bot.id == bot_id))
        bot = result.scalars().first()
        context.user_data["settings_bot_token"] = bot.token

    text = TextUtils.pad_message(
        "<b>📝 Editar Perfil (Bio/Descrição)</b>\n\n"
        "Este é o texto que aparece <b>antes</b> da pessoa iniciar o bot.\n\n"
        "ℹ️ <b>Regras do Telegram:</b>\n"
        "• Apenas texto puro (sem negrito/itálico).\n"
        "• Sem fotos ou vídeos.\n"
        "• Máximo de 512 caracteres."
    )

    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔙 Cancelar", callback_data=f"manage_bot_{bot_id}")]]
    )
    await ChatManager.render_view(update, context, text, kb)
    return WAITING_DESCRIPTION


async def receive_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa a descrição enviada e atualiza o perfil do bot."""
    msg = update.message
    bot_id = context.user_data["settings_bot_id"]
    bot_token = context.user_data["settings_bot_token"]

    if msg.photo or msg.video or msg.document:
        await msg.reply_text(
            "❌ <b>Erro:</b> O perfil do Telegram aceita apenas texto.",
            parse_mode="HTML",
        )
        return WAITING_DESCRIPTION

    description_text = msg.text

    if not description_text:
        await msg.reply_text("❌ Envie um texto válido.")
        return WAITING_DESCRIPTION

    success = await BotService.update_bot_telegram_profile(bot_token, description_text)

    if not success:
        await msg.reply_text(
            "⚠️ Salvei no banco, mas o Telegram rejeitou atualizar o perfil (texto muito longo?)."
        )

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Bot).filter(Bot.id == bot_id))
        bot = result.scalars().first()
        if bot:
            bot.description = description_text
            await session.commit()
            saved_bot = bot

    await msg.reply_text("✅ <b>Perfil do Telegram Atualizado!</b>", parse_mode="HTML")

    text = TextUtils.pad_message(
        f"<b>⚙️ Gerenciando: {saved_bot.name}</b>\nO que deseja fazer?"
    )
    await ChatManager.render_view(
        update, context, text, bot_management_keyboard(saved_bot)
    )
    return ConversationHandler.END


async def start_edit_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia a edição da mensagem de boas-vindas do bot."""
    query = update.callback_query
    bot_id = int(query.data.split("_")[2])
    context.user_data["settings_bot_id"] = bot_id

    text = TextUtils.pad_message(
        "<b>👋 Editar Mensagem de Boas-Vindas</b>\n\n"
        "Esta é a mensagem enviada quando alguém clica em /start.\n\n"
        "✅ <b>Pode conter:</b> Texto, Emojis, <b>Foto ou Vídeo</b>.\n"
        "💡 <i>Se enviar mídia, coloque o texto na legenda.</i>"
    )

    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔙 Cancelar", callback_data=f"manage_bot_{bot_id}")]]
    )
    await ChatManager.render_view(update, context, text, kb)
    return WAITING_WELCOME


async def receive_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa a mensagem de boas-vindas (texto ou mídia com legenda)."""
    msg = update.message
    bot_id = context.user_data["settings_bot_id"]

    media_id = None
    media_type = None
    welcome_text = ""

    if msg.photo:
        media_id = msg.photo[-1].file_id
        media_type = "photo"
        welcome_text = msg.caption_html or ""
    elif msg.video:
        media_id = msg.video.file_id
        media_type = "video"
        welcome_text = msg.caption_html or ""
    else:
        welcome_text = msg.text_html or ""

    if not welcome_text and not media_id:
        await msg.reply_text("❌ Envie ao menos um texto ou mídia.")
        return WAITING_WELCOME

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Bot).filter(Bot.id == bot_id))
        bot = result.scalars().first()
        if bot:
            bot.welcome_message = welcome_text
            bot.welcome_media_id = media_id
            bot.welcome_media_type = media_type
            await session.commit()
            saved_bot = bot

    await msg.reply_text(
        "✅ <b>Boas-vindas Atualizada!</b>\nVeja o preview:", parse_mode="HTML"
    )

    if media_type == "photo":
        await context.bot.send_photo(
            chat_id=msg.chat_id, photo=media_id, caption=welcome_text, parse_mode="HTML"
        )
    elif media_type == "video":
        await context.bot.send_video(
            chat_id=msg.chat_id, video=media_id, caption=welcome_text, parse_mode="HTML"
        )
    else:
        await context.bot.send_message(
            chat_id=msg.chat_id, text=welcome_text, parse_mode="HTML"
        )

    text = TextUtils.pad_message(
        f"<b>⚙️ Gerenciando: {saved_bot.name}</b>\nO que deseja fazer?"
    )
    await ChatManager.render_view(
        update, context, text, bot_management_keyboard(saved_bot)
    )
    return ConversationHandler.END


async def cancel_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela a edição de configurações do bot."""
    bot_id = int(update.callback_query.data.split("_")[2])
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Bot).filter(Bot.id == bot_id))
        bot = result.scalars().first()
        text = TextUtils.pad_message(
            f"<b>⚙️ Gerenciando: {bot.name}</b>\nOperação cancelada."
        )
        await ChatManager.render_view(
            update, context, text, bot_management_keyboard(bot)
        )
    return ConversationHandler.END


async def restart_via_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reinicia o bot via comando /start durante o wizard."""
    await start_command(update, context)
    return ConversationHandler.END


settings_wizard_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_edit_description, pattern="^edit_desc_"),
        CallbackQueryHandler(start_edit_welcome, pattern="^edit_welcome_"),
    ],
    states={
        WAITING_DESCRIPTION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_description)
        ],
        WAITING_WELCOME: [
            MessageHandler(
                (filters.TEXT | filters.PHOTO | filters.VIDEO) & ~filters.COMMAND,
                receive_welcome,
            )
        ],
    },
    fallbacks=[
        CallbackQueryHandler(cancel_settings, pattern="^manage_bot_"),
        CommandHandler("start", restart_via_command),
    ],
)

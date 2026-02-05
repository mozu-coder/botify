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

WAITING_MSG_1 = 1
WAITING_MSG_2 = 2
WAITING_MSG_3 = 3


async def start_edit_followups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia o wizard de configuração de mensagens de remarketing."""
    query = update.callback_query
    bot_id = int(query.data.split("_")[2])
    context.user_data["settings_bot_id"] = bot_id
    context.user_data["new_followups"] = []

    text = TextUtils.pad_message(
        "<b>📢 Mensagens de Recuperação (1/3)</b>\n\n"
        "Estas mensagens serão enviadas automaticamente se o usuário interagir mas <b>NÃO</b> assinar (Remarketing).\n\n"
        "⚙️ <b>Como funciona:</b>\n"
        "Você pode definir até 3 variações. O sistema escolherá uma aleatoriamente para enviar ao usuário.\n"
        "<i>Se não definir nenhuma, usaremos uma mensagem padrão.</i>\n\n"
        "📝 <b>Envie a Variação #1:</b>\n"
        "<i>Ex: Vi que você conferiu nossos planos... não perca a chance!</i>"
    )

    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⏭ Pular esta", callback_data="skip_followup")],
            [InlineKeyboardButton("🔙 Cancelar", callback_data=f"manage_bot_{bot_id}")],
        ]
    )

    await ChatManager.render_view(update, context, text, kb)
    return WAITING_MSG_1


async def receive_msg_1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa a primeira mensagem de remarketing."""
    return await process_followup_step(update, context, 1)


async def skip_msg_1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pula a primeira mensagem de remarketing."""
    return await process_followup_step(update, context, 1, skipped=True)


async def receive_msg_2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa a segunda mensagem de remarketing."""
    return await process_followup_step(update, context, 2)


async def skip_msg_2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pula a segunda mensagem de remarketing."""
    return await process_followup_step(update, context, 2, skipped=True)


async def receive_msg_3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa a terceira mensagem de remarketing."""
    return await process_followup_step(update, context, 3)


async def skip_msg_3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pula a terceira mensagem de remarketing."""
    return await process_followup_step(update, context, 3, skipped=True)


async def process_followup_step(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    step_num: int,
    skipped: bool = False,
):
    """
    Processa cada etapa do wizard de mensagens de remarketing.

    Args:
        update: Update do Telegram
        context: Contexto da conversação
        step_num: Número da etapa atual (1-3)
        skipped: Se True, pula a etapa sem adicionar mensagem
    """
    bot_id = context.user_data["settings_bot_id"]
    current_list = context.user_data.get("new_followups", [])

    if not skipped:
        msg = update.message
        if msg.photo or msg.video or msg.document:
            await msg.reply_text(
                "❌ <b>Erro:</b> A recuperação deve ser apenas texto.",
                parse_mode="HTML",
            )
            return step_num

        text_content = msg.text_html
        current_list.append(text_content)

    context.user_data["new_followups"] = current_list

    next_step = step_num + 1

    if next_step <= 3:
        text = TextUtils.pad_message(
            f"<b>📢 Mensagens de Recuperação ({next_step}/3)</b>\n\n"
            f"✅ Variação #{step_num} processada.\n\n"
            f"📝 <b>Envie a Variação #{next_step}:</b>\n"
            "Quanto mais variações, menos repetitivo seu bot fica."
        )
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("⏭ Pular esta", callback_data="skip_followup")],
                [
                    InlineKeyboardButton(
                        "🔙 Cancelar", callback_data=f"manage_bot_{bot_id}"
                    )
                ],
            ]
        )

        if skipped and update.callback_query:
            await ChatManager.render_view(update, context, text, kb)
        else:
            await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")

        return next_step

    else:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Bot).filter(Bot.id == bot_id))
            bot = result.scalars().first()
            if bot:
                bot.followups = current_list
                await session.commit()
                saved_bot = bot

        count = len(current_list)
        msg_final = (
            "O bot usará o padrão do sistema."
            if count == 0
            else f"O bot alternará entre suas {count} mensagens."
        )

        text = TextUtils.pad_message(
            f"<b>✅ Recuperação Configurada!</b>\n\n" f"{msg_final}"
        )

        if update.callback_query:
            await ChatManager.render_view(
                update, context, text, bot_management_keyboard(saved_bot)
            )
        else:
            await update.message.reply_text(
                text, reply_markup=bot_management_keyboard(saved_bot), parse_mode="HTML"
            )

        return ConversationHandler.END


async def cancel_followups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela a configuração de mensagens de remarketing."""
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


followup_wizard_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_edit_followups, pattern="^edit_followups_")
    ],
    states={
        WAITING_MSG_1: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_msg_1),
            CallbackQueryHandler(skip_msg_1, pattern="^skip_followup$"),
        ],
        WAITING_MSG_2: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_msg_2),
            CallbackQueryHandler(skip_msg_2, pattern="^skip_followup$"),
        ],
        WAITING_MSG_3: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_msg_3),
            CallbackQueryHandler(skip_msg_3, pattern="^skip_followup$"),
        ],
    },
    fallbacks=[
        CallbackQueryHandler(cancel_followups, pattern="^manage_bot_"),
        CommandHandler("start", restart_via_command),
    ],
)

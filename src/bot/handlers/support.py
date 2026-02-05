from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CallbackQueryHandler

from src.utils.chat_manager import ChatManager
from src.utils.formatters import TextUtils


async def view_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exibe a central de ajuda com links para tutoriais e suporte."""
    suporte_url = "https://t.me/seuuser"
    tutorial_url = "https://google.com"

    text = TextUtils.pad_message(
        "<b>🆘 Central de Ajuda</b>\n\n"
        "Está com dúvidas sobre como configurar seu bot ou receber pagamentos?\n\n"
        "📌 <b>Dúvidas Frequentes:</b>\n"
        "• Como ativar meu bot?\n"
        "• Como funcionam os saques?\n"
        "• O bot parou de responder, o que fazer?\n\n"
        "Escolha uma opção abaixo para ser atendido:"
    )

    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📚 Ler Tutoriais / Docs", url=tutorial_url)],
            [InlineKeyboardButton("👨‍💻 Falar com Suporte Humano", url=suporte_url)],
            [InlineKeyboardButton("🔙 Voltar ao Menu", callback_data="back_to_main")],
        ]
    )

    await ChatManager.render_view(update, context, text, kb)


support_handler = CallbackQueryHandler(view_support, pattern="^support_view$")

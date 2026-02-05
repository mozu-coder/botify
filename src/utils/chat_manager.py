from telegram import Update, InlineKeyboardMarkup, Message
from telegram.ext import ContextTypes
from telegram.error import BadRequest


class ChatManager:
    """Gerenciador de mensagens do bot, mantendo apenas uma mensagem visível por vez."""

    @staticmethod
    async def clear_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Remove a mensagem enviada pelo usuário, se possível."""
        if update.message:
            try:
                await update.message.delete()
            except Exception:
                pass

    @staticmethod
    async def render_view(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        text: str,
        reply_markup: InlineKeyboardMarkup = None,
    ):
        """
        Renderiza uma view garantindo que apenas uma mensagem do bot fique visível.

        Comportamento:
        - Se for callback (clique em botão): edita a mensagem existente
        - Se for novo comando ou falha na edição: apaga a anterior e envia nova

        Args:
            update: Objeto de atualização do Telegram
            context: Contexto da conversação
            text: Texto da mensagem
            reply_markup: Teclado inline (opcional)
        """
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id

        last_msg_id = context.user_data.get("last_bot_msg_id")

        # Caso 1: Callback (edição)
        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(
                    text=text, reply_markup=reply_markup, parse_mode="HTML"
                )
                context.user_data["last_bot_msg_id"] = (
                    update.callback_query.message.message_id
                )
                return
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    return

        # Caso 2: Nova mensagem
        if last_msg_id:
            try:
                await context.bot.delete_message(
                    chat_id=chat_id, message_id=last_msg_id
                )
            except Exception:
                pass

        sent_msg: Message = await context.bot.send_message(
            chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode="HTML"
        )

        context.user_data["last_bot_msg_id"] = sent_msg.message_id

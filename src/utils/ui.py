from telegram import Update
from telegram.ext import ContextTypes


class UI:
    """Utilitários para feedback visual ao usuário."""

    @staticmethod
    async def show_toast(update: Update, message: str, alert: bool = False):
        """
        Exibe notificação ao usuário.

        Args:
            update: Objeto de atualização do Telegram
            message: Texto da notificação
            alert: Se True, exibe modal com botão OK. Se False, toast temporário
        """
        if update.callback_query:
            await update.callback_query.answer(text=message, show_alert=alert)

    @staticmethod
    async def answer_loading(update: Update):
        """Remove o indicador de carregamento do botão sem exibir mensagem."""
        if update.callback_query:
            await update.callback_query.answer()

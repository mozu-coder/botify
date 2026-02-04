from telegram import Update
from telegram.ext import ContextTypes

class UI:
    @staticmethod
    async def show_toast(update: Update, message: str, alert: bool = False):
        """
        Mostra uma notificação rápida para o usuário.
        
        Args:
            update: O objeto update do Telegram
            message: O texto a ser exibido
            alert: Se True, mostra um pop-up (modal) com botão OK. 
                   Se False, mostra apenas a notificação temporária no topo.
        """
        if update.callback_query:
            await update.callback_query.answer(
                text=message, 
                show_alert=alert
            )

    @staticmethod
    async def answer_loading(update: Update):
        """
        Apenas para parar o 'reloginho' de carregamento do botão
        sem mostrar mensagem nenhuma.
        """
        if update.callback_query:
            await update.callback_query.answer()
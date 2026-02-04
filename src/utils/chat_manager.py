from telegram import Update, InlineKeyboardMarkup, Message
from telegram.ext import ContextTypes
from telegram.error import BadRequest

class ChatManager:
    @staticmethod
    async def clear_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Tenta apagar a mensagem que o usuário acabou de enviar."""
        if update.message:
            try:
                await update.message.delete()
            except Exception:
                pass # Se não der pra apagar (ex: bot sem adm), segue a vida

    @staticmethod
    async def render_view(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, reply_markup: InlineKeyboardMarkup = None):
        """
        Inteligência central:
        1. Se for clique em botão -> Edita a mensagem.
        2. Se for comando novo -> Apaga o anterior do bot e manda um novo.
        3. Sempre garante que só exista UMA mensagem do bot na tela.
        """
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        # Tenta pegar o ID da última mensagem do bot salva no contexto
        last_msg_id = context.user_data.get('last_bot_msg_id')

        # Cenário 1: Callback (Clique no botão)
        if update.callback_query:
            try:
                # Tenta editar
                await update.callback_query.edit_message_text(
                    text=text, 
                    reply_markup=reply_markup, 
                    parse_mode='HTML'
                )
                # Atualiza o ID caso tenha mudado (raro em edit, mas seguro)
                context.user_data['last_bot_msg_id'] = update.callback_query.message.message_id
                return
            except BadRequest as e:
                # Se der erro "Message is not modified", ignoramos
                if "Message is not modified" in str(e):
                    return
                # Se a mensagem original foi apagada, cai no Cenário 2

        # Cenário 2: Nova mensagem ou Falha na edição
        # Primeiro, apaga a mensagem antiga do bot se ela existir visualmente
        if last_msg_id:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=last_msg_id)
            except Exception:
                pass # Mensagem já não existia

        # Envia a nova mensagem limpa
        sent_msg: Message = await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        
        # Salva o ID para a próxima interação
        context.user_data['last_bot_msg_id'] = sent_msg.message_id
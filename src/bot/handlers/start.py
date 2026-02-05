from telegram import Update
from telegram.ext import ContextTypes

from src.utils.chat_manager import ChatManager
from src.utils.formatters import TextUtils
from src.services.user_service import UserService
from src.bot.keyboards.menus import main_menu_keyboard


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Processa o comando /start.
    Registra o usuário no banco de dados e exibe o menu principal.
    """
    await ChatManager.clear_user_message(update, context)

    tg_user = update.effective_user
    db_user = await UserService.register_user(tg_user)

    welcome_text = TextUtils.pad_message(
        f"<b>Olá, {tg_user.first_name}! 👋</b>\n\n"
        "Bem-vindo ao <b>BotMaker</b>.\n"
        "Aqui você pode criar seus próprios bots de assinatura VIP, "
        "gerenciar planos e receber pagamentos via Pix automaticamente.\n\n"
        "👇 <b>O que você deseja fazer agora?</b>"
    )

    await ChatManager.render_view(
        update,
        context,
        text=welcome_text,
        reply_markup=main_menu_keyboard(is_admin=db_user.is_admin),
    )

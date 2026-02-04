from telegram import Update
from telegram.ext import ContextTypes

from src.utils.chat_manager import ChatManager
from src.utils.formatters import TextUtils
from src.services.user_service import UserService
from src.bot.keyboards.menus import main_menu_keyboard

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1. Limpa a mensagem do usuário (/start) para não poluir
    await ChatManager.clear_user_message(update, context)

    # 2. Registra no banco
    tg_user = update.effective_user
    db_user = await UserService.register_user(tg_user)

    # 3. Prepara o Texto
    # Usamos o pad_message pra garantir largura
    welcome_text = TextUtils.pad_message(
        f"<b>Olá, {tg_user.first_name}! 👋</b>\n\n"
        "Bem-vindo ao <b>BotMaker</b>.\n"
        "Aqui você pode criar seus próprios bots de assinatura VIP, "
        "gerenciar planos e receber pagamentos via Pix automaticamente.\n\n"
        "👇 <b>O que você deseja fazer agora?</b>"
    )

    # 4. Renderiza a View (Apaga anterior do bot e manda nova)
    await ChatManager.render_view(
        update, 
        context, 
        text=welcome_text, 
        reply_markup=main_menu_keyboard(is_admin=db_user.is_admin)
    )

# Handler para o botão "Voltar" (Menu Principal)
async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_command(update, context)
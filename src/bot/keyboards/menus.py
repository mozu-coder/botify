from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard(is_admin: bool = False):
    """Gera o teclado do menu principal da aplicação."""
    keyboard = [
        [
            InlineKeyboardButton("🚀 Criar Novo Bot", callback_data="wizard_new_bot"),
        ],
        [
            InlineKeyboardButton("🤖 Meus Bots", callback_data="my_bots_list"),
            InlineKeyboardButton("💰 Minha Carteira", callback_data="wallet_view"),
        ],
        [
            InlineKeyboardButton("🆘 Suporte / Ajuda", callback_data="support_view"),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)

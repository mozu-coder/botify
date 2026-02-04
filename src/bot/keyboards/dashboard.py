from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from src.utils.formatters import TextUtils

def my_bots_list_keyboard(bots):
    """Gera lista de botões com os bots do usuário"""
    keyboard = []
    for bot in bots:
        keyboard.append([
            InlineKeyboardButton(f"🤖 {bot.name}", callback_data=f"manage_bot_{bot.id}")
        ])
    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="back_to_main")])
    return InlineKeyboardMarkup(keyboard)

def bot_management_keyboard(bot):
    """Menu principal de gestão de UM bot específico"""
    # Ícone dinâmico do status
    status_icon = "🟢" if bot.is_active else "🔴"
    status_text = "Desativar" if bot.is_active else "Ativar"

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📝 Editar Descrição", callback_data=f"edit_desc_{bot.id}"),
            InlineKeyboardButton("👋 Boas-Vindas", callback_data=f"edit_welcome_{bot.id}")
        ],
        [
            InlineKeyboardButton("📢 Follow-ups", callback_data=f"edit_followups_{bot.id}"),
            InlineKeyboardButton("💎 Gerenciar Planos", callback_data=f"manage_plans_{bot.id}"),
        ],
        [
            InlineKeyboardButton("🔄 Trocar Grupo Vinculado", callback_data=f"change_group_{bot.id}")
        ],
        [
            InlineKeyboardButton(f"{status_icon} {status_text}", callback_data=f"toggle_bot_{bot.id}"),
            InlineKeyboardButton("🗑 Excluir Bot", callback_data=f"delete_bot_{bot.id}")
        ],
        [
            InlineKeyboardButton("🔙 Voltar para Lista", callback_data="my_bots_list")
        ]
    ])

def plans_list_keyboard(plans, bot_id):
    """Lista os planos existentes + botão de criar"""
    keyboard = []
    for plan in plans:
        status = "✅" if plan.is_active else "❌"
        # Agora o callback envia para 'open_plan_ID'
        btn_text = f"{status} {plan.name} - {TextUtils.currency(plan.price)}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"open_plan_{plan.id}")])
        
    keyboard.append([InlineKeyboardButton("➕ Criar Novo Plano", callback_data=f"new_plan_{bot_id}")])
    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data=f"manage_bot_{bot_id}")])
    return InlineKeyboardMarkup(keyboard)

def single_plan_keyboard(plan):
    """Menu de ações para um plano específico"""
    status_text = "Desativar ❌" if plan.is_active else "Ativar ✅"
    
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✏️ Nome", callback_data=f"edit_plan_name_{plan.id}"),
            InlineKeyboardButton("✏️ Valor", callback_data=f"edit_plan_price_{plan.id}"),
            InlineKeyboardButton("✏️ Dias", callback_data=f"edit_plan_days_{plan.id}")
        ],
        [
            InlineKeyboardButton(status_text, callback_data=f"toggle_plan_{plan.id}"),
            InlineKeyboardButton("🗑 Apagar", callback_data=f"delete_plan_{plan.id}")
        ],
        [
            InlineKeyboardButton("🔙 Voltar", callback_data=f"manage_plans_{plan.bot_id}")
        ]
    ])
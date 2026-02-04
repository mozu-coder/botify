from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from sqlalchemy.future import select
from sqlalchemy import delete

from src.database.base import AsyncSessionLocal
from src.database.models import Plan
from src.utils.chat_manager import ChatManager
from src.utils.formatters import TextUtils
from src.utils.ui import UI
from src.bot.keyboards.dashboard import single_plan_keyboard, plans_list_keyboard

# Estados para edição
EDITING_VALUE = 1

async def open_plan_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Abre o menu do plano selecionado"""
    query = update.callback_query
    plan_id = int(query.data.split("_")[2]) # open_plan_123
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Plan).filter(Plan.id == plan_id))
        plan = result.scalars().first()
        
        if not plan:
            await UI.show_toast(update, "Plano não encontrado!", alert=True)
            return

        status = "Ativo ✅" if plan.is_active else "Inativo ❌"
        
        text = TextUtils.pad_message(
            f"<b>⚙️ Gerenciar Plano</b>\n\n"
            f"🏷 <b>Nome:</b> {plan.name}\n"
            f"💰 <b>Valor:</b> {TextUtils.currency(plan.price)}\n"
            f"⏳ <b>Duração:</b> {TextUtils.duration(plan.days)}\n"
            f"📡 <b>Status:</b> {status}\n\n"
            "O que deseja alterar?"
        )
        
        await ChatManager.render_view(update, context, text, single_plan_keyboard(plan))

async def toggle_plan_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ativa/Desativa o plano"""
    plan_id = int(update.callback_query.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Plan).filter(Plan.id == plan_id))
        plan = result.scalars().first()
        
        if plan:
            plan.is_active = not plan.is_active
            await session.commit()
            await UI.show_toast(update, f"Plano {'ativado' if plan.is_active else 'desativado'}!")
            
            # Recarrega a view
            await open_plan_details(update, context)

async def delete_plan_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pede confirmação para deletar"""
    plan_id = int(update.callback_query.data.split("_")[2])
    
    text = TextUtils.pad_message(
        "<b>⚠️ Tem certeza?</b>\n\n"
        "Apagar este plano não afetará assinaturas ativas, "
        "mas ninguém poderá assinar ele novamente."
    )
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Sim, Apagar", callback_data=f"confirm_delete_{plan_id}")],
        [InlineKeyboardButton("Cancelar", callback_data=f"open_plan_{plan_id}")]
    ])
    
    await ChatManager.render_view(update, context, text, kb)

async def delete_plan_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Executa a deleção"""
    plan_id = int(update.callback_query.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Plan).filter(Plan.id == plan_id))
        plan = result.scalars().first()
        bot_id = plan.bot_id if plan else None
        
        if plan:
            await session.delete(plan)
            await session.commit()
            await UI.show_toast(update, "Plano apagado com sucesso!")
        
        # Redireciona de volta para a lista de planos
        # Simulando o callback para view_plans do dashboard
        update.callback_query.data = f"manage_plans_{bot_id}"
        from src.bot.handlers.dashboard import view_plans
        await view_plans(update, context)

# --- Lógica de Edição de Campos (Wizard Curto) ---

async def start_edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia a edição de Nome, Preço ou Dias"""
    query = update.callback_query
    data = query.data.split("_") # edit_plan_FIELD_ID
    field = data[2] # name, price, days
    plan_id = int(data[3])
    
    context.user_data['edit_plan_id'] = plan_id
    context.user_data['edit_field'] = field
    
    field_names = {'name': 'Nome', 'price': 'Valor', 'days': 'Duração (Dias)'}
    
    text = TextUtils.pad_message(
        f"<b>✏️ Editando: {field_names[field]}</b>\n\n"
        "Envie o novo valor para este campo:"
    )
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancelar", callback_data=f"open_plan_{plan_id}")]])
    await ChatManager.render_view(update, context, text, kb)
    
    return EDITING_VALUE

async def receive_new_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ChatManager.clear_user_message(update, context)
    value = update.message.text
    
    plan_id = context.user_data['edit_plan_id']
    field = context.user_data['edit_field']
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Plan).filter(Plan.id == plan_id))
        plan = result.scalars().first()
        
        if not plan:
            return ConversationHandler.END
            
        try:
            if field == 'name':
                plan.name = value
            elif field == 'price':
                plan.price = float(value.replace(',', '.'))
            elif field == 'days':
                plan.days = int(value)
                
            await session.commit()
            # Removido UI.show_toast aqui pois mensagem de texto não suporta callback answer
            
        except ValueError:
            # Removido UI.show_toast com alert=True pois causaria erro
            await update.message.reply_text("❌ Valor inválido! Tente novamente.")
            return EDITING_VALUE # Tenta de novo

    # Retorna para o menu do plano
    # Apenas chamamos o render manual, sem tentar hackear o update
    await open_plan_details_manual(update, context, plan_id)
    return ConversationHandler.END

async def cancel_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plan_id = int(update.callback_query.data.split("_")[2])
    await open_plan_details(update, context)
    return ConversationHandler.END

# Auxiliar para chamar o menu do plano sem ter um callback query real (vindo do receive_new_value)
async def open_plan_details_manual(update, context, plan_id):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Plan).filter(Plan.id == plan_id))
        plan = result.scalars().first()
        status = "Ativo ✅" if plan.is_active else "Inativo ❌"
        text = TextUtils.pad_message(
            f"<b>⚙️ Gerenciar Plano</b>\n\n"
            f"🏷 <b>Nome:</b> {plan.name}\n"
            f"💰 <b>Valor:</b> {TextUtils.currency(plan.price)}\n"
            f"⏳ <b>Duração:</b> {TextUtils.duration(plan.days)}\n"
            f"📡 <b>Status:</b> {status}\n\n"
            "O que deseja alterar?"
        )
        # ChatManager.render_view sabe lidar com edição baseada no last_bot_msg_id
        await ChatManager.render_view(update, context, text, single_plan_keyboard(plan))

# O Handler de Conversa para Edição
plan_edit_conversation = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_edit_field, pattern="^edit_plan_")],
    states={
        EDITING_VALUE: [MessageHandler(filters.TEXT, receive_new_value)]
    },
    fallbacks=[CallbackQueryHandler(cancel_edit, pattern="^open_plan_")]
)

# Os Handlers de ação direta (sem conversa)
plan_action_handlers = [
    CallbackQueryHandler(open_plan_details, pattern="^open_plan_"),
    CallbackQueryHandler(toggle_plan_status, pattern="^toggle_plan_"),
    CallbackQueryHandler(delete_plan_confirm, pattern="^delete_plan_"),
    CallbackQueryHandler(delete_plan_action, pattern="^confirm_delete_")
]
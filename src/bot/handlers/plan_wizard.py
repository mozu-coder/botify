from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters

from src.database.base import AsyncSessionLocal
from src.database.models import Plan
from src.utils.chat_manager import ChatManager
from src.utils.formatters import TextUtils
from src.bot.keyboards.dashboard import plans_list_keyboard
from sqlalchemy.future import select

# Estados
WAITING_NAME, WAITING_PRICE, WAITING_DAYS = range(3)

async def start_new_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Salva o ID do bot que veio no botão "new_plan_123"
    bot_id = int(update.callback_query.data.split("_")[2])
    context.user_data['plan_bot_id'] = bot_id
    
    text = TextUtils.pad_message(
        "<b>💎 Novo Plano: Nome</b>\n\n"
        "Digite o nome que aparecerá no botão.\n"
        "<i>Ex: VIP Mensal, Grupo Gold, Acesso Total</i>"
    )
    # Botão de cancelar volta para a lista de planos
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancelar", callback_data=f"manage_plans_{bot_id}")]])
    
    await ChatManager.render_view(update, context, text, kb)
    return WAITING_NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ChatManager.clear_user_message(update, context)
    name = update.message.text.strip()
    context.user_data['plan_name'] = name
    
    bot_id = context.user_data['plan_bot_id']
    
    text = TextUtils.pad_message(
        f"<b>Nome: {name}</b>\n\n"
        "<b>💰 Qual o valor do plano?</b>\n"
        "Digite apenas números (use ponto ou vírgula).\n"
        "<i>Ex: 29.90</i>"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancelar", callback_data=f"manage_plans_{bot_id}")]])
    await ChatManager.render_view(update, context, text, kb)
    return WAITING_PRICE

async def receive_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ChatManager.clear_user_message(update, context)
    price_text = update.message.text.replace(',', '.')
    bot_id = context.user_data['plan_bot_id']
    
    try:
        price = float(price_text)
        context.user_data['plan_price'] = price
    except ValueError:
        # Se digitar errado, avisa e mantém no estado
        text = TextUtils.pad_message("<b>❌ Valor inválido!</b>\nDigite algo como 10.00 ou 29,90")
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancelar", callback_data=f"manage_plans_{bot_id}")]])
        await ChatManager.render_view(update, context, text, kb)
        return WAITING_PRICE

    text = TextUtils.pad_message(
        f"<b>Valor: {TextUtils.currency(price)}</b>\n\n"
        "<b>⏳ Qual a duração em DIAS?</b>\n"
        "Digite a quantidade de dias de acesso.\n"
        "💡 <i>Dica: Digite 36500 para Vitalício.</i>"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancelar", callback_data=f"manage_plans_{bot_id}")]])
    await ChatManager.render_view(update, context, text, kb)
    return WAITING_DAYS

async def receive_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ChatManager.clear_user_message(update, context)
    
    bot_id = context.user_data['plan_bot_id']
    try:
        days = int(update.message.text)
    except ValueError:
        return WAITING_DAYS # Ignora input invalido ou mostra erro

    # Salva no Banco
    async with AsyncSessionLocal() as session:
        new_plan = Plan(
            bot_id=bot_id,
            name=context.user_data['plan_name'],
            price=context.user_data['plan_price'],
            days=days
        )
        session.add(new_plan)
        await session.commit()
        
        # Recarrega a lista para mostrar atualizado
        result = await session.execute(select(Plan).filter(Plan.bot_id == bot_id))
        plans = result.scalars().all()
    
    text = TextUtils.pad_message(
        "<b>✅ Plano Criado com Sucesso!</b>\n"
        f"O plano <b>{new_plan.name}</b> já está ativo no seu bot."
    )
    
    await ChatManager.render_view(update, context, text, plans_list_keyboard(plans, bot_id))
    return ConversationHandler.END

# Encerra o wizard se o usuário clicar em cancelar (volta pro menu de planos)
async def cancel_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # manage_plans_{bot_id}
    bot_id = int(query.data.split("_")[2])
    
    # Redireciona para a view de planos chamando a função view_plans do dashboard
    # Truque: importamos a função de view lá no main, aqui vamos só renderizar manualmente
    # para evitar dependencia circular.
    from src.bot.handlers.dashboard import view_plans
    await view_plans(update, context)
    return ConversationHandler.END

plan_wizard_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_new_plan, pattern="^new_plan_")],
    states={
        WAITING_NAME: [MessageHandler(filters.TEXT, receive_name)],
        WAITING_PRICE: [MessageHandler(filters.TEXT, receive_price)],
        WAITING_DAYS: [MessageHandler(filters.TEXT, receive_days)],
    },
    fallbacks=[CallbackQueryHandler(cancel_plan, pattern="^manage_plans_")]
)
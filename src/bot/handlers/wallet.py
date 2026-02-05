from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from src.utils.chat_manager import ChatManager
from src.utils.formatters import TextUtils
from src.utils.ui import UI
from src.services.finance_service import FinanceService
from src.core.config import settings

WAITING_AMOUNT = 1
WAITING_PIX = 2


async def view_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exibe o saldo e informações da carteira do usuário."""
    user_id = update.effective_user.id
    balance = await FinanceService.get_balance(user_id)

    fee_in_pct = int((settings.FEE_IN_PLATFORM + settings.FEE_IN_PROFIT) * 100)
    fee_out_pct = int((settings.FEE_OUT_PLATFORM + settings.FEE_OUT_PROFIT) * 100)
    min_fee_val = TextUtils.currency(settings.FEE_IN_MIN_FIXED)

    text = TextUtils.pad_message(
        "<b>💰 Minha Carteira</b>\n\n"
        f"💵 <b>Saldo Disponível:</b> {TextUtils.currency(balance)}\n\n"
        "<b>📊 Taxas:</b>\n"
        f"• Recebimento: {fee_in_pct}% (Mínimo {min_fee_val})\n"
        f"• Saque: {fee_out_pct}% (Mínimo {min_fee_val})"
    )

    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📜 Extrato Detalhado", callback_data="wallet_extract"
                )
            ],
            [
                InlineKeyboardButton(
                    "💸 Solicitar Saque", callback_data="wallet_withdraw"
                )
            ],
            [InlineKeyboardButton("� Menu Principal", callback_data="back_to_main")],
        ]
    )

    await ChatManager.render_view(update, context, text, kb)


async def view_extract(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exibe o extrato detalhado das últimas transações."""
    user_id = update.effective_user.id
    transactions = await FinanceService.get_extract(user_id)
    msg_lines = ["<b>📜 Últimas 15 Movimentações</b>\n"]

    if not transactions:
        msg_lines.append("<i>Nenhuma movimentação encontrada.</i>")
    else:
        for t in transactions:
            if "Taxa de Serviço" in t.description:
                continue
            icon = "🟢" if t.amount > 0 else "🔴"
            date = t.created_at.strftime("%d/%m %H:%M")
            msg_lines.append(f"{icon} <b>{TextUtils.currency(t.amount)}</b> | {date}")
            msg_lines.append(f"   <i>{t.description}</i>")

    text = TextUtils.pad_message("\n".join(msg_lines))
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔙 Voltar", callback_data="wallet_view")]]
    )
    await ChatManager.render_view(update, context, text, kb)


async def start_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia o processo de solicitação de saque."""
    user_id = update.effective_user.id
    balance = await FinanceService.get_balance(user_id)

    if balance < settings.MIN_WITHDRAWAL:
        await UI.show_toast(
            update,
            f"Mínimo para saque: {TextUtils.currency(settings.MIN_WITHDRAWAL)}",
            alert=True,
        )
        return ConversationHandler.END

    text = TextUtils.pad_message(
        "<b>💸 Novo Saque</b>\n\n"
        f"Disponível: {TextUtils.currency(balance)}\n\n"
        "<b>Quanto você quer retirar da plataforma?</b>\n"
        "<i>As taxas serão descontadas desse valor.</i>\n\n"
        "Digite o valor (ex: 150.00):"
    )
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔙 Cancelar", callback_data="wallet_view")]]
    )
    await ChatManager.render_view(update, context, text, kb)
    return WAITING_AMOUNT


async def receive_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa o valor digitado pelo usuário para saque."""
    await ChatManager.clear_user_message(update, context)
    try:
        text_val = update.message.text.replace(",", ".")
        amount_gross = float(text_val)
    except ValueError:
        await UI.show_toast(update, "Valor inválido!", alert=True)
        return WAITING_AMOUNT

    user_id = update.effective_user.id
    balance = await FinanceService.get_balance(user_id)

    if amount_gross > balance:
        msg = (
            f"<b>❌ Saldo Insuficiente</b>\n\n"
            f"Você tentou retirar: {TextUtils.currency(amount_gross)}\n"
            f"Seu saldo atual: {TextUtils.currency(balance)}\n\n"
            "Digite um valor menor ou igual ao seu saldo:"
        )
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Cancelar", callback_data="wallet_view")]]
        )
        await ChatManager.render_view(update, context, TextUtils.pad_message(msg), kb)
        return WAITING_AMOUNT

    fees = FinanceService.calculate_fees_from_total(amount_gross)
    net_receive = amount_gross - fees

    if net_receive <= 0:
        await UI.show_toast(update, "Valor muito baixo para cobrir taxas.", alert=True)
        return WAITING_AMOUNT

    context.user_data["withdraw_gross"] = amount_gross

    text = TextUtils.pad_message(
        f"<b>📝 Resumo da Retirada:</b>\n\n"
        f"🏦 <b>Sai da Carteira:</b> {TextUtils.currency(amount_gross)}\n"
        f"📉 <b>Taxas (7%):</b> - {TextUtils.currency(fees)}\n"
        f"💰 <b>VOCÊ RECEBE NO PIX: {TextUtils.currency(net_receive)}</b>\n\n"
        "<b>Para onde enviar?</b>\n"
        "Digite sua chave PIX (CPF, Email, etc):"
    )
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔙 Cancelar", callback_data="wallet_view")]]
    )
    await ChatManager.render_view(update, context, text, kb)
    return WAITING_PIX


async def receive_pix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa a chave PIX e finaliza a solicitação de saque."""
    await ChatManager.clear_user_message(update, context)
    pix_key = update.message.text.strip()
    amount_gross = context.user_data["withdraw_gross"]
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name
    username = update.effective_user.username or "SemUser"

    try:
        withdrawal = await FinanceService.request_withdrawal(
            user_id, amount_gross, pix_key
        )
        current_balance = await FinanceService.get_balance(user_id)

        admin_text = (
            f"<b>💸 Nova Solicitação de Saque #{withdrawal.id}</b>\n\n"
            f"👤 <b>Usuário:</b> {user_name} (@{username})\n"
            f"🆔 <b>ID:</b> <code>{user_id}</code>\n\n"
            f"🏦 <b>Debitado:</b> {TextUtils.currency(withdrawal.amount_final)}\n"
            f"📉 <b>Taxas:</b> {TextUtils.currency(withdrawal.fee_total)}\n"
            f"💰 <b>VALOR A PAGAR PIX:</b> {TextUtils.currency(withdrawal.amount_requested)}\n\n"
            f"💳 <b>Saldo Remanescente:</b> {TextUtils.currency(current_balance)}\n\n"
            f"🔑 <b>Chave Pix:</b> <code>{pix_key}</code>"
        )

        admin_kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✅ Confirmar Pagamento",
                        callback_data=f"admin_pay_{withdrawal.id}",
                    ),
                    InlineKeyboardButton(
                        "❌ Rejeitar/Estornar",
                        callback_data=f"admin_reject_{withdrawal.id}",
                    ),
                ]
            ]
        )

        await context.bot.send_message(
            chat_id=settings.ADMIN_WITHDRAWAL_GROUP_ID,
            text=admin_text,
            reply_markup=admin_kb,
            parse_mode="HTML",
        )

        text = TextUtils.pad_message(
            "<b>✅ Solicitação Recebida!</b>\n\n"
            f"Valor que cairá na conta: <b>{TextUtils.currency(withdrawal.amount_requested)}</b>\n"
            f"Status: ⏳ <b>Em Análise</b>\n\n"
            "O pagamento será processado em até <b>3 dias úteis</b>."
        )
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Ir para Carteira", callback_data="wallet_view")]]
        )
        await ChatManager.render_view(update, context, text, kb)
        return ConversationHandler.END

    except ValueError as e:
        await UI.show_toast(update, str(e), alert=True)
        return ConversationHandler.END


async def cancel_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela o processo de saque."""
    query = update.callback_query
    await query.answer()
    await view_wallet(update, context)
    return ConversationHandler.END


withdrawal_wizard = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_withdrawal, pattern="^wallet_withdraw$")],
    states={
        WAITING_AMOUNT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_amount)
        ],
        WAITING_PIX: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_pix)],
    },
    fallbacks=[CallbackQueryHandler(cancel_withdrawal, pattern="^wallet_view$")],
)

wallet_handlers = [
    CallbackQueryHandler(view_wallet, pattern="^wallet_view$"),
    CallbackQueryHandler(view_extract, pattern="^wallet_extract$"),
    withdrawal_wizard,
]

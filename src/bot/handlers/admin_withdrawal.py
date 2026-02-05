from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CallbackQueryHandler
from sqlalchemy.future import select
from datetime import datetime

from src.database.base import AsyncSessionLocal
from src.database.models import (
    Withdrawal,
    WithdrawalStatus,
    Transaction,
    TransactionType,
)
from src.utils.formatters import TextUtils


async def approve_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Aprova solicitação de saque, atualiza status e notifica o usuário.
    """
    query = update.callback_query
    withdrawal_id = int(query.data.split("_")[2])

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Withdrawal).filter(Withdrawal.id == withdrawal_id)
        )
        withdrawal = result.scalars().first()

        if not withdrawal:
            await query.answer("Saque não encontrado!", show_alert=True)
            return

        if withdrawal.status != WithdrawalStatus.PENDING:
            await query.answer(
                f"Este saque já está {withdrawal.status.value}", show_alert=True
            )
            return

        withdrawal.status = WithdrawalStatus.PAID
        withdrawal.processed_at = datetime.now()
        await session.commit()

        original_text = query.message.text_html
        new_text = (
            f"{original_text}\n\n✅ <b>PAGO por {update.effective_user.first_name}</b>"
        )
        await query.edit_message_text(new_text, parse_mode="HTML", reply_markup=None)

        try:
            await context.bot.send_message(
                chat_id=withdrawal.user_id,
                text=(
                    f"✅ <b>Saque Aprovado!</b>\n\n"
                    f"Seu saque de <b>{TextUtils.currency(withdrawal.amount_requested)}</b> foi processado.\n"
                    "O valor deve cair na sua conta em instantes."
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass


async def reject_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Rejeita solicitação de saque e estorna o valor para o saldo do usuário.
    """
    query = update.callback_query
    withdrawal_id = int(query.data.split("_")[2])

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Withdrawal).filter(Withdrawal.id == withdrawal_id)
        )
        withdrawal = result.scalars().first()

        if not withdrawal or withdrawal.status != WithdrawalStatus.PENDING:
            await query.answer("Saque inválido ou já processado.", show_alert=True)
            return

        withdrawal.status = WithdrawalStatus.REJECTED
        withdrawal.processed_at = datetime.now()

        refund = Transaction(
            user_id=withdrawal.user_id,
            type=TransactionType.SALE,
            description=f"Estorno Saque #{withdrawal.id} (Rejeitado)",
            amount=withdrawal.amount_final,
        )
        session.add(refund)
        await session.commit()

        original_text = query.message.text_html
        new_text = f"{original_text}\n\n❌ <b>REJEITADO por {update.effective_user.first_name}</b>"
        await query.edit_message_text(new_text, parse_mode="HTML", reply_markup=None)

        try:
            await context.bot.send_message(
                chat_id=withdrawal.user_id,
                text=(
                    f"❌ <b>Saque Rejeitado</b>\n\n"
                    f"Seu saque de {TextUtils.currency(withdrawal.amount_requested)} foi rejeitado e o valor estornado para sua carteira.\n"
                    "Entre em contato com o suporte se tiver dúvidas."
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass


admin_handlers = [
    CallbackQueryHandler(approve_withdrawal, pattern="^admin_pay_"),
    CallbackQueryHandler(reject_withdrawal, pattern="^admin_reject_"),
]

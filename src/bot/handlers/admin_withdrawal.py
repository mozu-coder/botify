from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CallbackQueryHandler
from sqlalchemy.future import select
from datetime import datetime

from src.database.base import AsyncSessionLocal
from src.database.models import Withdrawal, WithdrawalStatus, Transaction, TransactionType
from src.utils.formatters import TextUtils

"""
Processa a ação de pagamento manual pelo administrador.
Atualiza o status para PAID e notifica o usuário.
"""
async def approve_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    withdrawal_id = int(query.data.split("_")[2]) # admin_pay_123
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Withdrawal).filter(Withdrawal.id == withdrawal_id))
        withdrawal = result.scalars().first()
        
        if not withdrawal:
            await query.answer("Saque não encontrado!", show_alert=True)
            return
            
        if withdrawal.status != WithdrawalStatus.PENDING:
            await query.answer(f"Este saque já está {withdrawal.status.value}", show_alert=True)
            return

        # 1. Atualiza Status
        withdrawal.status = WithdrawalStatus.PAID
        withdrawal.processed_at = datetime.now()
        await session.commit()
        
        # 2. Atualiza Mensagem no Grupo Admin (Remove botões)
        original_text = query.message.text_html
        new_text = f"{original_text}\n\n✅ <b>PAGO por {update.effective_user.first_name}</b>"
        await query.edit_message_text(new_text, parse_mode="HTML", reply_markup=None)
        
        # 3. Notifica o Usuário no Privado
        try:
            await context.bot.send_message(
                chat_id=withdrawal.user_id,
                text=(
                    f"✅ <b>Saque Aprovado!</b>\n\n"
                    f"Seu saque de <b>{TextUtils.currency(withdrawal.amount_requested)}</b> foi processado.\n"
                    "O valor deve cair na sua conta em instantes."
                ),
                parse_mode="HTML"
            )
        except Exception:
            pass # Usuário bloqueou o bot?

"""
Processa a rejeição do saque.
Estorna o valor (Valor + Taxas) para o saldo do usuário.
"""
async def reject_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    withdrawal_id = int(query.data.split("_")[2]) # admin_reject_123
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Withdrawal).filter(Withdrawal.id == withdrawal_id))
        withdrawal = result.scalars().first()
        
        if not withdrawal or withdrawal.status != WithdrawalStatus.PENDING:
            await query.answer("Saque inválido ou já processado.", show_alert=True)
            return

        # 1. Atualiza Status
        withdrawal.status = WithdrawalStatus.REJECTED
        withdrawal.processed_at = datetime.now()
        
        # 2. Estorno Financeiro (Devolve Valor + Taxas)
        refund = Transaction(
            user_id=withdrawal.user_id,
            type=TransactionType.SALE, # Usamos SALE ou criamos tipo REFUND. SALE soma saldo positivo.
            description=f"Estorno Saque #{withdrawal.id} (Rejeitado)",
            amount=withdrawal.amount_final # Devolve tudo que foi debitado
        )
        session.add(refund)
        await session.commit()

        # 3. Atualiza Admin
        original_text = query.message.text_html
        new_text = f"{original_text}\n\n❌ <b>REJEITADO por {update.effective_user.first_name}</b>"
        await query.edit_message_text(new_text, parse_mode="HTML", reply_markup=None)

        # 4. Notifica Usuário
        try:
            await context.bot.send_message(
                chat_id=withdrawal.user_id,
                text=(
                    f"❌ <b>Saque Rejeitado</b>\n\n"
                    f"Seu saque de {TextUtils.currency(withdrawal.amount_requested)} foi rejeitado e o valor estornado para sua carteira.\n"
                    "Entre em contato com o suporte se tiver dúvidas."
                ),
                parse_mode="HTML"
            )
        except Exception:
            pass

admin_handlers = [
    CallbackQueryHandler(approve_withdrawal, pattern="^admin_pay_"),
    CallbackQueryHandler(reject_withdrawal, pattern="^admin_reject_")
]
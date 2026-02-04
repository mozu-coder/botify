from sqlalchemy.future import select
from sqlalchemy import func, desc
from src.database.base import AsyncSessionLocal
from src.database.models import Transaction, TransactionType, Withdrawal, WithdrawalStatus
from src.core.config import settings

class FinanceService:
    
    @staticmethod
    def calculate_fees_from_total(amount_gross: float) -> float:
        """
        Calcula a taxa baseada no valor BRUTO (Total a debitar).
        GGPIX: 2% (min 0.77) + USER: 5% = Total 7% sobre o valor retirado.
        """
        # Taxa percentual total (Plataforma + Lucro)
        pct_total = settings.FEE_OUT_PLATFORM + settings.FEE_OUT_PROFIT
        
        # Calcula taxa percentual
        fee_pct = amount_gross * pct_total
        
        # Compara com o mínimo fixo da plataforma (R$ 0.77)
        final_fee = max(fee_pct, settings.FEE_OUT_MIN_FIXED)
        
        return round(final_fee, 2)

    @staticmethod
    async def get_balance(user_id: int) -> float:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(func.sum(Transaction.amount)).filter(Transaction.user_id == user_id)
            )
            balance = result.scalar()
            return round(balance, 2) if balance else 0.00

    @staticmethod
    async def get_extract(user_id: int, limit: int = 15):
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Transaction)
                .filter(Transaction.user_id == user_id)
                .filter(Transaction.amount != 0) 
                .order_by(desc(Transaction.created_at))
                .limit(limit)
            )
            return result.scalars().all()

    @staticmethod
    async def request_withdrawal(user_id: int, amount_gross: float, pix_key: str, pix_type: str = "CPF"):
        """
        Gera o saque unificando as taxas na transação para o extrato ficar limpo.
        """
        # 1. Validação de Mínimo
        if amount_gross < settings.MIN_WITHDRAWAL:
            raise ValueError(f"O valor mínimo para movimentação é R$ {settings.MIN_WITHDRAWAL:.2f}")

        # 2. Verifica Saldo
        balance = await FinanceService.get_balance(user_id)
        if balance < amount_gross:
            raise ValueError(f"Saldo insuficiente. Você tem R$ {balance:.2f} e tentou retirar R$ {amount_gross:.2f}")

        # 3. Calcula Taxas e Valor Líquido
        fees = FinanceService.calculate_fees_from_total(amount_gross)
        net_to_receive = amount_gross - fees

        if net_to_receive <= 0:
            raise ValueError("O valor informado não cobre as taxas mínimas de saque.")

        async with AsyncSessionLocal() as session:
            # 4. Registra o Saque (Tabela de Controle Administrativo)
            # Aqui mantemos separado para você saber quanto é taxa e quanto é saque
            withdrawal = Withdrawal(
                user_id=user_id,
                amount_requested=net_to_receive, # Vai receber isso no Pix
                fee_total=fees,                  # Ficou isso pra plataforma
                amount_final=amount_gross,       # Saiu isso da conta do user
                pix_key=pix_key,
                pix_type=pix_type,
                status=WithdrawalStatus.PENDING
            )
            session.add(withdrawal)
            
            # 5. Debita do Saldo (Tabela de Extrato do Usuário)
            # TRUQUE: Unificamos em UMA transação de saída com o valor TOTAL (Bruto).
            # Mas na descrição informamos quanto ele recebe de verdade.
            # Assim, o saldo bate (saiu 150) e não tem linha de "Taxa".
            
            t_main = Transaction(
                user_id=user_id,
                type=TransactionType.WITHDRAWAL,
                # Ex: "Saque Pix (Recebido: R$ 140.00)"
                description=f"Saque Pix (Liq: R$ {net_to_receive:.2f})",
                amount=-amount_gross # Debita o total (R$ 150.00)
            )
            session.add(t_main)
            
            # NÃO ADICIONAMOS MAIS A TRANSAÇÃO SEPARADA DE TAXA (t_fee)
            
            await session.commit()
            return withdrawal
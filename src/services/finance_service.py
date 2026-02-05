from sqlalchemy.future import select
from sqlalchemy import func, desc
from src.database.base import AsyncSessionLocal
from src.database.models import (
    Transaction,
    TransactionType,
    Withdrawal,
    WithdrawalStatus,
)
from src.core.config import settings


class FinanceService:
    """Gerencia operações financeiras, saldo e extratos dos usuários."""

    @staticmethod
    def calculate_fees_from_total(amount_gross: float) -> float:
        """
        Calcula taxas de saque baseadas no valor bruto.

        Aplica taxa percentual (plataforma + lucro) ou mínimo fixo, o que for maior.

        Args:
            amount_gross: Valor bruto a ser retirado

        Returns:
            Valor total das taxas
        """
        pct_total = settings.FEE_OUT_PLATFORM + settings.FEE_OUT_PROFIT
        fee_pct = amount_gross * pct_total
        final_fee = max(fee_pct, settings.FEE_OUT_MIN_FIXED)

        return round(final_fee, 2)

    @staticmethod
    async def get_balance(user_id: int) -> float:
        """Retorna o saldo atual do usuário."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(func.sum(Transaction.amount)).filter(
                    Transaction.user_id == user_id
                )
            )
            balance = result.scalar()
            return round(balance, 2) if balance else 0.00

    @staticmethod
    async def get_extract(user_id: int, limit: int = 15):
        """
        Retorna o extrato de transações do usuário.

        Args:
            user_id: ID do usuário
            limit: Número máximo de transações a retornar
        """
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
    async def request_withdrawal(
        user_id: int, amount_gross: float, pix_key: str, pix_type: str = "CPF"
    ):
        """
        Processa solicitação de saque unificando taxas em uma única transação.

        Args:
            user_id: ID do usuário
            amount_gross: Valor bruto a ser retirado
            pix_key: Chave PIX para recebimento
            pix_type: Tipo da chave PIX

        Returns:
            Objeto Withdrawal criado

        Raises:
            ValueError: Se valor menor que mínimo, saldo insuficiente ou não cobrir taxas
        """
        # Validação de valor mínimo
        if amount_gross < settings.MIN_WITHDRAWAL:
            raise ValueError(
                f"O valor mínimo para movimentação é R$ {settings.MIN_WITHDRAWAL:.2f}"
            )

        # Verificação de saldo
        balance = await FinanceService.get_balance(user_id)
        if balance < amount_gross:
            raise ValueError(
                f"Saldo insuficiente. Você tem R$ {balance:.2f} e tentou retirar R$ {amount_gross:.2f}"
            )

        # Cálculo de taxas e valor líquido
        fees = FinanceService.calculate_fees_from_total(amount_gross)
        net_to_receive = amount_gross - fees

        if net_to_receive <= 0:
            raise ValueError("O valor informado não cobre as taxas mínimas de saque.")

        async with AsyncSessionLocal() as session:
            # Registro do saque (controle administrativo)
            withdrawal = Withdrawal(
                user_id=user_id,
                amount_requested=net_to_receive,
                fee_total=fees,
                amount_final=amount_gross,
                pix_key=pix_key,
                pix_type=pix_type,
                status=WithdrawalStatus.PENDING,
            )
            session.add(withdrawal)

            # Débito no saldo (extrato do usuário)
            # Unifica em uma transação com valor total, informando líquido na descrição
            t_main = Transaction(
                user_id=user_id,
                type=TransactionType.WITHDRAWAL,
                description=f"Saque Pix (Liq: R$ {net_to_receive:.2f})",
                amount=-amount_gross,
            )
            session.add(t_main)

            await session.commit()
            return withdrawal

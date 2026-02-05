class TextUtils:
    """Utilitários para formatação de texto e valores."""

    @staticmethod
    def currency(value: float) -> str:
        """
        Formata valor numérico para moeda brasileira.

        Args:
            value: Valor a ser formatado

        Returns:
            String no formato "R$ 1.000,00"
        """
        try:
            formatted = f"{float(value):,.2f}"
            return (
                f"R$ {formatted.replace(',', 'X').replace('.', ',').replace('X', '.')}"
            )
        except (ValueError, TypeError):
            return "R$ 0,00"

    @staticmethod
    def duration(days: int) -> str:
        """
        Formata duração em dias.

        Args:
            days: Número de dias

        Returns:
            String formatada (ex: "30 dias" ou "♾️ Vitalício")
        """
        if not days:
            return "Indefinido"

        if int(days) >= 36000:
            return "♾️ Vitalício"

        if int(days) == 1:
            return "1 dia"

        return f"{days} dias"

    @staticmethod
    def pad_message(text: str) -> str:
        """
        Adiciona padding invisível ao final da mensagem para forçar
        largura mínima do balão no Telegram.

        Args:
            text: Texto original

        Returns:
            Texto com padding invisível
        """
        invisible_padding = "⠀" * 30  # U+2800 (braille vazio)
        return f"{text}\n{invisible_padding}"

    @staticmethod
    def bool_to_emoji(value: bool) -> str:
        """Converte booleano em emoji visual."""
        return "✅" if value else "❌"

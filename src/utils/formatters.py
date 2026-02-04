class TextUtils:
    @staticmethod
    def currency(value: float) -> str:
        """Formata float para Moeda BRL (R$ 1.000,00) sem depender de locale do sistema."""
        try:
            formatted = f"{float(value):,.2f}"
            return f"R$ {formatted.replace(',', 'X').replace('.', ',').replace('X', '.')}"
        except (ValueError, TypeError):
            return "R$ 0,00"

    @staticmethod
    def duration(days: int) -> str:
        """Formata dias. Se for absurdo (> 36000), vira Vitalício."""
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
        Adiciona uma linha invisível larga ao final do texto para forçar
        o balão do Telegram a ficar largo e não quebrar o layout.
        """
        # U+2800 é um caractere braille vazio que ocupa espaço visual mas é "invisível"
        invisible_padding = "⠀" * 30  
        return f"{text}\n{invisible_padding}"

    @staticmethod
    def bool_to_emoji(value: bool) -> str:
        return "✅" if value else "❌"
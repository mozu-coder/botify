from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Telegram
    TELEGRAM_BOT_TOKEN: str
    ADMIN_USER_IDS: str
    WEBHOOK_URL: str
    PORT: int = 8080

    # Database
    DATABASE_URL: str

    # GGPIX API
    GGPIX_API_KEY: str
    GGPIX_WEBHOOK_SECRET: str
    GGPIX_BASE_URL: str = "https://ggpixapi.com/api/v1"

    ADMIN_WITHDRAWAL_GROUP_ID: int

    # Taxas e Limites (Business Logic)
    MIN_WITHDRAWAL: float = 50.00
    
    # Taxas de Entrada (Venda)
    FEE_IN_PLATFORM: float = 0.03 # 3%
    FEE_IN_PROFIT: float = 0.05   # 5% (Minha margem)
    FEE_IN_MIN_FIXED: float = 0.77

    # Taxas de Saída (Saque)
    FEE_OUT_PLATFORM: float = 0.02 # 2%
    FEE_OUT_PROFIT: float = 0.05   # 5% (Minha margem)
    FEE_OUT_MIN_FIXED: float = 0.77

    class Config:
        env_file = ".env"

    @property
    def async_database_url(self) -> str:
        """Garante que a URL use o driver asyncpg para o SQLAlchemy"""
        url = self.DATABASE_URL
        if url and "postgresql://" in url and "postgresql+asyncpg" not in url:
            return url.replace("postgresql://", "postgresql+asyncpg://")
        return url

settings = Settings()
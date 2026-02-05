from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configurações centralizadas da aplicação."""

    TELEGRAM_BOT_TOKEN: str
    ADMIN_USER_IDS: str
    WEBHOOK_URL: str
    PORT: int = 8080

    DATABASE_URL: str

    GGPIX_API_KEY: str
    GGPIX_WEBHOOK_SECRET: str
    GGPIX_BASE_URL: str = "https://ggpixapi.com/api/v1"

    ADMIN_WITHDRAWAL_GROUP_ID: int

    MIN_WITHDRAWAL: float = 50.00

    FEE_IN_PLATFORM: float = 0.03
    FEE_IN_PROFIT: float = 0.05
    FEE_IN_MIN_FIXED: float = 0.77

    FEE_OUT_PLATFORM: float = 0.02
    FEE_OUT_PROFIT: float = 0.05
    FEE_OUT_MIN_FIXED: float = 0.77

    class Config:
        env_file = ".env"

    @property
    def async_database_url(self) -> str:
        """Converte a URL do banco para o driver asyncpg do SQLAlchemy."""
        url = self.DATABASE_URL
        if url and "postgresql://" in url and "postgresql+asyncpg" not in url:
            return url.replace("postgresql://", "postgresql+asyncpg://")
        return url


settings = Settings()

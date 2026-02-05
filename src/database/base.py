from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from src.core.config import settings


engine = create_async_engine(settings.async_database_url, echo=False)

AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    """Classe base para modelos SQLAlchemy."""

    pass


async def get_db():
    """Fornece uma sessão de banco de dados assíncrona."""
    async with AsyncSessionLocal() as session:
        yield session

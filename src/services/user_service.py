from sqlalchemy.future import select
from src.database.base import AsyncSessionLocal
from src.database.models import User
from src.core.config import settings


class UserService:
    """Gerencia operações relacionadas aos usuários da plataforma."""

    @staticmethod
    async def register_user(tg_user):
        """
        Registra ou atualiza dados do usuário no banco de dados.

        Args:
            tg_user: Objeto User do Telegram

        Returns:
            Objeto User do banco de dados
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User).filter(User.id == tg_user.id))
            user = result.scalars().first()

            is_admin = str(tg_user.id) in settings.ADMIN_USER_IDS

            if not user:
                user = User(
                    id=tg_user.id,
                    full_name=tg_user.full_name,
                    username=tg_user.username,
                    is_admin=is_admin,
                )
                session.add(user)
            else:
                user.full_name = tg_user.full_name
                user.username = tg_user.username
                user.is_admin = is_admin

            await session.commit()
            return user

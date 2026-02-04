from sqlalchemy.future import select
from src.database.base import AsyncSessionLocal
from src.database.models import User
from src.core.config import settings

class UserService:
    @staticmethod
    async def register_user(tg_user):
        """Registra ou atualiza o usuário no banco."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User).filter(User.id == tg_user.id))
            user = result.scalars().first()
            
            # Verifica se é admin baseado no .env
            # O .env retorna string "[123, 456]", precisamos tratar isso depois, 
            # mas por agora vamos simplificar comparando string
            is_admin = str(tg_user.id) in settings.ADMIN_USER_IDS

            if not user:
                user = User(
                    id=tg_user.id,
                    full_name=tg_user.full_name,
                    username=tg_user.username,
                    is_admin=is_admin
                )
                session.add(user)
            else:
                # Atualiza dados caso o user tenha mudado nome
                user.full_name = tg_user.full_name
                user.username = tg_user.username
                user.is_admin = is_admin # Garante update de permissão
            
            await session.commit()
            return user
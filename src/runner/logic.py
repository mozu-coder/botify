from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, Bot as TgBot
from sqlalchemy.future import select
from src.database.base import AsyncSessionLocal
from src.database.models import Bot, Plan, Subscriber, Transaction, TransactionType, Lead 
from src.services.payment_service import PaymentService
from src.utils.formatters import TextUtils
import uuid
from datetime import datetime

class RunnerLogic:
    
    @staticmethod
    async def process_start(update: Update, bot: TgBot, db_bot: Bot):
        user = update.effective_user
        chat_id = update.effective_chat.id
        
        async with AsyncSessionLocal() as session:
            # 1. Garante que o Subscriber existe
            result = await session.execute(select(Subscriber).filter(Subscriber.id == user.id))
            subscriber = result.scalars().first()
            if not subscriber:
                subscriber = Subscriber(id=user.id, name=user.full_name) # Removi username pra simplificar se der erro
                session.add(subscriber)
                await session.flush() # Salva pra ter o ID disponível

            # 2. Registra/Atualiza o Lead (NOVO)
            # Verifica se esse user já é lead deste bot
            lead_res = await session.execute(
                select(Lead).filter(Lead.user_id == user.id, Lead.bot_id == db_bot.id)
            )
            lead = lead_res.scalars().first()
            
            if not lead:
                lead = Lead(user_id=user.id, bot_id=db_bot.id)
                session.add(lead)
                # Se já existe, não faz nada (mantém a data de criação original pra saber quão "velho" é o lead)
            
            await session.commit()
        
        # 2. Envia Boas-vindas
        if db_bot.welcome_media_id:
            caption = db_bot.welcome_message or ""
            try:
                if db_bot.welcome_media_type == 'photo':
                    await bot.send_photo(chat_id=chat_id, photo=db_bot.welcome_media_id, caption=caption, parse_mode="HTML")
                elif db_bot.welcome_media_type == 'video':
                    await bot.send_video(chat_id=chat_id, video=db_bot.welcome_media_id, caption=caption, parse_mode="HTML")
            except Exception:
                await bot.send_message(chat_id=chat_id, text=caption, parse_mode="HTML")
        else:
            if db_bot.welcome_message:
                await bot.send_message(chat_id=chat_id, text=db_bot.welcome_message, parse_mode="HTML")

        # 3. Mostra Planos
        await RunnerLogic.show_plans(update, bot, db_bot)

    @staticmethod
    async def show_plans(update: Update, bot: TgBot, db_bot: Bot):
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Plan).filter(Plan.bot_id == db_bot.id, Plan.is_active == True))
            plans = result.scalars().all()
        
        if not plans:
            await bot.send_message(chat_id=update.effective_chat.id, text="<i>Sem planos disponíveis no momento.</i>", parse_mode="HTML")
            return

        keyboard = []
        for plan in plans:
            btn_text = f"{plan.name} - {TextUtils.currency(plan.price)}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"buy_plan_{plan.id}")])
        
        await bot.send_message(
            chat_id=update.effective_chat.id,
            text="👇 <b>Escolha seu plano de acesso:</b>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

    @staticmethod
    async def process_purchase(update: Update, bot: TgBot, db_bot: Bot, callback_data: str):
        """
        Gera o Pix para o plano selecionado.
        Cria a transação com VALOR ZERO para não afetar o saldo até pagar.
        """
        plan_id = int(callback_data.split("_")[2])
        user = update.effective_user
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Plan).filter(Plan.id == plan_id))
            plan = result.scalars().first()
            
            if not plan:
                await bot.answer_callback_query(update.callback_query.id, "Plano indisponível.")
                return

            external_id = f"{uuid.uuid4()}|{plan.id}|{user.id}"
            
            await bot.answer_callback_query(update.callback_query.id, "Gerando Pix...")
            await bot.send_message(update.effective_chat.id, "⏳ <b>Gerando seu Pix...</b>", parse_mode="HTML")
            
            charge = await PaymentService.create_pix_charge(
                amount=plan.price,
                description=f"Plano {plan.name}",
                payer_name=user.full_name,
                external_id=external_id
            )
            
            if not charge:
                await bot.send_message(update.effective_chat.id, "❌ Erro no pagamento. Tente novamente.")
                return
            
            # --- CORREÇÃO AQUI ---
            transaction = Transaction(
                user_id=db_bot.owner_id,
                bot_id=db_bot.id,
                external_id=external_id,
                type=TransactionType.SALE,
                description=f"(Pendente) {plan.name} - @{user.username or user.first_name}",
                amount=0.0 # <--- COMEÇA COM ZERO PRA NÃO SOMAR NO SALDO
            )
            session.add(transaction)
            await session.commit()
            
            pix_code = charge['pixCopyPaste']
            
            msg = (
                f"✅ <b>Pix Gerado!</b>\n\n"
                f"💠 <b>Plano:</b> {plan.name}\n"
                f"💲 <b>Valor:</b> {TextUtils.currency(plan.price)}\n\n"
                "Copie o código abaixo e pague no seu banco:"
            )
            
            await bot.send_message(update.effective_chat.id, msg, parse_mode="HTML")
            await bot.send_message(update.effective_chat.id, f"`{pix_code}`", parse_mode="MarkdownV2")
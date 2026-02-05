import uvicorn
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.runner.scheduler import check_abandoned_carts
from src.runner.router import runner_router
from src.core.config import settings
from src.database.base import engine, Base
from src.bot.handlers.start import start_command
from src.bot.handlers.creation_wizard import creation_handler
from src.bot.handlers.plan_wizard import plan_wizard_handler
from src.bot.handlers.plan_editor import plan_edit_conversation, plan_action_handlers
from src.bot.handlers.bot_editor import change_group_handler, bot_action_handlers
from src.bot.handlers.settings_wizard import settings_wizard_handler
from src.bot.handlers.followup_wizard import followup_wizard_handler
from src.bot.handlers.dashboard import dashboard_handlers
from src.bot.handlers.wallet import wallet_handlers
from src.bot.handlers.support import support_handler
from src.bot.handlers.admin_withdrawal import admin_handlers


scheduler = AsyncIOScheduler()


async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida da aplicação FastAPI.
    Inicializa o banco de dados, configura handlers do Telegram e define
    o método de atualização (Webhook para produção ou Polling para desenvolvimento).
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    bot_app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

    bot_app.add_handler(creation_handler)
    bot_app.add_handler(plan_wizard_handler)
    bot_app.add_handler(plan_edit_conversation)
    bot_app.add_handler(change_group_handler)
    bot_app.add_handler(settings_wizard_handler)
    bot_app.add_handler(followup_wizard_handler)

    for handler in wallet_handlers:
        bot_app.add_handler(handler)

    for handler in plan_action_handlers:
        bot_app.add_handler(handler)

    for handler in bot_action_handlers:
        bot_app.add_handler(handler)

    for handler in dashboard_handlers:
        bot_app.add_handler(handler)

    for handler in admin_handlers:
        bot_app.add_handler(handler)

    bot_app.add_handler(support_handler)
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(CallbackQueryHandler(start_command, pattern="^back_to_main$"))

    await bot_app.initialize()

    if "localhost" in settings.WEBHOOK_URL or "127.0.0.1" in settings.WEBHOOK_URL:
        await bot_app.bot.delete_webhook()
        await bot_app.start()
        await bot_app.updater.start_polling()
        print("🔧 Modo DEV: Execução via Polling")
    else:
        webhook_url = f"{settings.WEBHOOK_URL}/telegram-webhook"
        await bot_app.bot.set_webhook(url=webhook_url)
        await bot_app.start()
        print(f"🚀 Modo PROD: Webhook definido em {webhook_url}")

    app.state.bot_app = bot_app

    yield

    if bot_app.updater.running:
        await bot_app.updater.stop()
    await bot_app.stop()
    await bot_app.shutdown()


app = FastAPI(lifespan=lifespan)
app.include_router(runner_router)


@app.get("/")
async def health_check():
    """Verifica o status da API."""
    return {"status": "ok"}


@app.post("/telegram-webhook")
async def telegram_webhook(request: Request):
    """Recebe e processa atualizações do Telegram via Webhook."""
    bot_app = request.app.state.bot_app
    update_data = await request.json()
    update = Update.de_json(update_data, bot_app.bot)
    await bot_app.process_update(update)
    return {"ok": True}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=True)

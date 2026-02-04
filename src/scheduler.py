import asyncio
from src.services.jobs_service import JobsService

async def start_scheduler():
    while True:
        try:
            await JobsService.check_expired_subscriptions()
            await JobsService.send_remarketing() # <--- AQUI
        except Exception as e:
            print(f"Erro Scheduler: {e}")
        await asyncio.sleep(60)
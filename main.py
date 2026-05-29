"""
Crypto Paper Trading Bot — entry point.

Usage:
    python main.py              # run bot (MODE from .env)
    python main.py --web        # run bot + web dashboard at http://localhost:8000
    python main.py --dashboard  # live Rich terminal dashboard
    python main.py --migrate    # initialize database schema
"""
import argparse
import asyncio
import logging
import sys

from config.settings import settings

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


def _validate_mode():
    if settings.MODE not in ("DRY_RUN", "PAPER_TRADING"):
        logger.error("Invalid MODE: %s — must be DRY_RUN or PAPER_TRADING", settings.MODE)
        sys.exit(1)


async def _run_bot():
    from scheduler.runner import run_bot
    await run_bot()


async def _run_dashboard():
    from cli.dashboard import run_dashboard
    await run_dashboard()


async def _run_migrate():
    from db.database import init_db
    await init_db()
    print("Database initialized.")


async def _run_web(port: int = 8000):
    import uvicorn
    from scheduler.runner import BotRunner
    from db.database import init_db
    from api.app import app

    await init_db()
    runner = BotRunner()

    logger.info(
        "Crypto Bot started | mode=%s | interval=%ds | balance=%.2f | pairs=%s",
        settings.MODE, settings.CYCLE_INTERVAL_SECONDS,
        settings.PAPER_BALANCE, settings.TRADING_PAIRS,
    )
    logger.info("Web dashboard → http://localhost:%d", port)

    async def bot_loop():
        while True:
            try:
                await runner.run_cycle()
            except Exception as e:
                logger.exception("Bot loop error: %s", e)
            await asyncio.sleep(settings.CYCLE_INTERVAL_SECONDS)

    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="warning")
    server = uvicorn.Server(config)

    try:
        await asyncio.gather(bot_loop(), server.serve())
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        logger.info("Bot stopped.")


def main():
    parser = argparse.ArgumentParser(description="Crypto Paper Trading Bot")
    parser.add_argument("--web", action="store_true", help="Run bot + web dashboard at http://localhost:8000")
    parser.add_argument("--port", type=int, default=8000, help="Web server port (default: 8000)")
    parser.add_argument("--dashboard", action="store_true", help="Show live Rich terminal dashboard")
    parser.add_argument("--migrate", action="store_true", help="Initialize database schema")
    args = parser.parse_args()

    _validate_mode()
    logger.info("Starting Crypto Bot | MODE=%s | PAIRS=%s", settings.MODE, settings.TRADING_PAIRS)

    if args.web:
        asyncio.run(_run_web(port=args.port))
    elif args.dashboard:
        asyncio.run(_run_dashboard())
    elif args.migrate:
        asyncio.run(_run_migrate())
    else:
        asyncio.run(_run_bot())


if __name__ == "__main__":
    main()

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session

from app.db import engine
from app.services.reports import low_stock_products

logger = logging.getLogger("monitou.low_stock_alerts")


def send_low_stock_digest() -> None:
    """Run the shared low-stock query and push a digest an admin will see
    without opening the app.

    Delivery channel (email vs. Slack/WhatsApp webhook) and frequency
    (daily vs. real-time) are open decisions — see CLAUDE.md Section 9.
    For now this logs the digest; swap the body for an email/webhook call
    once a channel is chosen.
    """
    with Session(engine) as session:
        alerts = low_stock_products(session)

    if not alerts:
        logger.info("low-stock digest: nothing below threshold")
        return

    lines = [f"{a.sku} {a.name}: {a.balance}/{a.reorder_threshold} (deficit {a.deficit})" for a in alerts]
    logger.warning("low-stock digest: %d product(s) below threshold\n%s", len(alerts), "\n".join(lines))


def start_scheduler(*, hour: int = 8, minute: int = 0) -> BackgroundScheduler:
    """Daily low-stock digest at `hour:minute` server time (default 08:00)."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(send_low_stock_digest, "cron", hour=hour, minute=minute, id="low_stock_digest")
    scheduler.start()
    return scheduler

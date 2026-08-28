import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session, select

from app.db import engine
from app.models.tenant import Tenant, TenantStatus
from app.services.reports import low_stock_products

logger = logging.getLogger("monitou.low_stock_alerts")


def send_low_stock_digest() -> None:
    """Run the shared low-stock query per tenant and push a digest an admin
    will see without opening the app.

    One tenant-scoped pass per tenant — never a single cross-tenant query
    with tenant info stitched on afterward (see CLAUDE.md Section 11.9.5).

    Delivery channel (email vs. Slack/WhatsApp webhook) and frequency
    (daily vs. real-time) are open decisions — see CLAUDE.md Section 9.
    For now this logs the digest; swap the body for an email/webhook call
    once a channel is chosen.
    """
    with Session(engine) as session:
        tenants = session.exec(select(Tenant).where(Tenant.status == TenantStatus.active)).all()
        for tenant in tenants:
            alerts = low_stock_products(session, tenant_id=tenant.id)
            if not alerts:
                logger.info("low-stock digest [%s]: nothing below threshold", tenant.tenant_code)
                continue
            lines = [f"{a.sku} {a.name}: {a.balance}/{a.reorder_threshold} (deficit {a.deficit})" for a in alerts]
            logger.warning(
                "low-stock digest [%s]: %d product(s) below threshold\n%s",
                tenant.tenant_code,
                len(alerts),
                "\n".join(lines),
            )


def start_scheduler(*, hour: int = 8, minute: int = 0) -> BackgroundScheduler:
    """Daily low-stock digest at `hour:minute` server time (default 08:00)."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(send_low_stock_digest, "cron", hour=hour, minute=minute, id="low_stock_digest")
    scheduler.start()
    return scheduler

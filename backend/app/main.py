from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.jobs.low_stock_alerts import start_scheduler
from app.routers import auth, barcodes, products, reports, sales, stock, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = start_scheduler()
    yield
    scheduler.shutdown()


app = FastAPI(title="Monitou Spare Parts POS & Inventory API", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(products.router)
app.include_router(barcodes.router)
app.include_router(stock.router)
app.include_router(sales.router)
app.include_router(reports.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

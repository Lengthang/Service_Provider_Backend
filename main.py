from fastapi import FastAPI
from api.routes import auth, providers, categories, services, admin, customer, bookings, payments, promo_codes, disputes, reviews, portfolio
from db.database import AsyncSessionLocal
from services.escrow_auto_release import auto_release_expired_escrows
import asyncio
from contextlib import asynccontextmanager

async def escrow_release_loop():
    while True:
        try:
            async with AsyncSessionLocal() as db:
                count = await auto_release_expired_escrows(db)
                if count:
                    print(f"[escrow] Auto-released {count} stale escrow(s)")
        except Exception as e:
            print(f"[escrow] Error in auto-release: {e}")
        await asyncio.sleep(900)  # 15 minutes

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(escrow_release_loop())
    yield
    task.cancel()

app = FastAPI(
    title="FixIt API",
    description="Backend for the FixIt home services platform",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(customer.router)
app.include_router(providers.router)
app.include_router(bookings.router)
app.include_router(categories.router)
app.include_router(services.router)
app.include_router(payments.router)
app.include_router(promo_codes.router)
app.include_router(disputes.router)
app.include_router(reviews.router)
app.include_router(portfolio.router)


@app.get("/")
def root():
    return {"message": "Welcome to FixIt API"}


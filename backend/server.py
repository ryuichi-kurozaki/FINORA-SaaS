from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import os  # noqa: E402
import logging  # noqa: E402
from fastapi import FastAPI, Request  # noqa: E402
from starlette.middleware.cors import CORSMiddleware  # noqa: E402

from core import mongo, db  # noqa: E402
import auth_routes  # noqa: E402
import crud  # noqa: E402
import routes_analytics  # noqa: E402
import io_routes  # noqa: E402
import public_routes  # noqa: E402
import features  # noqa: E402
import billing  # noqa: E402
import stripe_payments  # noqa: E402
import tenancy  # noqa: E402
import econtract  # noqa: E402
import renewal  # noqa: E402
import payouts  # noqa: E402
import asyncio  # noqa: E402
from seed import seed  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
app = FastAPI(title="FINORA API", version="1.0.0")


@app.get("/api/")
async def root():
    return {"service": "FINORA", "status": "ok"}


for r in (auth_routes.router, routes_analytics.router, io_routes.router, public_routes.router, features.router, stripe_payments.router, payouts.router, billing.router, tenancy.router, renewal.router, econtract.router, crud.router):
    app.include_router(r)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if request.url.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ["CORS_ORIGINS"].split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await seed()
    await db.accounts.update_many({"account_number": {"$exists": True}}, {"$unset": {"account_number": ""}})
    await db.tenants.update_many({"payout_bank": {"$exists": True}}, {"$unset": {"payout_bank": ""}})
    app.state.renewal_task = asyncio.create_task(renewal.loop())


@app.on_event("shutdown")
async def shutdown():
    mongo.close()

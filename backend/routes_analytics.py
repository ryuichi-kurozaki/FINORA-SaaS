from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from core import db, new_id, now_iso, clean, current, admin_only, audit, scope
from calc import positions, data_health, goals_progress
from analytics import (load, summarize, cashflow, build_breakdowns, record_snapshots, trend, metrics, simulate, risk,
                       get_fx, DEFAULT_FX)
import ai_engine

router = APIRouter(prefix="/api")


async def context(user, client_id=None):
    data = await load(user, client_id)
    await record_snapshots(user, data)
    summ = summarize(data["assets"], data["liabilities"])
    cf = cashflow(data["cashflows"])
    series = await trend(user, client_id)
    meetings = sorted([c["date"] for c in data["consulting"] if c.get("kind") == "meeting" and c.get("date")])
    rk = risk(summ, data["assets"], data["liabilities"], cf)
    docs = [clean(d) for d in await db.documents.find(await scope(user, client_id)).to_list(2000)]
    pos = positions(data["transactions"], data["assets"])
    return {"data": data, "summary": summ, "cashflow": cf, "trend": series, "metrics": metrics(series),
            "risk": rk, "breakdowns": build_breakdowns(data), "positions": pos,
            "health": data_health(data, data["transactions"], docs, pos),
            "goals": goals_progress(data["goals"], summ, cf, data["liabilities"], rk["items"]),
            "last_meeting": meetings[-1] if meetings else None}


@router.get("/analytics/dashboard")
async def dashboard(client_id: Optional[str] = None, lang: str = "ja", user=Depends(current)):
    ctx = await context(user, client_id)
    d = ctx["data"]
    return {k: ctx[k] for k in ("summary", "cashflow", "trend", "metrics", "risk", "breakdowns", "last_meeting", "health", "goals")} | {
        "projection": simulate(ctx["summary"], ctx["cashflow"], d["liabilities"], {"years": 20}),
        "insights": ai_engine.insights(ctx, lang), "engine": ai_engine.ENGINE,
        "counts": {k: len(d[k]) for k in ("clients", "accounts", "assets", "liabilities", "cashflows", "consulting", "tasks", "transactions", "goals")},
    }


@router.get("/positions")
async def get_positions(client_id: Optional[str] = None, user=Depends(current)):
    data = await load(user, client_id)
    return positions(data["transactions"], data["assets"])


@router.get("/data-health")
async def get_health(client_id: Optional[str] = None, user=Depends(current)):
    return (await context(user, client_id))["health"]


@router.get("/goals/progress")
async def get_goals(client_id: Optional[str] = None, user=Depends(current)):
    return (await context(user, client_id))["goals"]


class SimIn(BaseModel):
    client_id: Optional[str] = None
    params: dict = {}


@router.post("/simulation")
async def simulation(body: SimIn, user=Depends(current)):
    data = await load(user, body.client_id)
    summ = summarize(data["assets"], data["liabilities"])
    return simulate(summ, cashflow(data["cashflows"]), data["liabilities"], body.params)


class AskIn(BaseModel):
    client_id: Optional[str] = None
    question: str
    lang: str = "ja"


@router.post("/ai/ask")
async def ai_ask(body: AskIn, request: Request, user=Depends(current)):
    ctx = await context(user, body.client_id)
    res = ai_engine.ask(ctx, body.lang, body.question[:1000])
    await db.ai_logs.insert_one({"id": new_id(), "tenant_id": user["tenant_id"], "user_id": user["id"],
                                 "client_id": body.client_id, "question": body.question[:1000], "intent": res["intent"],
                                 "engine": res["engine"], "at": now_iso()})
    return res


@router.get("/ai/report")
async def ai_report(client_id: Optional[str] = None, lang: str = "ja", user=Depends(current)):
    ctx = await context(user, client_id)
    return {"sections": ai_engine.ans_report(ctx, lang), "engine": ai_engine.ENGINE}


@router.get("/tasks/alerts")
async def task_alerts(user=Depends(current)):
    from crud import list_items
    limit = (datetime.now() + timedelta(days=7)).date().isoformat()
    tasks = [t for t in await list_items(user, "tasks") if t.get("status") != "done" and t.get("due_date") and t["due_date"] <= limit]
    today = datetime.now().date().isoformat()
    for t in tasks:
        t["overdue"] = t["due_date"] < today
    return sorted(tasks, key=lambda t: t["due_date"])


@router.get("/settings")
async def get_settings(user=Depends(current)):
    s = await db.settings.find_one({"tenant_id": user["tenant_id"]}) or {}
    return {"fx": await get_fx(user["tenant_id"]), "base_currency": s.get("base_currency", "JPY"),
            "fx_updated_at": s.get("fx_updated_at"), "ai_engine": ai_engine.ENGINE}


class SettingsIn(BaseModel):
    fx: dict


@router.put("/settings")
async def put_settings(body: SettingsIn, request: Request, user=Depends(admin_only)):
    fx = {k.upper()[:5]: float(v) for k, v in body.fx.items() if float(v) > 0}
    before = await get_fx(user["tenant_id"])
    await db.settings.update_one({"tenant_id": user["tenant_id"]}, {"$set": {"fx": fx, "fx_updated_at": now_iso()}}, upsert=True)
    await audit(user, "update", "settings", user["tenant_id"], before={"fx": before}, after={"fx": fx}, request=request)
    return {"fx": {**DEFAULT_FX, **fx}}

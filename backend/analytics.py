import math
import statistics

from core import db, now, new_id, scope

DEFAULT_FX = {"JPY": 1, "USD": 155, "EUR": 168, "GBP": 197, "BRL": 28, "CNY": 21.5, "AUD": 102, "HKD": 19.8, "SGD": 115, "CHF": 176}
INVEST = {"jp_stock", "foreign_stock", "etf", "fund", "bond", "fx", "crypto", "gold", "precious_metal", "unlisted", "real_estate"}
EQUITY = {"jp_stock", "foreign_stock", "etf", "fund", "unlisted"}
LIQUID = {"cash", "deposit"}
FREQ = {"monthly": 1, "quarterly": 1 / 3, "annual": 1 / 12, "once": 1 / 12}


async def get_fx(tenant_id):
    s = await db.settings.find_one({"tenant_id": tenant_id})
    return {**DEFAULT_FX, **((s or {}).get("fx") or {})}


def enrich(a, fx):
    r = fx.get(a.get("currency") or "JPY", 1)
    qty, ap, cp = a.get("quantity") or 0, a.get("acquisition_price") or 0, a.get("current_price") or 0
    unit = a.get("price_unit") or 1
    a["acquisition_total"], a["current_value"] = qty * ap / unit, qty * cp / unit
    a["unrealized_pl"] = a["current_value"] - a["acquisition_total"]
    a["unrealized_pct"] = (a["unrealized_pl"] / a["acquisition_total"] * 100) if a["acquisition_total"] else 0
    a["fx_rate"] = r
    a["value_jpy"], a["cost_jpy"], a["pl_jpy"] = a["current_value"] * r, a["acquisition_total"] * r, a["unrealized_pl"] * r
    a["realized_jpy"] = (a.get("realized_pl") or 0) * r
    a["dividend_jpy"] = (a.get("dividend_annual") or 0) * r
    a["interest_jpy"] = (a.get("interest_annual") or 0) * r
    return a


async def load(user, client_id=None):
    from crud import list_items
    data = {e: await list_items(user, e, client_id) for e in ("accounts", "assets", "liabilities", "cashflows", "consulting", "tasks", "transactions", "goals")}
    data["clients"] = [c for c in await list_items(user, "clients") if not client_id or c["id"] == client_id]
    return data


def summarize(assets, liabs):
    ta = sum(a["value_jpy"] for a in assets)
    inv = [a for a in assets if a.get("asset_class") in INVEST]
    principal, invested = sum(a["cost_jpy"] for a in inv), sum(a["value_jpy"] for a in inv)
    realized = sum(a["realized_jpy"] for a in assets)
    div, intr = sum(a["dividend_jpy"] for a in assets), sum(a["interest_jpy"] for a in assets)
    tl = sum(l.get("balance") or 0 for l in liabs)
    unreal = invested - principal
    cv = {}
    for a in assets:
        cv[a.get("asset_class") or "other"] = cv.get(a.get("asset_class") or "other", 0) + a["value_jpy"]
    return {
        "total_assets": ta, "total_liabilities": tl, "net_worth": ta - tl, "principal": principal,
        "invested_value": invested, "unrealized_pl": unreal, "unrealized_pct": unreal / principal * 100 if principal else 0,
        "realized_pl": realized, "dividends": div, "interest": intr, "annual_investment_income": div + intr + realized,
        "total_return_pct": (unreal + realized + div + intr) / principal * 100 if principal else 0,
        "income_yield_pct": (div + intr) / invested * 100 if invested else 0,
        "dividend_yield_pct": div / invested * 100 if invested else 0,
        "liquid": sum(a["value_jpy"] for a in assets if a.get("asset_class") in LIQUID),
        "foreign_value": sum(a["value_jpy"] for a in assets if (a.get("currency") or "JPY") != "JPY"),
        "class_values": cv, "asset_count": len(assets), "liability_count": len(liabs),
    }


def breakdown(items, key, val="value_jpy"):
    agg = {}
    for i in items:
        k = (key(i) if callable(key) else i.get(key)) or "other"
        agg[k] = agg.get(k, 0) + (i.get(val) or 0)
    tot = sum(agg.values()) or 1
    return sorted([{"key": k, "value": round(v), "pct": round(v / tot * 100, 1)} for k, v in agg.items() if v], key=lambda x: -x["value"])


def build_breakdowns(data):
    assets = data["assets"]
    inst = {a["id"]: a.get("institution") for a in data["accounts"]}
    inv = [a for a in assets if a.get("asset_class") in INVEST]
    return {
        "asset_class": breakdown(assets, "asset_class"),
        "country": breakdown(assets, lambda a: a.get("country") or "JP"),
        "currency": breakdown(assets, lambda a: a.get("currency") or "JPY"),
        "sector": breakdown(inv, "sector"),
        "institution": breakdown(assets, lambda a: inst.get(a.get("account_id")) or "unassigned"),
        "owner_type": breakdown(assets, lambda a: a.get("owner_type") or "individual"),
        "liability_type": breakdown(data["liabilities"], "liability_type", "balance"),
    }


def cashflow(cfs):
    inc = exp = inv = 0
    by = {"income": {}, "expense": {}}
    for c in cfs:
        m = (c.get("amount") or 0) * FREQ.get(c.get("frequency") or "monthly", 1)
        d = "income" if c.get("direction") == "income" else "expense"
        cat = c.get("category") or "other"
        by[d][cat] = by[d].get(cat, 0) + m
        if d == "income":
            inc += m
        else:
            exp += m
            inv += m if cat == "investment" else 0
    free = inc - (exp - inv)
    fmt = lambda dct: sorted([{"key": k, "value": round(v)} for k, v in dct.items()], key=lambda x: -x["value"])
    return {"income_m": inc, "expense_m": exp, "cf_m": inc - exp, "cf_y": (inc - exp) * 12, "free_m": free,
            "investable_m": max(0, free - inc * 0.1), "investment_m": inv, "income_by": fmt(by["income"]),
            "expense_by": fmt(by["expense"])}


async def record_snapshots(user, data):
    month = now().strftime("%Y-%m")
    for c in data["clients"]:
        s = summarize([a for a in data["assets"] if a.get("client_id") == c["id"]],
                      [l for l in data["liabilities"] if l.get("client_id") == c["id"]])
        await db.snapshots.update_one(
            {"tenant_id": user["tenant_id"], "client_id": c["id"], "date": month},
            {"$set": {k: s[k] for k in ("total_assets", "total_liabilities", "net_worth", "invested_value", "principal")},
             "$setOnInsert": {"id": new_id()}}, upsert=True)
        await db.daily_snapshots.update_one(
            {"tenant_id": user["tenant_id"], "client_id": c["id"], "date": now().strftime("%Y-%m-%d")},
            {"$set": {k: round(s[k]) for k in ("total_assets", "total_liabilities", "net_worth")}}, upsert=True)


async def trend(user, client_id=None):
    snaps = await db.snapshots.find(await scope(user, client_id), {"_id": 0}).to_list(50000)
    keys = ("total_assets", "total_liabilities", "net_worth", "invested_value", "principal")
    agg = {}
    for s in snaps:
        d = agg.setdefault(s["date"], {"date": s["date"], **{k: 0 for k in keys}})
        for k in keys:
            d[k] += s.get(k) or 0
    series = sorted(agg.values(), key=lambda x: x["date"])
    bm = {b["date"]: b["value"] for b in await db.benchmarks.find({"tenant_id": user["tenant_id"]}).to_list(1000)}
    last = 100
    for s in series:
        last = bm.get(s["date"], last)
        s["benchmark"] = last
    if series:
        base_v, base_b = series[0]["invested_value"] or 1, series[0]["benchmark"] or 100
        for s in series:
            s["benchmark_value"] = round(base_v * s["benchmark"] / base_b)
            for k in keys:
                s[k] = round(s[k])
    return series


def metrics(series):
    v = [s["invested_value"] for s in series if s["invested_value"] > 0]
    if len(v) < 3:
        return {"annual_return_pct": None, "volatility_pct": None, "max_drawdown_pct": None,
                "benchmark_return_pct": None, "excess_return_pct": None, "sharpe": None, "months": len(v)}
    rets = [v[i] / v[i - 1] - 1 for i in range(1, len(v))]
    ann = (v[-1] / v[0]) ** (12 / len(rets)) - 1
    vol = statistics.stdev(rets) * math.sqrt(12)
    peak, mdd = v[0], 0
    for x in v:
        peak = max(peak, x)
        mdd = min(mdd, x / peak - 1)
    b = [s["benchmark"] for s in series]
    bann = (b[-1] / b[0]) ** (12 / (len(b) - 1)) - 1
    return {"annual_return_pct": ann * 100, "volatility_pct": vol * 100, "max_drawdown_pct": mdd * 100,
            "benchmark_return_pct": bann * 100, "excess_return_pct": (ann - bann) * 100,
            "sharpe": (ann - 0.005) / vol if vol else None, "months": len(rets)}


def simulate(summ, cf, liabs, p):
    def g(k, d):
        v = p.get(k)
        return float(v) if v not in (None, "") else float(d)
    years = max(1, min(40, int(g("years", 20))))
    contrib = g("monthly_contribution", round(cf["investable_m"], -3))
    contrib = max(0, contrib + cf["income_m"] * g("income_change", 0) / 100 - cf["expense_m"] * g("expense_change", 0) / 100)
    cv = summ["class_values"]
    equity = sum(cv.get(k, 0) for k in EQUITY)
    shock = (equity * g("equity_shock", 0) + cv.get("real_estate", 0) * g("real_estate_shock", 0)
             + summ["foreign_value"] * g("fx_shock", 0)) / 100
    invest0 = summ["invested_value"] + shock
    other0 = summ["total_assets"] - summ["invested_value"]
    dy = g("dividend_yield", summ["income_yield_pct"]) / 100
    reinvest = bool(p.get("reinvest", True))
    scen = {"bull": g("bull_return", 8), "base": g("base_return", 5), "bear": g("bear_return", 1)}
    rc = g("rate_change", 0)
    debts = [[l.get("balance") or 0, ((l.get("interest_rate") or 0) + (rc if l.get("rate_type") == "variable" else 0)) / 100,
              l.get("monthly_payment") or 0] for l in liabs]
    debt_y = []
    for _ in range(years + 1):
        debt_y.append(sum(d[0] for d in debts))
        for d in debts:
            for _m in range(12):
                d[0] = max(0, d[0] * (1 + d[1] / 12) - d[2]) if d[0] > 0 else 0
    rows = [{"year": y, "debt": round(debt_y[y]), "principal": round(invest0 + other0 + contrib * 12 * y - debt_y[y])}
            for y in range(years + 1)]
    for name, r in scen.items():
        v, cash = invest0, other0
        rows[0][name] = round(v + cash - debt_y[0])
        for y in range(1, years + 1):
            for _m in range(12):
                inc = v * dy / 12
                v = v * (1 + r / 100 / 12) + contrib + (inc if reinvest else 0)
                cash = cash * (1 + 0.002 / 12) + (0 if reinvest else inc)
            rows[y][name] = round(v + cash - debt_y[y])
    return {"rows": rows, "milestones": {str(y): rows[y] for y in (5, 10, 20) if y <= years},
            "contribution_m": round(contrib), "start_net_worth": rows[0]["base"], "shock": round(shock),
            "assumptions": {**scen, "dividend_yield": dy * 100, "reinvest": reinvest, "rate_change": rc, "years": years}}


def risk(summ, assets, liabs, cf):
    ta = summ["total_assets"] or 1
    tl = summ["total_liabilities"]
    items = []

    def add(code, value, warn, danger, reverse=False, unit="%"):
        if reverse:
            level = "danger" if value < danger else "warn" if value < warn else "ok"
        else:
            level = "danger" if value > danger else "warn" if value > warn else "ok"
        items.append({"code": code, "value": round(value, 1), "warn": warn, "danger": danger, "level": level,
                      "unit": unit, "reverse": reverse})
    top = max(assets, key=lambda a: a["value_jpy"], default=None)
    add("concentration", (top["value_jpy"] if top else 0) / ta * 100, 25, 40)
    add("currency", summ["foreign_value"] / ta * 100, 50, 70)
    ctry = breakdown([a for a in assets if a.get("asset_class") in INVEST], lambda a: a.get("country") or "JP")
    add("country", ctry[0]["pct"] if ctry else 0, 60, 80)
    sec = breakdown([a for a in assets if a.get("asset_class") in EQUITY], "sector")
    add("sector", sec[0]["pct"] if sec else 0, 35, 50)
    var = sum(l.get("balance") or 0 for l in liabs if l.get("rate_type") == "variable")
    add("interest_rate", var / tl * 100 if tl else 0, 50, 80)
    add("liquidity", min(summ["liquid"] / cf["expense_m"], 99) if cf["expense_m"] else 99, 6, 3, True, "months")
    add("leverage", tl / ta * 100, 40, 60)
    add("balance", min(ta / tl, 99) if tl else 99, 2, 1.3, True, "x")
    score = max(0, 100 - sum(15 if i["level"] == "danger" else 7 if i["level"] == "warn" else 0 for i in items))
    return {"score": score, "items": items, "top_asset": top.get("name") if top else None,
            "top_country": ctry[0]["key"] if ctry else None, "top_sector": sec[0]["key"] if sec else None,
            "alerts": [i for i in items if i["level"] != "ok"]}

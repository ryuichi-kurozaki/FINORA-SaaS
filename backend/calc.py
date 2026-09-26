"""Derived calculations: positions from transactions, Data Health, goal progress, net-worth history."""
from datetime import datetime, timedelta

from analytics import INVEST, simulate

TX_ASSET_CLASSES = {"jp_stock", "foreign_stock", "etf", "fund", "bond", "crypto"}
NO_ACCOUNT_OK = {"real_estate", "insurance", "pension", "gold", "precious_metal", "unlisted"}
REQUIRED_DOCS = ["bank_doc", "tax_return"]


def _days_ago(iso):
    if not iso:
        return 9999
    try:
        return (datetime.now().date() - datetime.fromisoformat(str(iso)[:10]).date()).days
    except ValueError:
        return 9999


def positions(txs, assets):
    amap, pos = {a["id"]: a for a in assets}, {}
    for t in sorted(txs, key=lambda x: x.get("date") or ""):
        aid = t.get("asset_id")
        if not aid:
            continue
        p = pos.setdefault(aid, {"asset_id": aid, "qty": 0.0, "cost": 0.0, "realized": 0.0, "dividends": 0.0,
                                 "interest": 0.0, "fees": 0.0, "taxes": 0.0, "tx_count": 0})
        q, fee, tax = t.get("quantity") or 0, t.get("fee") or 0, t.get("tax") or 0
        amt = t.get("amount") or q * (t.get("unit_price") or 0)
        typ = t.get("tx_type")
        p["tx_count"] += 1
        p["fees"] += fee
        p["taxes"] += tax
        if typ == "buy":
            p["cost"] += amt + fee
            p["qty"] += q
        elif typ == "sell":
            avg = p["cost"] / p["qty"] if p["qty"] else 0
            p["realized"] += amt - fee - tax - avg * q
            p["cost"] -= avg * q
            p["qty"] -= q
        elif typ == "dividend":
            p["dividends"] += amt - tax
        elif typ == "interest":
            p["interest"] += amt - tax
        elif typ == "fee":
            p["fees"] += amt
        elif typ == "tax":
            p["taxes"] += amt
    out = []
    for aid, p in pos.items():
        a = amap.get(aid, {})
        p["avg_cost"] = p["cost"] / p["qty"] if p["qty"] else 0
        p["market_value"] = p["qty"] * (a.get("current_price") or 0) / (a.get("price_unit") or 1)
        p["unrealized"] = p["market_value"] - p["cost"]
        p.update(asset_name=a.get("name"), currency=a.get("currency"), client_id=a.get("client_id"),
                 registered_qty=a.get("quantity"), qty_mismatch=bool(a) and abs((a.get("quantity") or 0) - p["qty"]) > 1e-6)
        out.append({k: (round(v, 4) if isinstance(v, float) else v) for k, v in p.items()})
    return out


def data_health(data, txs, docs, pos):
    checks = []

    def add(code, level, items):
        checks.append({"code": code, "level": level if items else "ok", "count": len(items), "items": items[:30]})

    ref = lambda e, x: {"entity": e, "id": x["id"], "label": x.get("name") or x.get("institution") or x.get("title"), "client_id": x.get("client_id")}  # noqa: E731
    assets, liabs, cfs = data["assets"], data["liabilities"], data["cashflows"]
    add("missing_acq_price", "review", [ref("assets", a) for a in assets if a.get("asset_class") in INVEST and not a.get("acquisition_price")])
    add("missing_cur_price", "attention", [ref("assets", a) for a in assets if not a.get("current_price")])
    add("missing_currency", "attention", [ref("assets", a) for a in assets if not a.get("currency")] + [ref("accounts", a) for a in data["accounts"] if not a.get("currency")])
    add("missing_balance", "review", [ref("liabilities", x) for x in liabs if not x.get("balance")])
    add("missing_rate", "review", [ref("liabilities", x) for x in liabs if not x.get("interest_rate")])
    add("stale_valuation", "review", [ref("assets", a) for a in assets if _days_ago(a.get("price_date") or a.get("balance_date") or a.get("updated_at")) > 30])
    add("unlinked_account", "review", [ref("assets", a) for a in assets if not a.get("account_id") and a.get("asset_class") not in NO_ACCOUNT_OK])
    add("stale_loan", "attention", [ref("liabilities", x) for x in liabs if _days_ago(x.get("balance_date") or x.get("updated_at")) > 90])
    cids = {c["id"] for c in data["clients"]}
    add("cashflow_insufficient", "attention", [{"entity": "clients", "id": c["id"], "label": c.get("corporate_name") or c.get("name"), "client_id": c["id"]}
                                               for c in data["clients"] if not ({"income", "expense"} <= {f.get("direction") for f in cfs if f.get("client_id") == c["id"]})])
    missing_docs = []
    for cid in cids:
        have = {d.get("category") for d in docs if d.get("client_id") == cid}
        missing_docs += [{"entity": "documents", "id": f"{cid}:{k}", "label": k, "client_id": cid} for k in REQUIRED_DOCS if k not in have]
    add("docs_missing", "review", missing_docs)
    add("docs_expired", "review", [{"entity": "documents", "id": d["id"], "label": d.get("filename"), "client_id": d.get("client_id")}
                                   for d in docs if d.get("expiry_date") and d["expiry_date"] < datetime.now().date().isoformat()])
    tx_assets = {t.get("asset_id") for t in txs}
    add("tx_missing", "review", [ref("assets", a) for a in assets if a.get("asset_class") in TX_ASSET_CLASSES and a["id"] not in tx_assets])
    anomalies = [ref("assets", a) for a in assets if a.get("unrealized_pct", 0) > 300 or a.get("unrealized_pct", 0) < -70]
    anomalies += [{"entity": "assets", "id": p["asset_id"], "label": f"{p['asset_name']} (qty {p['qty']} ≠ {p['registered_qty']})", "client_id": p.get("client_id")} for p in pos if p["qty_mismatch"]]
    add("anomaly", "attention", anomalies)
    att = sum(c["level"] == "attention" for c in checks)
    rev = sum(c["level"] == "review" for c in checks)
    return {"score": max(0, 100 - att * 12 - rev * 5), "status": "attention" if att else "review" if rev else "ok",
            "checks": checks, "note": "FINORA never modifies source data automatically."}


def goals_progress(goals, summ, cf, liabs, risk_items):
    leverage = next((i["value"] for i in risk_items if i["code"] == "leverage"), 0)
    auto = {"net_worth": summ["net_worth"], "dividend": summ["dividends"] + summ["interest"],
            "investment_assets": summ["invested_value"], "debt_ratio": leverage, "loan_payoff": summ["total_liabilities"]}
    orig_debt = sum(x.get("original_amount") or x.get("balance") or 0 for x in liabs) or 1
    today = datetime.now().date()
    months = {}
    for g in goals:
        try:
            months[g["id"]] = max(0, (datetime.fromisoformat(g["target_date"][:10]).date() - today).days // 30)
        except (KeyError, TypeError, ValueError):
            months[g["id"]] = None
    horizon = max([m for m in months.values() if m] + [12])
    sim = simulate(summ, cf, liabs, {"years": min(40, -(-horizon // 12))})
    out = []
    for g in goals:
        cat, target = g.get("category"), g.get("target_amount") or 0
        manual = g.get("current_value") is not None
        cur = g["current_value"] if manual else auto.get(cat, 0)
        lower = cat in ("debt_ratio", "loan_payoff")
        if cat == "loan_payoff":
            pct = (1 - cur / orig_debt) * 100
        elif cat == "debt_ratio":
            pct = min(100, target / cur * 100) if cur else 100
        else:
            pct = cur / target * 100 if target else 0
        m = months[g["id"]]
        res = {**g, "current": round(cur, 2), "current_source": "manual" if manual else ("auto" if cat in auto else "manual"),
               "progress_pct": round(max(0, min(100, pct)), 1), "remaining": round(max(0, (cur - target) if lower else (target - cur)), 2),
               "months_left": m, "lower_is_better": lower, "simulation": None}
        if m is not None and cat in ("net_worth", "investment_assets", "retirement", "real_estate_fund", "business_fund") and target:
            row = sim["rows"][min(len(sim["rows"]) - 1, max(1, -(-m // 12)))]
            key = "_invest" if cat == "investment_assets" else ""
            res["simulation"] = {"year": row["year"], **{s: {"value": row.get(s + key, row[s]), "reached": row.get(s + key, row[s]) >= target}
                                                        for s in ("bull", "base", "bear")}}
        out.append(res)
    return out


def merge_history(monthly, daily):
    first_daily = min((d["date"] for d in daily), default="9999")
    agg = {}
    for s in monthly:
        date = f"{s['date']}-28"
        if date < first_daily:
            agg[date] = {"date": date, "total_assets": s["total_assets"], "total_liabilities": s["total_liabilities"], "net_worth": s["net_worth"]}
    for d in daily:
        x = agg.setdefault(d["date"], {"date": d["date"], "total_assets": 0, "total_liabilities": 0, "net_worth": 0})
        for k in ("total_assets", "total_liabilities", "net_worth"):
            x[k] += d.get(k) or 0
    return sorted(agg.values(), key=lambda x: x["date"])


def days_back(n):
    return (datetime.now().date() - timedelta(days=n)).isoformat()

const ASSET_CLASSES = ["cash", "deposit", "jp_stock", "foreign_stock", "etf", "fund", "bond", "fx", "crypto", "real_estate", "insurance", "pension", "gold", "precious_metal", "unlisted", "other"];
const CURRENCIES = ["JPY", "USD", "EUR", "GBP", "BRL", "CNY", "AUD", "HKD", "SGD", "CHF"];
const OWNER = ["individual", "corporate"];
export const INCOME_CATS = ["salary", "executive_comp", "business_income", "dividend", "interest", "real_estate_income", "investment_income", "other_income"];
export const EXPENSE_CATS = ["living", "business_expense", "tax", "social_insurance", "insurance", "loan_repayment", "investment", "other"];
export const DOC_CATS = ["contract", "bank_doc", "securities_doc", "financial_statement", "tax_return", "insurance_policy", "real_estate_doc", "loan_doc", "investment_doc", "other"];
export const OWNED = ["accounts", "assets", "liabilities", "cashflows", "transactions", "goals"];
export const TX_TYPES = ["buy", "sell", "deposit_tx", "withdrawal", "dividend", "interest", "fee", "tax", "transfer", "other"];
export const GOAL_CATS = ["net_worth", "dividend", "loan_payoff", "debt_ratio", "investment_assets", "retirement", "real_estate_fund", "business_fund", "other"];
export const REQ_CATS = ["rc_portfolio", "rc_tax", "rc_real_estate", "rc_loan", "rc_insurance", "rc_retirement", "rc_business", "other"];
export const REQ_STATUS = ["new", "accepted", "reviewing", "meeting_scheduled", "in_progress", "completed", "closed"];

// type: text | number | money | date | select | textarea | client | account | user
export const ENTITIES = {
  clients: [
    { k: "client_type", type: "select", opts: ["individual", "corporate"], table: true, req: true },
    { k: "name", table: true, req: true },
    { k: "corporate_name", table: true },
    { k: "email", table: true },
    { k: "phone" }, { k: "address", wide: true }, { k: "occupation" }, { k: "business" }, { k: "family" }, { k: "related_corps" },
    { k: "annual_income", type: "money", table: true }, { k: "income", type: "money", label: "income_field" },
    { k: "investment_experience" }, { k: "investment_purpose" },
    { k: "risk_tolerance", type: "select", opts: ["conservative", "moderate", "aggressive"], table: true },
    { k: "consultant_id", type: "user", table: true, adminOnly: true },
    { k: "status", type: "select", opts: ["active", "prospect", "dormant"], table: true },
    { k: "notes", type: "textarea", wide: true },
  ],
  accounts: [
    { k: "client_id", type: "client", table: true, req: true },
    { k: "institution", table: true, req: true },
    { k: "account_type", type: "select", opts: ["bank", "securities", "crypto_exchange", "other_institution"], table: true },
    { k: "region", type: "select", opts: ["domestic", "overseas"], table: true },
    { k: "owner_type", type: "select", opts: OWNER, table: true },
    { k: "currency", type: "select", opts: CURRENCIES, raw: true, table: true },
    { k: "branch" }, { k: "account_number" }, { k: "notes", type: "textarea", wide: true },
  ],
  assets: [
    { k: "client_id", type: "client", table: true, req: true },
    { k: "asset_class", type: "select", opts: ASSET_CLASSES, table: true, req: true },
    { k: "name", label: "asset_name", table: true, req: true },
    { k: "ticker" }, { k: "account_id", type: "account" },
    { k: "owner_type", type: "select", opts: OWNER },
    { k: "country", type: "select", opts: ["JP", "US", "BR", "GLOBAL", "other"] },
    { k: "sector", type: "select", opts: ["technology", "automotive", "diversified", "government", "digital_asset", "real_estate", "commodity", "energy", "finance", "healthcare", "consumer", "industrial", "other"] },
    { k: "currency", type: "select", opts: CURRENCIES, raw: true, table: true },
    { k: "acquired_date", type: "date" },
    { k: "acquisition_price", type: "number" }, { k: "quantity", type: "number", table: true }, { k: "current_price", type: "number", table: true },
    { k: "realized_pl", type: "number" }, { k: "dividend_annual", type: "number" }, { k: "interest_annual", type: "number" },
    { k: "price_date", type: "date" }, { k: "balance_date", type: "date" },
    { k: "notes", type: "textarea", wide: true },
    { k: "value_jpy", type: "money", table: true, computed: true },
    { k: "pl_jpy", type: "pl", table: true, computed: true },
  ],
  transactions: [
    { k: "client_id", type: "client", table: true, req: true },
    { k: "date", type: "date", table: true, req: true },
    { k: "tx_type", type: "select", opts: TX_TYPES, table: true, req: true },
    { k: "asset_id", type: "asset", table: true }, { k: "account_id", type: "account" },
    { k: "quantity", type: "number", table: true }, { k: "unit_price", type: "number", table: true },
    { k: "amount", type: "number", table: true, req: true },
    { k: "currency", type: "select", opts: CURRENCIES, raw: true, table: true },
    { k: "fx_rate", type: "number" }, { k: "fee", type: "number" }, { k: "tax", type: "number" },
    { k: "notes", type: "textarea", wide: true },
  ],
  goals: [
    { k: "client_id", type: "client", table: true, req: true },
    { k: "name", label: "goal_name", table: true, req: true, wide: true },
    { k: "category", type: "select", opts: GOAL_CATS, prefix: "g_", table: true, req: true },
    { k: "target_amount", type: "number", table: true, req: true }, { k: "current_value", type: "number" },
    { k: "target_date", type: "date", table: true }, { k: "priority", type: "select", opts: ["low", "medium", "high"], table: true },
    { k: "notes", type: "textarea", wide: true },
  ],
  liabilities: [
    { k: "client_id", type: "client", table: true, req: true },
    { k: "liability_type", type: "select", opts: ["mortgage", "real_estate_loan", "business_loan", "auto_loan", "card_loan", "other_loan"], table: true, req: true },
    { k: "institution", table: true, req: true },
    { k: "owner_type", type: "select", opts: OWNER },
    { k: "original_amount", type: "money" }, { k: "balance", type: "money", table: true, req: true },
    { k: "interest_rate", type: "number", table: true }, { k: "rate_type", type: "select", opts: ["fixed", "variable"], table: true },
    { k: "monthly_payment", type: "money", table: true }, { k: "start_date", type: "date" }, { k: "term_months", type: "number" },
    { k: "maturity_date", type: "date", table: true }, { k: "collateral" }, { k: "balance_date", type: "date" }, { k: "notes", type: "textarea", wide: true },
  ],
  cashflows: [
    { k: "client_id", type: "client", table: true, req: true },
    { k: "direction", type: "select", opts: ["income", "expense"], table: true, req: true },
    { k: "category", type: "category", table: true, req: true },
    { k: "name", label: "item_name", table: true },
    { k: "amount", type: "money", table: true, req: true },
    { k: "frequency", type: "select", opts: ["monthly", "quarterly", "annual", "once"], table: true },
    { k: "owner_type", type: "select", opts: OWNER }, { k: "notes", type: "textarea", wide: true },
  ],
  consulting: [
    { k: "client_id", type: "client", table: true, req: true },
    { k: "kind", type: "select", opts: ["hearing", "analysis", "purpose", "issue", "scenario", "proposal", "meeting", "next_step"], table: true, req: true },
    { k: "date", type: "date", table: true, req: true },
    { k: "title", table: true, req: true },
    { k: "content", type: "textarea", wide: true },
    { k: "next_action", table: true, wide: true },
    { k: "status", type: "select", opts: ["open", "in_progress", "done"], table: true },
  ],
  tasks: [
    { k: "title", table: true, req: true, wide: true },
    { k: "kind", type: "select", opts: ["meeting", "next_contact", "internal", "document_deadline", "dividend", "loan_renewal", "insurance_renewal", "other"], table: true },
    { k: "client_id", type: "client", table: true },
    { k: "due_date", type: "date", table: true, req: true },
    { k: "priority", type: "select", opts: ["low", "medium", "high"], table: true },
    { k: "status", type: "select", opts: ["open", "in_progress", "done"], table: true },
    { k: "assignee_id", type: "user" },
    { k: "visibility", type: "select", opts: ["internal", "shared"], table: true },
    { k: "notes", type: "textarea", wide: true },
  ],
};

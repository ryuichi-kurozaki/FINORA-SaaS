import { useRef, useState } from "react";
import { Ban, CreditCard, Eye, FileDown, Plus, RefreshCw, RotateCcw, Send, Trash2, Wallet } from "lucide-react";
import { toast } from "sonner";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useApp } from "@/context/AppContext";
import { api, errMsg, useApi } from "@/lib/api";
import { yen } from "@/lib/format";
import { Card, CardTitle, Empty, PageHeader, Spinner } from "@/components/common";
import { useScopeLabel } from "@/lib/useDashboard";
import EContractPanel from "@/components/econtract/EContractPanel";
import InvoiceDoc from "@/components/InvoiceDoc";
import { RevenuePanel } from "@/components/BusinessOverview";

export const ST = { DRAFT: "bg-slate-100 text-slate-600", ISSUED: "bg-sky-50 text-sky-700", PAID: "bg-emerald-50 text-emerald-700", PARTIALLY_PAID: "bg-amber-50 text-amber-700", OVERDUE: "bg-red-50 text-red-700", CANCELLED: "bg-slate-100 text-slate-400" };
const inp = "mt-1 h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm";
const today = () => new Date().toISOString().slice(0, 10);

function InvoiceView({ id, onClose }) {
  const { t } = useApp();
  const { data } = useApi(id ? `/invoices/${id}` : null, [id]);
  const ref = useRef(null);
  const pdf = async () => {
    const html2pdf = (await import("html2pdf.js")).default;
    await html2pdf().set({ margin: 6, filename: `${data.number}.pdf`, html2canvas: { scale: 2 }, jsPDF: { format: "a4" } }).from(ref.current).save();
  };
  return (
    <Dialog open={!!id} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-[820px] overflow-auto">
        <DialogHeader><DialogTitle>{t("invoices")}</DialogTitle></DialogHeader>
        {!data ? <Spinner /> : <div className="overflow-x-auto"><div ref={ref}><InvoiceDoc inv={data} t={t} /></div></div>}
        <DialogFooter><Button className="btn-emerald" onClick={pdf} disabled={!data} data-testid="invoice-pdf-btn"><FileDown className="mr-1 h-4 w-4" />{t("export_pdf")}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function NewInvoice({ open, onClose, clientId, onDone }) {
  const { t, clients } = useApp();
  const [f, setF] = useState({ client_id: clientId || "", contract_id: "", description: "", quantity: 1, unit_price: "", due_date: "", notes: "" });
  const { data: cons } = useApi(f.client_id ? `/data/contracts?client_id=${f.client_id}` : null, [f.client_id]);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const save = async () => {
    const items = f.description ? [{ description: f.description, quantity: Number(f.quantity) || 1, unit_price: Number(f.unit_price) || 0 }] : [];
    try {
      await api.post("/invoices", { client_id: f.client_id, contract_id: f.contract_id || null, items, due_date: f.due_date || null, notes: f.notes });
      toast.success(t("saved")); onDone(); onClose();
    } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>{t("new_invoice")}</DialogTitle></DialogHeader>
        <div className="grid gap-3 text-xs text-slate-600">
          {!clientId && <label>{t("client")}<select className={inp} value={f.client_id} onChange={set("client_id")} data-testid="inv-client"><option value="">—</option>{clients.map((c) => <option key={c.id} value={c.id}>{c.corporate_name || c.name}</option>)}</select></label>}
          <label>{t("contracts")}<select className={inp} value={f.contract_id} onChange={set("contract_id")} data-testid="inv-contract"><option value="">—</option>{(cons || []).map((c) => <option key={c.id} value={c.id}>{c.name} ({yen(c.fee)})</option>)}</select></label>
          <label>{t("item_desc")}<input className={inp} value={f.description} onChange={set("description")} data-testid="inv-desc" /></label>
          <div className="grid grid-cols-2 gap-3">
            <label>{t("quantity")}<input type="number" className={inp} value={f.quantity} onChange={set("quantity")} data-testid="inv-qty" /></label>
            <label>{t("unit_price_inv")}<input type="number" className={inp} value={f.unit_price} onChange={set("unit_price")} data-testid="inv-price" /></label>
          </div>
          <label>{t("due_date_inv")}<input type="date" className={inp} value={f.due_date} onChange={set("due_date")} data-testid="inv-due" /></label>
          <label>{t("notes")}<input className={inp} value={f.notes} onChange={set("notes")} data-testid="inv-notes" /></label>
        </div>
        <DialogFooter><Button className="btn-emerald" onClick={save} disabled={!f.client_id || (!f.contract_id && !f.description)} data-testid="inv-save">{t("save")}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function PaymentDialog({ inv, onClose, onDone }) {
  const { t } = useApp();
  const [f, setF] = useState({ date: today(), amount: "", method: "BANK_TRANSFER", reference: "", notes: "" });
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const save = async () => {
    try { await api.post("/payments", { ...f, invoice_id: inv.id, amount: Number(f.amount || inv.balance) }); toast.success(t("saved")); onDone(); onClose(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Dialog open={!!inv} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>{t("record_payment")} · {inv?.number}</DialogTitle></DialogHeader>
        <div className="grid gap-3 text-xs text-slate-600">
          <div className="rounded-lg bg-slate-50 p-2 text-sm">{t("balance")}: <b className="font-num">{yen(inv?.balance)}</b></div>
          <label>{t("payment_date")}<input type="date" className={inp} value={f.date} onChange={set("date")} data-testid="pay-date" /></label>
          <label>{t("amount")}<input type="number" className={inp} placeholder={String(inv?.balance || "")} value={f.amount} onChange={set("amount")} data-testid="pay-amount" /></label>
          <label>{t("method")}<select className={inp} value={f.method} onChange={set("method")} data-testid="pay-method">{["BANK_TRANSFER", "CREDIT_CARD", "CASH", "OTHER"].map((m) => <option key={m} value={m}>{t(m)}</option>)}</select></label>
          <label>{t("reference")}<input className={inp} value={f.reference} onChange={set("reference")} data-testid="pay-ref" /></label>
        </div>
        <DialogFooter><Button className="btn-emerald" onClick={save} data-testid="pay-save">{t("save")}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function RefundDialog({ inv, onClose, onDone }) {
  const { t } = useApp();
  const [busy, setBusy] = useState(false);
  const go = async (e) => {
    e.preventDefault();
    setBusy(true);
    try { await api.post(`/stripe/refund/invoice/${inv.id}`); toast.success(t("refund_done")); onDone(); onClose(); } catch (err) { toast.error(errMsg(err)); } finally { setBusy(false); }
  };
  return (
    <AlertDialog open={!!inv} onOpenChange={(o) => !o && !busy && onClose()}>
      <AlertDialogContent data-testid="refund-dialog">
        <AlertDialogHeader>
          <AlertDialogTitle>{t("refund_title")}</AlertDialogTitle>
          <AlertDialogDescription data-testid="refund-dialog-body">{inv?.number} — {t("refund_body").replace("{amount}", yen(inv?.paid || 0))}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={busy} data-testid="refund-cancel">{t("cancel_action")}</AlertDialogCancel>
          <AlertDialogAction disabled={busy} onClick={go} className="bg-red-600 hover:bg-red-700" data-testid="refund-confirm">{busy ? "…" : t("refund_confirm")}</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export function InvoiceList({ clientId }) {
  const { t, user, isClient } = useApp();
  const owner = user.role === "admin";
  const payCard = async (i) => {
    try { const { data } = await api.post("/stripe/checkout/invoice", { invoice_id: i.id, origin_url: window.location.origin }); window.location.href = data.checkout_url; } catch (e) { toast.error(errMsg(e)); }
  };
  const { data, loading, reload } = useApi(`/invoices${clientId ? `?client_id=${clientId}` : ""}`, [clientId]);
  const [view, setView] = useState(null);
  const [pay, setPay] = useState(null);
  const [nw, setNw] = useState(false);
  const [refund, setRefund] = useState(null);
  const act = async (path) => { try { await api.post(path); toast.success(t("saved")); reload(); } catch (e) { toast.error(errMsg(e)); } };
  return (
    <Card>
      <div className="mb-3 flex items-center justify-between"><CardTitle>{t("invoices")}</CardTitle>{owner && <Button size="sm" className="btn-emerald" onClick={() => setNw(true)} data-testid="new-invoice-btn"><Plus className="mr-1 h-4 w-4" />{t("new_invoice")}</Button>}</div>
      {loading ? <Spinner /> : !data?.length ? <Empty text={t("no_data")} /> : (
        <div className="overflow-x-auto">
          <table className="data-table w-full min-w-[820px] text-sm" data-testid="invoice-table">
            <thead><tr>{["invoice_no", "client", "issue_date", "due_date_inv", "total_amount", "paid_amount", "balance", "status", "actions"].map((h) => <th key={h}>{t(h)}</th>)}</tr></thead>
            <tbody>
              {data.map((i) => (
                <tr key={i.id} data-testid={`invoice-row-${i.id}`}>
                  <td className="font-num">{i.number}</td><td>{i.client_name}</td><td className="font-num">{i.issue_date}</td><td className="font-num">{i.due_date}</td>
                  <td className="font-num">{yen(i.total)}</td><td className="font-num text-[#00A878]">{yen(i.paid)}</td><td className="font-num">{yen(i.balance)}</td>
                  <td><span className={`rounded-md px-2 py-0.5 text-xs font-medium ${ST[i.status]}`} data-testid={`invoice-status-${i.id}`}>{t(i.status)}</span></td>
                  <td className="whitespace-nowrap">
                    <button className="icon-btn" onClick={() => setView(i.id)} data-testid={`invoice-view-${i.id}`}><Eye className="h-4 w-4" /></button>
                    {owner && i.status === "DRAFT" && <button className="icon-btn text-sky-600" onClick={() => act(`/invoices/${i.id}/issue`)} title={t("issue")} data-testid={`invoice-issue-${i.id}`}><Send className="h-4 w-4" /></button>}
                    {owner && ["ISSUED", "PARTIALLY_PAID", "OVERDUE"].includes(i.status) && <button className="icon-btn text-[#00A878]" onClick={() => setPay(i)} title={t("record_payment")} data-testid={`invoice-pay-${i.id}`}><Wallet className="h-4 w-4" /></button>}
                    {isClient && i.card_enabled && ["ISSUED", "PARTIALLY_PAID", "OVERDUE"].includes(i.status) && i.balance > 0 && <button className="ml-1 inline-flex items-center gap-1 rounded-lg bg-[#071A2B] px-2.5 py-1 text-xs font-semibold text-white hover:bg-[#00A878]" onClick={() => payCard(i)} data-testid={`invoice-card-pay-${i.id}`}><CreditCard className="h-3.5 w-3.5" />{t("pay_by_card")}</button>}
                    {owner && i.card_refundable && <button className="icon-btn text-amber-600 hover:text-red-600" onClick={() => setRefund(i)} title={t("refund")} aria-label={t("refund")} data-testid={`invoice-refund-${i.id}`}><RotateCcw className="h-4 w-4" /></button>}
                    {owner && !i.paid && !["CANCELLED", "PAID"].includes(i.status) && <button className="icon-btn hover:text-red-600" onClick={() => act(`/invoices/${i.id}/cancel`)} title={t("CANCELLED")} data-testid={`invoice-cancel-${i.id}`}><Ban className="h-4 w-4" /></button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <InvoiceView id={view} onClose={() => setView(null)} />
      <PaymentDialog key={pay?.id} inv={pay} onClose={() => setPay(null)} onDone={reload} />
      <RefundDialog inv={refund} onClose={() => setRefund(null)} onDone={reload} />
      {nw && <NewInvoice open={nw} onClose={() => setNw(false)} clientId={clientId} onDone={reload} />}
    </Card>
  );
}

export function PaymentsList({ clientId }) {
  const { t, user } = useApp();
  const { data, loading, reload } = useApi(`/payments${clientId ? `?client_id=${clientId}` : ""}`, [clientId]);
  const del = async (id) => { try { await api.delete(`/payments/${id}`); toast.success(t("deleted")); reload(); } catch (e) { toast.error(errMsg(e)); } };
  return (
    <Card>
      <CardTitle>{t("payments")}</CardTitle>
      {loading ? <Spinner /> : !data?.length ? <Empty text={t("no_data")} /> : (
        <div className="overflow-x-auto">
          <table className="data-table w-full min-w-[640px] text-sm" data-testid="payment-table">
            <thead><tr>{["payment_date", "invoice_no", "client", "amount", "method", "reference", ""].map((h) => <th key={h}>{h && t(h)}</th>)}</tr></thead>
            <tbody>{data.map((p) => (
              <tr key={p.id}><td className="font-num">{p.date}</td><td className="font-num">{p.invoice_number}</td><td>{p.client_name}</td><td className="font-num text-[#00A878]">{p.refunded ? <span className="text-slate-400 line-through">{yen(p.amount)}</span> : yen(p.amount)}{p.refunded && <span className="ml-2 rounded-md bg-amber-50 px-1.5 py-0.5 text-[11px] font-medium text-amber-700 no-underline" data-testid={`payment-refunded-${p.id}`}>{t("refunded")}</span>}{!p.refunded && p.refunded_amount > 0 && <span className="ml-2 rounded-md bg-amber-50 px-1.5 py-0.5 text-[11px] font-medium text-amber-700" data-testid={`payment-partial-refund-${p.id}`}>{t("partially_refunded")} {yen(p.refunded_amount)}</span>}</td><td>{t(p.method)}</td><td>{p.reference || "—"}</td>
                <td>{user.role === "admin" && <button className="icon-btn hover:text-red-600" onClick={() => del(p.id)} data-testid={`payment-delete-${p.id}`}><Trash2 className="h-4 w-4" /></button>}</td></tr>
            ))}</tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

export default function Billing() {
  const { t, user, isClient, scopeClient } = useApp();
  const scope = useScopeLabel();
  const [k, setK] = useState(0);
  const gen = async () => { try { const { data } = await api.post("/invoices/generate-recurring"); toast.success(`${t("generate_recurring")}: ${data.created}`); setK(k + 1); } catch (e) { toast.error(errMsg(e)); } };
  const tabs = ["invoices", "contracts", "payments", ...(isClient ? [] : ["revenue"])];
  return (
    <div data-testid="billing-page">
      <PageHeader eyebrow={`Billing · ${scope}`} title={t("billing")}>{user.role === "admin" && <Button variant="outline" onClick={gen} data-testid="generate-recurring-btn"><RefreshCw className="mr-1 h-4 w-4" />{t("generate_recurring")}</Button>}</PageHeader>
      <Tabs defaultValue="invoices" key={k}>
        <TabsList className="bg-white/70">{tabs.map((x) => <TabsTrigger key={x} value={x} data-testid={`billing-tab-${x}`} className="data-[state=active]:bg-[#071A2B] data-[state=active]:text-white">{t(x)}</TabsTrigger>)}</TabsList>
        <TabsContent value="invoices" className="mt-5"><InvoiceList clientId={scopeClient} /></TabsContent>
        <TabsContent value="contracts" className="mt-5"><EContractPanel key={scopeClient} clientId={scopeClient} grouped={isClient} /></TabsContent>
        <TabsContent value="payments" className="mt-5"><PaymentsList clientId={scopeClient} /></TabsContent>
        {!isClient && <TabsContent value="revenue" className="mt-5"><RevenuePanel /></TabsContent>}
      </Tabs>
    </div>
  );
}

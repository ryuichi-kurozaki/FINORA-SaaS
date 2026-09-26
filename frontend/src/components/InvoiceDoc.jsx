import { LogoFull } from "@/components/Logo";
import { yen } from "@/lib/format";

export default function InvoiceDoc({ inv, t }) {
  const iss = inv.issuer || {};
  return (
    <div className="bg-white p-8 text-[#202A33]" style={{ width: 760 }} data-testid="invoice-document">
      <div className="flex items-start justify-between border-b-2 border-[#071A2B] pb-4">
        <LogoFull className="h-12 w-auto" />
        <div className="text-right">
          <div className="font-display text-2xl font-extrabold tracking-[0.3em] text-[#071A2B]">{t("invoice_title")}</div>
          <div className="mt-1 font-num text-xs text-slate-500">{t("invoice_no")}: {inv.number}</div>
          <div className="font-num text-xs text-slate-500">{t("issue_date")}: {inv.issue_date}</div>
          <div className="font-num text-xs font-semibold text-[#071A2B]">{t("due_date_inv")}: {inv.due_date}</div>
        </div>
      </div>
      <div className="mt-6 grid grid-cols-2 gap-8 text-sm">
        <div>
          <div className="border-b border-slate-300 pb-1 text-lg font-bold">{inv.client_name} <span className="text-sm font-normal">{t("bill_to")}</span></div>
          {inv.contract_name && <div className="mt-2 text-xs text-slate-500">{t("contracts")}: {inv.contract_name}</div>}
          <div className="mt-4 rounded-lg bg-[#F7F9FC] p-3">
            <div className="text-xs text-slate-500">{t("total_amount")}</div>
            <div className="font-num text-2xl font-bold text-[#071A2B]">{yen(inv.total)}</div>
          </div>
        </div>
        <div className="text-right text-xs leading-relaxed text-slate-600">
          <div className="text-sm font-bold text-[#071A2B]">{iss.company_name}</div>
          {iss.representative && <div>{iss.representative}</div>}
          {iss.address && <div>{iss.address}</div>}
          {iss.phone && <div>{iss.phone}</div>}
          {iss.email && <div>{iss.email}</div>}
          {iss.registration_no && <div>{t("registration_no")}: {iss.registration_no}</div>}
        </div>
      </div>
      <table className="mt-6 w-full text-sm">
        <thead><tr className="bg-[#071A2B] text-white"><th className="p-2 text-left">{t("item_desc")}</th><th className="p-2 text-right">{t("quantity")}</th><th className="p-2 text-right">{t("unit_price_inv")}</th><th className="p-2 text-right">{t("amount")}</th></tr></thead>
        <tbody>
          {inv.items.map((it, i) => (
            <tr key={i} className="border-b border-slate-200"><td className="p-2">{it.description}</td><td className="p-2 text-right font-num">{it.quantity}</td><td className="p-2 text-right font-num">{yen(it.unit_price)}</td><td className="p-2 text-right font-num">{yen(it.quantity * it.unit_price)}</td></tr>
          ))}
        </tbody>
      </table>
      <div className="ml-auto mt-4 w-72 space-y-1 text-sm">
        <div className="flex justify-between"><span>{t("subtotal")}</span><span className="font-num">{yen(inv.subtotal)}</span></div>
        <div className="flex justify-between"><span>{t("tax_amount")} ({inv.tax_rate}% · {t(inv.tax_mode)})</span><span className="font-num">{yen(inv.tax)}</span></div>
        <div className="flex justify-between border-t-2 border-[#071A2B] pt-1 text-base font-bold"><span>{t("total_amount")}</span><span className="font-num">{yen(inv.total)}</span></div>
        {inv.paid > 0 && <div className="flex justify-between text-[#00A878]"><span>{t("paid_amount")}</span><span className="font-num">{yen(inv.paid)}</span></div>}
        {inv.paid > 0 && <div className="flex justify-between font-semibold"><span>{t("inv_balance")}</span><span className="font-num">{yen(inv.balance)}</span></div>}
      </div>
      {iss.bank_info && <div className="mt-6 rounded-lg border border-slate-200 p-3 text-xs"><b>{t("bank_info")}</b><div className="mt-1 whitespace-pre-wrap">{iss.bank_info}</div></div>}
      {(inv.notes || iss.invoice_note) && <div className="mt-3 whitespace-pre-wrap text-xs text-slate-500">{inv.notes || iss.invoice_note}</div>}
      <div className="mt-8 border-t border-slate-200 pt-2 text-center text-[10px] text-slate-400">Issued via FINORA · www.finora.co.jp</div>
    </div>
  );
}

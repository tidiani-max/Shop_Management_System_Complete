import { useState } from "react";
import { AlertTriangle, Clock, TrendingUp } from "lucide-react";
import { num } from "./api";
import { useFetch } from "./ctx";

type Lang = "fr" | "ar";
const fmt = (v: number, lang: Lang) =>
  `${new Intl.NumberFormat(lang === "ar" ? "ar-MA" : "fr-FR", { maximumFractionDigits: 0 }).format(v)} FCFA`;
const money = (v: number, lang: Lang) => (lang === "ar" ? `\u2066${fmt(v, lang)}\u2069` : fmt(v, lang));
const n = (v: number, lang: Lang) =>
  new Intl.NumberFormat(lang === "ar" ? "ar-MA" : "fr-FR", { maximumFractionDigits: 2 }).format(v);

/** "What is wrong" + "what to do", keyed by the alert type returned by /reports/insights. */
const ALERTS: Record<string, { fr: [string, string]; ar: [string, string] }> = {
  LOSS_SALES: {
    fr: ["Produits vendus à perte", "Vérifiez le prix de vente : il est inférieur au coût d’achat. Corrigez le prix ou le coût."],
    ar: ["منتجات بيعت بخسارة", "راجع سعر البيع: أقل من تكلفة الشراء. صحّح السعر أو التكلفة."],
  },
  PRICE_BELOW_COST: {
    fr: ["Prix catalogue inférieur au coût", "Chaque vente fait perdre de l’argent. Augmentez le prix (mot de passe administrateur)."],
    ar: ["سعر الكتالوج أقل من التكلفة", "كل عملية بيع تسبب خسارة. ارفع السعر (بكلمة مرور المدير)."],
  },
  LOW_MARGIN: {
    fr: ["Marge très faible", "Le gain est presque nul. Négociez l’achat ou augmentez légèrement le prix."],
    ar: ["هامش ربح ضعيف جداً", "الربح شبه معدوم. فاوض على سعر الشراء أو ارفع السعر قليلاً."],
  },
  RESTOCK: {
    fr: ["À réapprovisionner vite", "Ces produits se vendent bien et vont manquer. Commandez la quantité suggérée (≈ 2 semaines de ventes)."],
    ar: ["يجب إعادة التموين بسرعة", "تُباع جيداً وستنفد قريباً. اطلب الكمية المقترحة (≈ مبيعات أسبوعين)."],
  },
  DEAD_STOCK: {
    fr: ["Stock qui ne bouge pas", "Argent immobilisé. Faites une promotion, regroupez les produits, ou arrêtez de racheter."],
    ar: ["مخزون راكد", "أموال مجمّدة. اعمل عرضاً ترويجياً أو لا تعد الشراء."],
  },
  OVERDUE_CREDIT: {
    fr: ["Crédits clients en retard", "Appelez ces clients et fixez une date de paiement. Évitez de leur redonner du crédit."],
    ar: ["ديون عملاء متأخرة", "اتصل بهؤلاء العملاء وحدد موعد السداد. تجنّب منحهم دَيناً جديداً."],
  },
  REGISTER_DIFF: {
    fr: ["Écarts de caisse", "Le comptage ne correspond pas au système. Vérifiez avec l’employé concerné."],
    ar: ["فروقات في الصندوق", "الجرد لا يطابق النظام. تحقق مع الموظف المعني."],
  },
};

function itemLine(type: string, it: any, lang: Lang): string {
  const fr = lang === "fr";
  switch (type) {
    case "LOSS_SALES":
      return `${it.label} — ${fr ? "perte" : "خسارة"} ${money(num(it.loss), lang)}`;
    case "PRICE_BELOW_COST":
      return `${it.label} — ${fr ? "prix" : "السعر"} ${money(num(it.price), lang)} < ${fr ? "coût" : "التكلفة"} ${money(num(it.cost), lang)}`;
    case "LOW_MARGIN":
      return `${it.label} — ${fr ? "marge" : "الهامش"} ${it.margin_pct}%`;
    case "RESTOCK":
      return `${it.label} — ${fr ? "reste" : "المتبقي"} ${n(num(it.stock_qty), lang)} ${it.base_unit} (${n(num(it.days_left), lang)} ${fr ? "j" : "يوم"}) → ${fr ? "commander" : "اطلب"} ${n(num(it.suggested_qty), lang)}`;
    case "DEAD_STOCK":
      return `${it.label} — ${n(num(it.stock_qty), lang)} ${it.base_unit} · ${money(num(it.stock_value), lang)} ${fr ? "immobilisés" : "مجمّدة"}${it.days_since_sale != null ? ` · ${it.days_since_sale} ${fr ? "j sans vente" : "يوم بلا بيع"}` : ""}`;
    case "OVERDUE_CREDIT":
      return `${it.party_name}${it.phone ? ` (${it.phone})` : ""} — ${money(num(it.balance), lang)} · ${it.days} ${fr ? "jours" : "يوم"}`;
    case "REGISTER_DIFF":
      return `${new Date(it.closed_at).toLocaleDateString(lang === "ar" ? "ar-MA" : "fr-FR")}${it.closed_by ? ` · ${it.closed_by}` : ""} — ${fr ? "espèces" : "نقد"} ${money(num(it.diff_cash), lang)} / ${fr ? "mobile" : "موبايل"} ${money(num(it.diff_mobile), lang)}`;
    default:
      return it.label || "";
  }
}

export function OwnerInsights({ lang, period }: { lang: Lang; period: string }) {
  const fr = lang === "fr";
  const { data } = useFetch<any>(`/reports/insights?period=${period}`);
  const [rank, setRank] = useState<"qty" | "profit">("qty");
  const [openAlert, setOpenAlert] = useState<string>("");
  if (!data) return null;
  const list: any[] = rank === "qty" ? data.top_by_qty : data.top_by_profit;
  const maxRev = Math.max(1, ...data.hours.map((h: any) => num(h.revenue)));
  const hasHours = data.hours.some((h: any) => h.invoices > 0);
  const sev: Record<string, string> = { high: "red", medium: "amber", low: "green" };
  const sevLabel: Record<string, string> = fr
    ? { high: "Urgent", medium: "À surveiller", low: "Info" }
    : { high: "عاجل", medium: "للمتابعة", low: "معلومة" };
  return (
    <div style={{ display: "grid", gap: 16, marginTop: 16 }}>
      <section className="card">
        <div className="card-title">
          <h3>
            <AlertTriangle size={17} style={{ verticalAlign: "-3px" }} />{" "}
            {fr ? "Diagnostic : ce qui ne va pas et quoi faire" : "التشخيص: ما المشكلة وماذا تفعل"}
          </h3>
        </div>
        {data.diagnostics.length === 0 && (
          <p className="muted">{fr ? "Tout est en ordre sur cette période." : "كل شيء على ما يرام في هذه الفترة."}</p>
        )}
        {data.diagnostics.map((a: any) => {
          const txt = ALERTS[a.type]?.[lang] || [a.type, ""];
          const isOpen = openAlert === a.type;
          return (
            <div key={a.type} style={{ borderTop: "1px solid var(--line)", padding: "10px 0" }}>
              <button
                type="button"
                onClick={() => setOpenAlert(isOpen ? "" : a.type)}
                style={{ display: "flex", gap: 10, alignItems: "center", width: "100%", background: "none", border: 0, font: "inherit", textAlign: "start", color: "inherit" }}
              >
                <span className={`badge ${sev[a.severity]}`}>{sevLabel[a.severity]}</span>
                <b style={{ flex: 1 }}>
                  {txt[0]} ({a.count})
                </b>
                <small className="muted">{isOpen ? "−" : "+"}</small>
              </button>
              <p className="muted" style={{ margin: "6px 0 0" }}>{txt[1]}</p>
              {isOpen && (
                <ul style={{ margin: "8px 0 0", paddingInlineStart: 18, display: "grid", gap: 4 }}>
                  {a.items.slice(0, 10).map((it: any, i: number) => (
                    <li key={i}>{itemLine(a.type, it, lang)}</li>
                  ))}
                  {a.items.length > 10 && <li className="muted">… +{a.items.length - 10}</li>}
                </ul>
              )}
            </div>
          );
        })}
      </section>

      <section className="card">
        <div className="card-title">
          <h3>
            <TrendingUp size={17} style={{ verticalAlign: "-3px" }} /> {fr ? "Top 20 des produits" : "أفضل 20 منتجاً"}
          </h3>
        </div>
        <div className="tabs">
          <button className={rank === "qty" ? "active" : ""} onClick={() => setRank("qty")}>
            {fr ? "Par quantité vendue" : "حسب الكمية"}
          </button>
          <button className={rank === "profit" ? "active" : ""} onClick={() => setRank("profit")}>
            {fr ? "Par bénéfice" : "حسب الربح"}
          </button>
        </div>
        {list.length === 0 && <p className="muted">{fr ? "Aucune vente sur cette période." : "لا مبيعات في هذه الفترة."}</p>}
        {list.map((p: any, i: number) => (
          <div className="rank-row" key={p.product_id}>
            <span className="rank">{i + 1}</span>
            <div>
              <b>{(lang === "ar" && p.name_ar) || p.label}</b>
              <small>
                {n(num(p.qty), lang)} {p.base_unit} · {fr ? "marge" : "هامش"} {p.margin_pct}%
              </small>
            </div>
            <strong>{money(num(rank === "qty" ? p.revenue : p.profit), lang)}</strong>
          </div>
        ))}
      </section>

      <section className="card">
        <div className="card-title">
          <h3>
            <Clock size={17} style={{ verticalAlign: "-3px" }} /> {fr ? "Heures de pointe" : "أوقات الذروة"}
          </h3>
        </div>
        {!hasHours && <p className="muted">{fr ? "Aucune vente sur cette période." : "لا مبيعات في هذه الفترة."}</p>}
        {hasHours && (
          <div style={{ display: "flex", alignItems: "flex-end", gap: 3, height: 90, direction: "ltr" }}>
            {data.hours.map((h: any) => (
              <div key={h.hour} title={`${h.hour}h — ${h.invoices}`} style={{ flex: 1, textAlign: "center" }}>
                <div
                  style={{
                    height: Math.max(2, (num(h.revenue) / maxRev) * 70),
                    background: data.peak_hours.some((p: any) => p.hour === h.hour) ? "var(--green)" : "var(--line)",
                    borderRadius: 3,
                  }}
                />
                <small style={{ fontSize: 8 }}>{h.hour}</small>
              </div>
            ))}
          </div>
        )}
        {data.peak_hours.map((p: any) => (
          <div key={p.hour} style={{ borderTop: "1px solid var(--line)", marginTop: 10, paddingTop: 8 }}>
            <b>
              {String(p.hour).padStart(2, "0")}h–{String((p.hour + 1) % 24).padStart(2, "0")}h
            </b>{" "}
            <small className="muted">
              {p.invoices} {fr ? "ventes" : "عملية"} · {money(num(p.revenue), lang)}
            </small>
            <br />
            <small>
              {fr ? "Produits demandés" : "الأكثر طلباً"}: {p.top_products.map((x: any) => `${x.label} (${n(num(x.qty), lang)})`).join(", ")}
            </small>
            <br />
            <small>
              {fr ? "Catégories" : "الفئات"}: {p.top_categories.map((x: any) => x.category).join(", ")}
            </small>
          </div>
        ))}
      </section>
    </div>
  );
}

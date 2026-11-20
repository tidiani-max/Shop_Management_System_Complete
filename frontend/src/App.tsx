import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { CustomerCreditModal, CustomerCreditPage } from "./CustomerCredit";
import { OwnerInsights } from "./Insights";
import { AddPackagingForm, BASE_UNITS, MoneyField, PackagingBuilder } from "./StockInputs";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Banknote,
  Bell,
  Box,
  Check,
  ChevronRight,
  CircleHelp,
  Cloud,
  CloudOff,
  Copy,
  CreditCard,
  Download,
  Eye,
  EyeOff,
  FileText,
  History,
  Home,
  Languages,
  KeyRound,
  LockKeyhole,
  LogOut,
  Menu,
  Minus,
  Package,
  Plus,
  Printer,
  ReceiptText,
  RefreshCw,
  Search,
  Settings,
  Share2,
  ShieldCheck,
  ShoppingBag,
  ShoppingCart,
  Store,
  TrendingUp,
  UserRound,
  Users,
  Wallet,
  X,
} from "lucide-react";
import { ApiError, api, errMsg, getToken, num, setToken, waitForServer, type SessionUser } from "./api";
import { AppCtx, modalStore, receiptStore, useApp, useFetch } from "./ctx";

type Lang = "fr" | "ar";
type Role = "owner" | "worker" | "admin";
type Screen = "welcome" | "login" | "signup" | "recovery" | "app" | "adminLogin";
type Page =
  | "dashboard"
  | "money"
  | "debts"
  | "stock"
  | "sales"
  | "history"
  | "alerts"
  | "team"
  | "credit"
  | "settings";
type WorkerAccount = {
  id: number;
  name: string;
  phone: string;
  username: string;
  password: string;
  recoveryCode: string;
  active: boolean;
  canCredit?: boolean;
  canReceiveStock?: boolean;
};

const copy = {
  fr: {
    appName: "Mon Commerce",
    by: "Une solution simple par DDS",
    welcome: "Votre boutique, plus claire chaque jour.",
    welcomeSub: "Suivez votre argent, vos ventes et votre stock même sans connexion.",
    create: "Créer ma boutique",
    signIn: "Se connecter",
    admin: "Accès DDS",
    phone: "Téléphone ou e-mail",
    password: "Mot de passe",
    remember: "Se souvenir de moi",
    forgot: "Mot de passe oublié ?",
    back: "Retour",
    continue: "Continuer",
    shopName: "Nom de la boutique",
    ownerName: "Nom complet",
    preferred: "Langue préférée",
    confirmPassword: "Confirmer le mot de passe",
    optional: "Facultatif",
    hello: "Bonjour,",
    today: "Aujourd’hui",
    connected: "Connecté",
    offline: "Mode hors ligne",
    synced: "Synchronisé il y a 2 min",
    received: "Argent reçu aujourd’hui",
    spent: "Argent dépensé aujourd’hui",
    available: "Argent disponible",
    balance: "Bilan du jour",
    included: "Ventes encaissées et dépenses payées",
    customersOwe: "Clients me doivent",
    iOwe: "Dettes à payer",
    people: "personnes",
    cash: "Espèces",
    mobile: "Mobile Money",
    stock: "Stock",
    products: "Produits",
    low: "Stock faible",
    out: "En rupture",
    best: "Produits les plus vendus",
    recent: "Activité récente",
    seeAll: "Tout voir",
    alerts: "Alertes",
    home: "Accueil",
    money: "Argent",
    debts: "Dettes",
    sales: "Vendre",
    history: "Historique",
    settings: "Réglages",
    newSale: "Nouvelle vente",
    search: "Rechercher un produit…",
    cart: "Panier",
    total: "Total",
    payment: "Mode de paiement",
    confirmSale: "Confirmer la vente",
    quick: "Vente rapide",
    add: "Ajouter",
    quantity: "Quantité",
    piece: "pièce",
    receipt: "Reçu",
    print: "Imprimer",
    download: "Télécharger PDF",
    share: "Partager",
    saleSuccess: "Vente enregistrée avec succès",
    newReceipt: "N° reçu",
    worker: "Employé",
    thanks: "Merci pour votre achat !",
    pending: "en attente",
    syncNow: "Synchroniser",
    pendingSync: "Transactions à synchroniser",
    income: "Entrées",
    expenses: "Sorties",
    addExpense: "Ajouter une dépense",
    description: "Description",
    amount: "Montant",
    category: "Catégorie",
    save: "Enregistrer",
    owedToMe: "On me doit",
    owedByMe: "Je dois",
    remaining: "Reste à payer",
    recordPayment: "Enregistrer un paiement",
    addDebt: "Ajouter une dette",
    currentStock: "Quantité actuelle",
    price: "Prix de vente",
    status: "État",
    addProduct: "Ajouter un produit",
    reports: "Rapports",
    notifications: "Notifications",
    markAll: "Tout marquer comme lu",
    onlineInfo: "Les données de la boutique sont à jour.",
    offlineInfo: "Les ventes restent sur cet appareil jusqu’au retour de la connexion.",
    signOut: "Se déconnecter",
    recoveryTitle: "Récupérer votre compte",
    sendCode: "Envoyer le code",
    codeTitle: "Entrez le code à 6 chiffres",
    codeHint: "Code de démonstration : 123456",
    verify: "Vérifier",
    newPassword: "Nouveau mot de passe",
    changed: "Mot de passe modifié",
    returnLogin: "Retour à la connexion",
    owner: "Propriétaire",
    daily: "Jour",
    weekly: "Semaine",
    monthly: "Mois",
    menu: "Menu",
    emptyCart: "Votre panier est vide",
    addItems: "Touchez un produit pour l’ajouter",
    counted: "Espèces comptées",
    expected: "Espèces attendues",
    difference: "Différence",
    review: "Examiner",
    reviewed: "Examiné",
    devices: "Appareils",
    backup: "Sauvegarde",
    healthy: "Opérationnel",
  },
  ar: {
    appName: "متجري",
    by: "حل بسيط من DDS",
    welcome: "متجرك أوضح كل يوم.",
    welcomeSub: "تابع أموالك ومبيعاتك ومخزونك، حتى دون اتصال بالإنترنت.",
    create: "إنشاء متجري",
    signIn: "تسجيل الدخول",
    admin: "دخول إدارة DDS",
    phone: "رقم الهاتف أو البريد الإلكتروني",
    password: "كلمة المرور",
    remember: "تذكرني",
    forgot: "هل نسيت كلمة المرور؟",
    back: "رجوع",
    continue: "متابعة",
    shopName: "اسم المتجر",
    ownerName: "الاسم الكامل",
    preferred: "اللغة المفضلة",
    confirmPassword: "تأكيد كلمة المرور",
    optional: "اختياري",
    hello: "مرحباً،",
    today: "اليوم",
    connected: "متصل",
    offline: "وضع عدم الاتصال",
    synced: "تمت المزامنة قبل دقيقتين",
    received: "المبالغ المستلمة اليوم",
    spent: "المبالغ المصروفة اليوم",
    available: "الأموال المتاحة",
    balance: "حصيلة اليوم",
    included: "المبيعات المقبوضة والمصروفات المدفوعة",
    customersOwe: "ديون العملاء لي",
    iOwe: "ديون يجب دفعها",
    people: "أشخاص",
    cash: "نقداً",
    mobile: "الدفع عبر الهاتف",
    stock: "المخزون",
    products: "المنتجات",
    low: "مخزون منخفض",
    out: "نفد المخزون",
    best: "المنتجات الأكثر مبيعاً",
    recent: "النشاط الأخير",
    seeAll: "عرض الكل",
    alerts: "التنبيهات",
    home: "الرئيسية",
    money: "الأموال",
    debts: "الديون",
    sales: "بيع",
    history: "السجل",
    settings: "الإعدادات",
    newSale: "عملية بيع جديدة",
    search: "ابحث عن منتج…",
    cart: "السلة",
    total: "المجموع",
    payment: "طريقة الدفع",
    confirmSale: "تأكيد البيع",
    quick: "بيع سريع",
    add: "إضافة",
    quantity: "الكمية",
    piece: "قطعة",
    receipt: "الإيصال",
    print: "طباعة",
    download: "تنزيل PDF",
    share: "مشاركة",
    saleSuccess: "تم تسجيل عملية البيع بنجاح",
    newReceipt: "رقم الإيصال",
    worker: "الموظف",
    thanks: "شكراً لتسوقكم معنا!",
    pending: "قيد الانتظار",
    syncNow: "مزامنة الآن",
    pendingSync: "عمليات تنتظر المزامنة",
    income: "المبالغ الداخلة",
    expenses: "المبالغ الخارجة",
    addExpense: "إضافة مصروف",
    description: "الوصف",
    amount: "المبلغ",
    category: "الفئة",
    save: "حفظ",
    owedToMe: "ديون لي",
    owedByMe: "ديون عليّ",
    remaining: "المبلغ المتبقي",
    recordPayment: "تسجيل دفعة",
    addDebt: "إضافة دين",
    currentStock: "الكمية الحالية",
    price: "سعر البيع",
    status: "الحالة",
    addProduct: "إضافة منتج",
    reports: "التقارير",
    notifications: "الإشعارات",
    markAll: "تحديد الكل كمقروء",
    onlineInfo: "بيانات المتجر محدّثة.",
    offlineInfo: "تبقى المبيعات على هذا الجهاز حتى عودة الاتصال.",
    signOut: "تسجيل الخروج",
    recoveryTitle: "استعادة حسابك",
    sendCode: "إرسال الرمز",
    codeTitle: "أدخل الرمز المكوّن من 6 أرقام",
    codeHint: "رمز العرض: 123456",
    verify: "تحقق",
    newPassword: "كلمة مرور جديدة",
    changed: "تم تغيير كلمة المرور",
    returnLogin: "العودة إلى تسجيل الدخول",
    owner: "المالك",
    daily: "يوم",
    weekly: "أسبوع",
    monthly: "شهر",
    menu: "القائمة",
    emptyCart: "سلة المشتريات فارغة",
    addItems: "اضغط على منتج لإضافته",
    counted: "النقد المحسوب",
    expected: "النقد المتوقع",
    difference: "الفرق",
    review: "مراجعة",
    reviewed: "تمت المراجعة",
    devices: "الأجهزة",
    backup: "النسخ الاحتياطي",
    healthy: "يعمل بشكل طبيعي",
  },
} as const;

const products = [
  {
    id: 1,
    fr: "Riz parfumé",
    ar: "أرز معطّر",
    price: 750,
    stock: 42,
    unitFr: "kg",
    unitAr: "كغ",
    color: "#F0E9D5",
  },
  {
    id: 2,
    fr: "Huile végétale",
    ar: "زيت نباتي",
    price: 1200,
    stock: 18,
    unitFr: "L",
    unitAr: "لتر",
    color: "#F9E8B7",
  },
  {
    id: 3,
    fr: "Sucre",
    ar: "سكر",
    price: 650,
    stock: 8,
    unitFr: "kg",
    unitAr: "كغ",
    color: "#E7EDF0",
  },
  {
    id: 4,
    fr: "Lait en poudre",
    ar: "حليب مجفف",
    price: 500,
    stock: 0,
    unitFr: "pièce",
    unitAr: "قطعة",
    color: "#E8F2EE",
  },
  {
    id: 5,
    fr: "Savon",
    ar: "صابون",
    price: 350,
    stock: 26,
    unitFr: "pièce",
    unitAr: "قطعة",
    color: "#E1EEF0",
  },
  {
    id: 6,
    fr: "Tomate concentrée",
    ar: "معجون الطماطم",
    price: 400,
    stock: 15,
    unitFr: "boîte",
    unitAr: "علبة",
    color: "#F4DDD8",
  },
];

function App() {
  const [lang, setLang] = useState<Lang>("fr");
  const [screen, setScreen] = useState<Screen>("welcome");
  const [role, setRole] = useState<Role>("owner");
  const [page, setPage] = useState<Page>("dashboard");
  const [online, setOnline] = useState(true);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [modal, setModal] = useState<string | null>(null);
  const [toast, setToast] = useState("");
  const [workers, setWorkers] = useState<WorkerAccount[]>([]);
  const [booting, setBooting] = useState(true);
  const [serverDown, setServerDown] = useState(false);
  const [session, setSession] = useState<SessionUser | null>(null);
  const [shop, setShop] = useState({ name: "", phone: "", city: "" });
  const [bump, setBump] = useState(0);
  const [receiptId, setReceiptId] = useState<number | null>(null);
  const [initialized, setInitialized] = useState(true);
  const t = copy[lang];
  const rtl = lang === "ar";
  const refresh = () => setBump((n) => n + 1);
  const loadShop = async () => {
    const st = await api.get("/setup/status");
    setInitialized(st.initialized);
    setShop({ name: st.shop_name || "", phone: st.shop_phone || "", city: st.shop_city || "" });
    return st;
  };
  const roleOf = (u: SessionUser): Role =>
    u.role === "OWNER" ? "owner" : u.role === "WORKER" ? "worker" : "admin";
  const onAuth = (token: string, user: SessionUser) => {
    setToken(token);
    setSession(user);
    setRole(roleOf(user));
    setPage("dashboard");
    setScreen("app");
    void loadShop();
  };
  const goApp = (_r?: Role) => setScreen("app");
  const notify = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(""), 2600);
  };
  const addWorker = (worker: WorkerAccount) => setWorkers((current) => [...current, worker]);
  const loadWorkers = async () => {
    try {
      const rows = await api.get("/workers");
      setWorkers(
        rows.map((w: any) => ({
          id: w.id,
          name: w.name,
          phone: w.phone || "",
          username: w.username,
          password: "",
          recoveryCode: "",
          active: w.active,
          canCredit: w.can_sell_credit,
          canReceiveStock: w.can_receive_stock,
        })),
      );
    } catch {
      /* not an owner */
    }
  };
  const logout = async () => {
    try {
      await api.post("/auth/logout");
    } catch {
      /* ignore */
    }
    setToken(null);
    setSession(null);
    setWorkers([]);
    setScreen("login"); // shared laptop: straight to the login / quick-switch screen
    setPage("dashboard");
  };

  useEffect(() => {
    let alive = true;
    (async () => {
      if (!(await waitForServer())) {
        if (alive) (setServerDown(true), setBooting(false));
        return;
      }
      try {
        const st = await loadShop();
        if (getToken() && st.initialized) {
          const me = await api.get<SessionUser>("/auth/me");
          if (alive) (setSession(me), setRole(roleOf(me)), setScreen("app"));
        } else if (!st.initialized && alive) setScreen("signup");
      } catch {
        setToken(null);
      }
      if (alive) setBooting(false);
    })();
    const expired = () => {
      setSession(null);
      setScreen("login");
    };
    window.addEventListener("shop:session-expired", expired);
    return () => {
      alive = false;
      window.removeEventListener("shop:session-expired", expired);
    };
  }, []);
  useEffect(() => {
    if (session?.role === "OWNER") void loadWorkers();
  }, [session, bump]);

  if (booting || serverDown)
    return (
      <div className="app" style={{ display: "grid", placeItems: "center", minHeight: "100vh" }}>
        <p style={{ textAlign: "center", padding: 24 }}>
          {serverDown
            ? "Le serveur local ne répond pas. Fermez puis relancez l’application. · الخادم المحلي لا يستجيب."
            : "Démarrage… · جارٍ التشغيل…"}
        </p>
      </div>
    );

  return (
    <AppCtx.Provider value={{ user: session, shop, bump, refresh }}>
    <div dir={rtl ? "rtl" : "ltr"} lang={lang} className={`app ${rtl ? "arabic" : ""}`}>
      {screen === "welcome" && (
        <Welcome t={t} lang={lang} setLang={setLang} setScreen={setScreen} />
      )}
      {screen === "login" && (
        <Login
          t={t}
          lang={lang}
          setLang={setLang}
          setScreen={setScreen}
          onAuth={onAuth}
        />
      )}
      {screen === "signup" && (
        <Signup
          t={t}
          lang={lang}
          setLang={setLang}
          setScreen={setScreen}
          onAuth={onAuth}
          initialized={initialized}
          addWorker={addWorker}
          notify={notify}
        />
      )}
      {screen === "recovery" && (
        <Recovery t={t} lang={lang} setScreen={setScreen} notify={notify} />
      )}
      {screen === "adminLogin" && (
        <AdminLogin t={t} lang={lang} setLang={setLang} setScreen={setScreen} onAuth={onAuth} />
      )}
      {screen === "app" && (
        <Shell
          t={t}
          lang={lang}
          setLang={setLang}
          role={role}
          setRole={setRole}
          page={page}
          setPage={setPage}
          online={online}
          setOnline={setOnline}
          notificationsOpen={notificationsOpen}
          setNotificationsOpen={setNotificationsOpen}
          modal={modal}
          setModal={setModal}
          notify={notify}
          workers={workers}
          setWorkers={setWorkers}
          addWorker={addWorker}
          logout={logout}
        />
      )}
      {toast && (
        <div className="toast">
          <span className="toast-check">
            <Check size={15} />
          </span>
          {toast}
        </div>
      )}
    </div>
    </AppCtx.Provider>
  );
}

function Brand({ light = false }: { light?: boolean }) {
  return (
    <div className={`brand ${light ? "brand-light" : ""}`}>
      <div className="brand-mark">
        <Store size={22} strokeWidth={2.2} />
      </div>
      <div>
        <strong>DDS</strong>
        <span>MON COMMERCE</span>
      </div>
    </div>
  );
}

function LanguageButton({
  lang,
  setLang,
  subtle = false,
}: {
  lang: Lang;
  setLang: (l: Lang) => void;
  subtle?: boolean;
}) {
  return (
    <button
      className={`language-btn ${subtle ? "subtle" : ""}`}
      onClick={() => setLang(lang === "fr" ? "ar" : "fr")}
    >
      <Languages size={17} />
      <span>{lang === "fr" ? "العربية" : "Français"}</span>
    </button>
  );
}

function Welcome({ t, lang, setLang, setScreen }: any) {
  return (
    <main className="auth-page">
      <div className="auth-top">
        <Brand />
        <LanguageButton lang={lang} setLang={setLang} />
      </div>
      <section className="welcome-card">
        <div className="welcome-copy">
          <span className="eyebrow">
            <ShieldCheck size={15} /> {t.by}
          </span>
          <h1>{t.welcome}</h1>
          <p>{t.welcomeSub}</p>
          <div className="welcome-actions">
            <button className="btn primary" onClick={() => setScreen("signup")}>
              {t.create}
              <ChevronRight size={18} />
            </button>
            <button className="btn secondary" onClick={() => setScreen("login")}>
              {t.signIn}
            </button>
          </div>
          <button className="text-btn admin-link" onClick={() => setScreen("adminLogin")}>
            <LockKeyhole size={14} />
            {t.admin}
          </button>
        </div>
        <div className="welcome-visual">
          <div className="phone-demo">
            <div className="demo-head">
              <span>Ma Boutique</span>
              <span className="live-dot" />
            </div>
            <p>Aujourd’hui</p>
            <strong>
              185 500 <small>FCFA</small>
            </strong>
            <div className="mini-grid">
              <span>
                Reçu<b>243 000</b>
              </span>
              <span>
                Dépensé<b>57 500</b>
              </span>
            </div>
            <div className="demo-row">
              <span>
                <ShoppingBag size={18} /> Nouvelle vente
              </span>
              <ChevronRight size={16} />
            </div>
          </div>
          <div className="floating-card card-one">
            <Cloud size={18} />
            <span>Synchronisé</span>
            <Check size={15} />
          </div>
          <div className="floating-card card-two">
            <TrendingUp size={18} />
            <span>+12% cette semaine</span>
          </div>
        </div>
      </section>
      <footer className="auth-footer">© 2026 Diawara Digital & Software · Bamako, Mali</footer>
    </main>
  );
}

function AuthLayout({ children, t, lang, setLang, setScreen, title, subtitle }: any) {
  return (
    <main className="form-page">
      <aside className="form-aside">
        <Brand light />
        <div>
          <h2>{t.welcome}</h2>
          <p>{t.welcomeSub}</p>
        </div>
        <small>Simple. Sûr. Toujours disponible.</small>
      </aside>
      <section className="form-main">
        <div className="form-top">
          <button className="icon-text" onClick={() => setScreen("welcome")}>
            <ArrowLeft size={18} />
            {t.back}
          </button>
          <LanguageButton lang={lang} setLang={setLang} subtle />
        </div>
        <div className="form-wrap">
          <h1>{title}</h1>
          <p className="muted">{subtitle}</p>
          {children}
        </div>
      </section>
    </main>
  );
}

function Login({ t, lang, setLang, setScreen, onAuth }: any) {
  const [show, setShow] = useState(false);
  const [selectedRole, setSelectedRole] = useState<Role>("owner");
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [people, setPeople] = useState<any[]>([]);
  const [pinUser, setPinUser] = useState<any | null>(null);
  useEffect(() => {
    api.get("/auth/switch-list").then(setPeople).catch(() => {});
  }, []);
  const submit = async (e: any) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const r = pinUser
        ? await api.post("/auth/pin-login", { user_id: pinUser.id, pin: password })
        : await api.post("/auth/login", { identifier, password, role: selectedRole });
      onAuth(r.token, r.user);
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  };
  const pick = (u: any) => {
    setSelectedRole(u.role === "OWNER" ? "owner" : "worker");
    setError("");
    setPassword("");
    if (u.has_pin) {
      setPinUser(u);
      setIdentifier(u.username);
    } else {
      setPinUser(null);
      setIdentifier(u.username);
    }
  };
  return (
    <AuthLayout
      t={t}
      lang={lang}
      setLang={setLang}
      setScreen={setScreen}
      title={t.signIn}
      subtitle={lang === "fr" ? "Heureux de vous revoir." : "سعداء بعودتك."}
    >
      <div className="role-switch">
        <button
          className={selectedRole === "owner" ? "active" : ""}
          onClick={() => setSelectedRole("owner")}
        >
          <UserRound size={17} />
          {t.owner}
        </button>
        <button
          className={selectedRole === "worker" ? "active" : ""}
          onClick={() => setSelectedRole("worker")}
        >
          <ShoppingBag size={17} />
          {t.worker}
        </button>
      </div>
      {people.length > 0 && (
        <div className="role-switch" style={{ flexWrap: "wrap", gap: 6, marginBottom: 12 }}>
          {people.map((u) => (
            <button
              type="button"
              key={u.id}
              className={identifier === u.username ? "active" : ""}
              onClick={() => pick(u)}
            >
              {u.role === "OWNER" ? <UserRound size={15} /> : <ShoppingBag size={15} />}
              {u.name}
            </button>
          ))}
        </div>
      )}
      <form onSubmit={submit}>
        {!pinUser && (
        <Field
          label={
            selectedRole === "worker"
              ? lang === "fr"
                ? "Identifiant employé"
                : "معرّف الموظف"
              : t.phone
          }
          placeholder={selectedRole === "worker" ? "EMP-1234" : "PRO-1234"}
          icon={<UserRound size={18} />}
          value={identifier}
          onChange={(e: any) => setIdentifier(e.target.value)}
        />
        )}
        <Field
          label={pinUser ? `PIN · ${pinUser.name}` : t.password}
          placeholder="••••••••"
          type={show ? "text" : "password"}
          icon={<LockKeyhole size={18} />}
          value={password}
          onChange={(e: any) => setPassword(e.target.value)}
          action={
            <button type="button" onClick={() => setShow(!show)}>
              {show ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          }
        />
        <div className="form-options">
          <label>
            <input type="checkbox" defaultChecked /> {t.remember}
          </label>
          <button type="button" onClick={() => setScreen("recovery")}>
            {t.forgot}
          </button>
        </div>
        {pinUser && (
          <button type="button" className="text-btn centered" onClick={() => setPinUser(null)}>
            {lang === "fr" ? "Utiliser le mot de passe" : "استخدام كلمة المرور"}
          </button>
        )}
        <button className="btn primary full" disabled={busy}>
          {t.signIn}
          <ArrowRight size={18} />
        </button>
        {error && (
          <p className="form-error">
            <AlertTriangle size={15} />
            {error}
          </p>
        )}
      </form>
    </AuthLayout>
  );
}

function Signup({ t, lang, setLang, setScreen, onAuth, initialized, addWorker, notify }: any) {
  const [step, setStep] = useState(1);
  const [f, setF] = useState({ shop: "", shopPhone: "", owner: "", pw: "", pw2: "", admin: "", admin2: "" });
  const [creds, setCreds] = useState<any>(null);
  const [err, setErr] = useState("");
  const set = (k: string) => (e: any) => setF((x) => ({ ...x, [k]: e.target.value }));
  if (initialized && step === 1 && !creds) {
    /* already configured: signup is only for first-run */
  }
  const [task, setTask] = useState<string | null>(null);
  const [completed, setCompleted] = useState<string[]>([]);
  const [saved, setSaved] = useState(false);
  const [createdWorker, setCreatedWorker] = useState<WorkerAccount | null>(null);
  const labels =
    lang === "fr"
      ? ["Boutique", "Propriétaire", "Accès", "Premiers pas"]
      : ["المتجر", "المالك", "بيانات الدخول", "الخطوات الأولى"];
  return (
    <AuthLayout
      t={t}
      lang={lang}
      setLang={setLang}
      setScreen={setScreen}
      title={lang === "fr" ? "Créons votre boutique" : "لننشئ متجرك"}
      subtitle={
        lang === "fr"
          ? "Quelques informations suffisent pour commencer."
          : "بعض المعلومات تكفي للبدء."
      }
    >
      <div className="steps">
        {labels.map((x, i) => (
          <div className={step >= i + 1 ? "done" : ""} key={x}>
            <span>{step > i + 1 ? <Check size={13} /> : i + 1}</span>
            <b>{x}</b>
          </div>
        ))}
      </div>
      {step === 1 && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setStep(2);
          }}
        >
          <Field
            label={t.shopName}
            placeholder={lang === "fr" ? "Ex. Alimentation Diawara" : "مثال: متجر دياوارا"}
            icon={<Store size={18} />}
            value={f.shop}
            onChange={set("shop")}
          />
          <Field
            label={lang === "fr" ? "Téléphone de la boutique" : "هاتف المتجر"}
            placeholder="+223 76 12 34 56"
            icon={<UserRound size={18} />}
            value={f.shopPhone}
            onChange={set("shopPhone")}
          />
          <button className="btn primary full">
            {t.continue}
            <ArrowRight size={18} />
          </button>
        </form>
      )}
      {step === 2 && (
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            if (f.pw.length < 6 || f.pw !== f.pw2) {
              setErr(lang === "fr" ? "Mot de passe: 6 caractères minimum, identique dans les deux champs." : "كلمة المرور: 6 أحرف على الأقل ومتطابقة.");
              return;
            }
            if (f.admin.length < 6 || f.admin !== f.admin2 || f.admin === f.pw) {
              setErr(lang === "fr" ? "Le mot de passe administrateur doit être confirmé, de 6 caractères minimum et différent du mot de passe de connexion." : "يجب تأكيد كلمة مرور المدير وأن تختلف عن كلمة مرور الدخول.");
              return;
            }
            try {
              const r = await api.post("/setup", {
                shop_name: f.shop,
                shop_phone: f.shopPhone,
                owner_name: f.owner,
                owner_password: f.pw,
                admin_password: f.admin,
              });
              setToken(r.token);
              setCreds({ token: r.token, user: r.user, recovery: r.recovery_code });
              setErr("");
              setStep(3);
            } catch (ex) {
              setErr(errMsg(ex));
            }
          }}
        >
          <Field
            label={t.ownerName}
            placeholder={lang === "fr" ? "Mamadou Diawara" : "مامادو دياوارا"}
            icon={<UserRound size={18} />}
            value={f.owner}
            onChange={set("owner")}
          />
          <Field
            label={t.password}
            placeholder="••••••••"
            type="password"
            icon={<LockKeyhole size={18} />}
            value={f.pw}
            onChange={set("pw")}
          />
          <Field
            label={t.confirmPassword}
            placeholder="••••••••"
            type="password"
            icon={<LockKeyhole size={18} />}
            value={f.pw2}
            onChange={set("pw2")}
          />
          <Field
            label={lang === "fr" ? "Mot de passe administrateur (prix, annulations)" : "كلمة مرور المدير (الأسعار والإلغاء)"}
            placeholder="••••••••"
            type="password"
            icon={<ShieldCheck size={18} />}
            value={f.admin}
            onChange={set("admin")}
          />
          <Field
            label={lang === "fr" ? "Confirmer le mot de passe administrateur" : "تأكيد كلمة مرور المدير"}
            placeholder="••••••••"
            type="password"
            icon={<ShieldCheck size={18} />}
            value={f.admin2}
            onChange={set("admin2")}
          />
          <p className="muted">
            {lang === "fr"
              ? "Vous seul détenez ce mot de passe : il est exigé pour modifier un prix ou annuler une facture."
              : "أنت وحدك تملك كلمة المرور هذه: مطلوبة لتعديل سعر أو إلغاء فاتورة."}
          </p>
          {err && <p className="form-error"><AlertTriangle size={15} />{err}</p>}
          <button className="btn primary full">
            {t.continue}
            <ArrowRight size={18} />
          </button>
        </form>
      )}
      {step === 3 && (
        <div className="credentials-step">
          <CredentialsCard
            lang={lang}
            title={lang === "fr" ? "Compte propriétaire créé" : "تم إنشاء حساب المالك"}
            name={creds?.user?.name || f.owner}
            username={creds?.user?.username || ""}
            password={f.pw}
            recoveryCode={creds?.recovery || ""}
            notify={notify}
          />
          <label className="saved-check">
            <input type="checkbox" checked={saved} onChange={(e) => setSaved(e.target.checked)} />
            <span>
              {lang === "fr"
                ? "J’ai écrit ou sauvegardé ces informations dans un endroit sûr."
                : "لقد كتبت هذه المعلومات أو حفظتها في مكان آمن."}
            </span>
          </label>
          <button className="btn primary full" disabled={!saved} onClick={() => setStep(4)}>
            {t.continue}
            <ArrowRight size={18} />
          </button>
        </div>
      )}
      {step === 4 && task === "worker" && !createdWorker && (
        <WorkerSetupForm
          t={t}
          lang={lang}
          cancel={() => setTask(null)}
          onCreated={(worker: WorkerAccount) => {
            addWorker(worker);
            setCreatedWorker(worker);
            setCompleted((items) => [...items, "worker"]);
          }}
        />
      )}
      {step === 4 && task === "worker" && createdWorker && (
        <div className="credentials-step">
          <CredentialsCard
            lang={lang}
            title={lang === "fr" ? "Compte employé créé" : "تم إنشاء حساب الموظف"}
            name={createdWorker.name}
            username={createdWorker.username}
            password={createdWorker.password}
            recoveryCode={createdWorker.recoveryCode}
            notify={notify}
          />
          <p className="credentials-help">
            {lang === "fr"
              ? "Remettez ces informations à l’employé. Il pourra changer son mot de passe et récupérer son compte."
              : "سلّم هذه المعلومات للموظف. يمكنه تغيير كلمة المرور واستعادة حسابه."}
          </p>
          <button
            className="btn primary full"
            onClick={() => {
              setCreatedWorker(null);
              setTask(null);
            }}
          >
            <Check size={18} />
            {lang === "fr" ? "Terminer" : "إنهاء"}
          </button>
        </div>
      )}
      {step === 4 && task === "product" && (
        <SetupTaskForm
          t={t}
          lang={lang}
          type="product"
          cancel={() => setTask(null)}
          done={() => {
            setCompleted((items) => [...items, "product"]);
            setTask(null);
            notify(lang === "fr" ? "Premier produit ajouté" : "تمت إضافة المنتج الأول");
          }}
        />
      )}
      {step === 4 && task === "stock" && (
        <SetupTaskForm
          t={t}
          lang={lang}
          type="stock"
          cancel={() => setTask(null)}
          done={() => {
            setCompleted((items) => [...items, "stock"]);
            setTask(null);
            notify(lang === "fr" ? "Stock initial enregistré" : "تم تسجيل المخزون الأولي");
          }}
        />
      )}
      {step === 4 && !task && (
        <div className="onboarding-list">
          <OnboardItem
            icon={<Users />}
            title={lang === "fr" ? "Ajouter un employé" : "إضافة موظف"}
            detail={
              completed.includes("worker")
                ? lang === "fr"
                  ? "Employé ajouté"
                  : "تمت إضافة الموظف"
                : t.optional
            }
            completed={completed.includes("worker")}
            onClick={() => setTask("worker")}
          />
          <OnboardItem
            icon={<Package />}
            title={lang === "fr" ? "Ajouter vos premiers produits" : "إضافة المنتجات الأولى"}
            detail={
              completed.includes("product")
                ? lang === "fr"
                  ? "Premier produit ajouté"
                  : "تمت إضافة المنتج الأول"
                : lang === "fr"
                  ? "Vous pourrez continuer plus tard"
                  : "يمكنك المتابعة لاحقاً"
            }
            completed={completed.includes("product")}
            onClick={() => setTask("product")}
          />
          <OnboardItem
            icon={<Box />}
            title={lang === "fr" ? "Saisir le stock initial" : "إدخال المخزون الأولي"}
            detail={
              completed.includes("stock")
                ? lang === "fr"
                  ? "Stock enregistré"
                  : "تم تسجيل المخزون"
                : t.optional
            }
            completed={completed.includes("stock")}
            onClick={() => setTask("stock")}
          />
          <button className="btn primary full" onClick={() => onAuth(creds.token, creds.user)}>
            {lang === "fr" ? "Ouvrir mon tableau de bord" : "فتح لوحة التحكم"}
            <ArrowRight size={18} />
          </button>
        </div>
      )}
    </AuthLayout>
  );
}

function OnboardItem({ icon, title, detail, onClick, completed }: any) {
  return (
    <button className={`onboard-item ${completed ? "completed" : ""}`} onClick={onClick}>
      <span>{icon}</span>
      <div>
        <b>{title}</b>
        <small>{detail}</small>
      </div>
      {completed ? <Check size={18} /> : <ChevronRight size={18} />}
    </button>
  );
}

function CredentialsCard({ lang, title, name, username, password, recoveryCode, notify }: any) {
  const copyValue = (value: string) => {
    void navigator.clipboard?.writeText(value);
    notify(lang === "fr" ? "Copié" : "تم النسخ");
  };
  const downloadAccessCard = () => {
    const content = [
      "DDS MON COMMERCE",
      title,
      "",
      `${lang === "fr" ? "Nom" : "الاسم"}: ${name}`,
      `${lang === "fr" ? "Identifiant" : "المعرّف"}: ${username}`,
      `${lang === "fr" ? "Mot de passe temporaire" : "كلمة المرور المؤقتة"}: ${password}`,
      `${lang === "fr" ? "Code de récupération" : "رمز الاسترداد"}: ${recoveryCode}`,
      "",
      lang === "fr"
        ? "Conservez cette fiche dans un endroit sûr."
        : "احتفظ بهذه البطاقة في مكان آمن.",
    ].join("\n");
    const url = URL.createObjectURL(new Blob([content], { type: "text/plain;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `acces-${username}.txt`;
    link.click();
    URL.revokeObjectURL(url);
    notify(lang === "fr" ? "Fiche d’accès téléchargée" : "تم تنزيل بطاقة الدخول");
  };
  return (
    <div className="credentials-card">
      <div className="credential-success">
        <Check size={20} />
      </div>
      <h3>{title}</h3>
      <p>{name}</p>
      <CredentialLine
        lang={lang}
        label={lang === "fr" ? "Identifiant" : "المعرّف"}
        value={username}
        copy={() => copyValue(username)}
      />
      <CredentialLine
        lang={lang}
        label={lang === "fr" ? "Mot de passe temporaire" : "كلمة المرور المؤقتة"}
        value={password}
        copy={() => copyValue(password)}
      />
      <CredentialLine
        lang={lang}
        label={lang === "fr" ? "Code de récupération" : "رمز الاسترداد"}
        value={recoveryCode}
        copy={() => copyValue(recoveryCode)}
        important
      />
      <button className="btn secondary full" onClick={downloadAccessCard}>
        <Download size={17} />
        {lang === "fr" ? "Télécharger la fiche d’accès" : "تنزيل بطاقة الدخول"}
      </button>
    </div>
  );
}

function CredentialLine({ label, value, copy, important }: any) {
  return (
    <div className={`credential-line ${important ? "important" : ""}`}>
      <span>{label}</span>
      <b dir="ltr">{value}</b>
      <button onClick={copy} aria-label="Copy">
        <Copy size={16} />
      </button>
    </div>
  );
}

function WorkerSetupForm({ t, lang, cancel, onCreated }: any) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [canCredit, setCanCredit] = useState(false);
  const [err, setErr] = useState("");
  const create = async (e: any) => {
    e.preventDefault();
    try {
      const w = await api.post("/workers", { name, phone, can_sell_credit: canCredit });
      onCreated({
        id: w.id,
        name: w.name,
        phone: w.phone || "",
        username: w.username,
        password: w.password,
        recoveryCode: w.recovery_code,
        active: true,
      });
    } catch (ex) {
      setErr(errMsg(ex));
    }
  };
  return (
    <form className="setup-form" onSubmit={create}>
      <div className="setup-heading">
        <button type="button" onClick={cancel}>
          <ArrowLeft size={18} />
        </button>
        <div>
          <h3>{lang === "fr" ? "Ajouter un employé" : "إضافة موظف"}</h3>
          <p>
            {lang === "fr"
              ? "L’employé sera lié à votre boutique."
              : "سيتم ربط الموظف بمتجرك."}
          </p>
        </div>
      </div>
      <Field
        label={t.ownerName}
        placeholder={lang === "fr" ? "Nom de l’employé" : "اسم الموظف"}
        icon={<UserRound size={18} />}
        value={name}
        onChange={(e: any) => setName(e.target.value)}
      />
      <Field
        label={lang === "fr" ? "Téléphone de l’employé" : "هاتف الموظف"}
        placeholder="+223 70 00 00 00"
        icon={<UserRound size={18} />}
        value={phone}
        onChange={(e: any) => setPhone(e.target.value)}
      />
      {err && <p className="form-error"><AlertTriangle size={15} />{err}</p>}
      <label className="permission-toggle">
        <span>
          <b>{lang === "fr" ? "Autoriser les ventes à crédit" : "السماح بالبيع بالدين"}</b>
          <small>
            {lang === "fr"
              ? "Le propriétaire pourra modifier cette autorisation."
              : "يمكن للمالك تغيير هذا الإذن لاحقاً."}
          </small>
        </span>
        <input
          type="checkbox"
          checked={canCredit}
          onChange={(e) => setCanCredit(e.target.checked)}
        />
      </label>
      <div className="modal-actions">
        <button type="button" className="btn secondary" onClick={cancel}>
          {t.back}
        </button>
        <button className="btn primary">
          <Plus size={17} />
          {lang === "fr" ? "Créer le compte" : "إنشاء الحساب"}
        </button>
      </div>
    </form>
  );
}

function SetupTaskForm({ t, lang, type, cancel, done }: any) {
  const [v, setV] = useState({ name: "", price: "", qty: "" });
  const [err, setErr] = useState("");
  return (
    <form
      className="setup-form"
      onSubmit={async (e) => {
        e.preventDefault();
        try {
          await api.post("/products", {
            name_fr: v.name,
            price: v.price,
            base_unit: "Unité",
            initial_stock: v.qty || null,
          });
          done();
        } catch (ex) {
          setErr(errMsg(ex));
        }
      }}
    >
      <div className="setup-heading">
        <button type="button" onClick={cancel}>
          <ArrowLeft size={18} />
        </button>
        <div>
          <h3>
            {type === "product" ? t.addProduct : lang === "fr" ? "Stock initial" : "المخزون الأولي"}
          </h3>
          <p>
            {lang === "fr"
              ? "Vous pourrez compléter ces informations plus tard."
              : "يمكنك إكمال هذه المعلومات لاحقاً."}
          </p>
        </div>
      </div>
      <Field
        label={lang === "fr" ? "Nom du produit" : "اسم المنتج"}
        placeholder={lang === "fr" ? "Ex. Farine" : "مثال: دقيق"}
        icon={<Package size={18} />}
        value={v.name}
        onChange={(e: any) => setV({ ...v, name: e.target.value })}
      />
      <div className="form-grid">
        <Field
          label={t.price}
          placeholder="0"
          type="number"
          icon={<Banknote size={18} />}
          value={v.price}
          onChange={(e: any) => setV({ ...v, price: e.target.value })}
        />
        <Field
          label={t.quantity}
          placeholder="0"
          type="number"
          step=".001"
          icon={<Box size={18} />}
          value={v.qty}
          onChange={(e: any) => setV({ ...v, qty: e.target.value })}
        />
      </div>
      {err && <p className="form-error"><AlertTriangle size={15} />{err}</p>}
      <div className="modal-actions">
        <button type="button" className="btn secondary" onClick={cancel}>
          {t.back}
        </button>
        <button className="btn primary">
          {t.save}
          <Check size={17} />
        </button>
      </div>
    </form>
  );
}

function Recovery({ t, lang, setScreen, notify }: any) {
  const [step, setStep] = useState(1);
  const [code, setCode] = useState("");
  const [role, setRole] = useState<Role>("owner");
  const [method, setMethod] = useState("contact");
  const [error, setError] = useState("");
  const [expired, setExpired] = useState(false);
  const [identifier, setIdentifier] = useState("");
  const [targetWorkerId, setTargetWorkerId] = useState<number | null>(null);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  return (
    <main className="recovery-page">
      <div className="recovery-card">
        <Brand />
        <button
          className="icon-text recovery-back"
          onClick={() => (step === 1 ? setScreen("login") : setStep(step - 1))}
        >
          <ArrowLeft size={18} />
          {t.back}
        </button>
        <div className="recovery-icon">{step === 4 ? <Check /> : <LockKeyhole />}</div>
        <h1>
          {step === 1
            ? t.recoveryTitle
            : step === 2
              ? t.codeTitle
              : step === 3
                ? t.newPassword
                : t.changed}
        </h1>
        {step === 1 && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (!identifier.trim()) return;
              setError("");
              setStep(2);
            }}
          >
            <div className="role-switch recovery-role">
              <button
                type="button"
                className={role === "owner" ? "active" : ""}
                onClick={() => setRole("owner")}
              >
                <UserRound size={16} />
                {t.owner}
              </button>
              <button
                type="button"
                className={role === "worker" ? "active" : ""}
                onClick={() => setRole("worker")}
              >
                <ShoppingBag size={16} />
                {t.worker}
              </button>
            </div>
                        <Field
              label={langLabel(t, "Identifiant ou téléphone", "المعرّف أو الهاتف")}
              placeholder={role === "owner" ? "PRO-1234" : "EMP-1234"}
              icon={<UserRound size={18} />}
              value={identifier}
              onChange={(e: any) => setIdentifier(e.target.value)}
            />
            {error && (
              <p className="form-error">
                <AlertTriangle size={15} />
                {error}
              </p>
            )}
            <button className="btn primary full">{t.sendCode}</button>
          </form>
        )}
        {step === 2 && (
          <div>
            <p className="muted">
              {langLabel(t, "Saisissez le code de récupération remis lors de la création du compte.", "أدخل رمز الاسترداد الذي تم تسليمه عند إنشاء الحساب.")}
            </p>
            <Field
              label={langLabel(t, "Code de récupération", "رمز الاسترداد")}
              placeholder={role === "owner" ? "PRO-XXXX-XX" : "WK-XXXX-XX"}
              icon={<KeyRound size={18} />}
              value={code}
              onChange={(e: any) => setCode(e.target.value)}
            />
            <button
              className="btn primary full"
              onClick={() => {
                if (code.trim().length < 6) return;
                setError("");
                setStep(3);
              }}
            >
              {t.verify}
            </button>
          </div>
        )}
        {step === 3 && (
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              if (newPassword.length < 6 || newPassword !== confirmPassword) {
                setError(
                  lang === "fr"
                    ? "Utilisez au moins 6 caractères et confirmez le même mot de passe."
                    : "استخدم 6 أحرف على الأقل وأكد كلمة المرور نفسها.",
                );
                return;
              }
              try {
                await api.post("/auth/recover", {
                  identifier,
                  recovery_code: code.trim(),
                  new_password: newPassword,
                });
                setError("");
                setStep(4);
              } catch (ex) {
                setError(errMsg(ex));
              }
            }}
          >
            <Field
              label={t.newPassword}
              placeholder="••••••••"
              type="password"
              icon={<LockKeyhole size={18} />}
              value={newPassword}
              onChange={(e: any) => setNewPassword(e.target.value)}
            />
            <Field
              label={t.confirmPassword}
              placeholder="••••••••"
              type="password"
              icon={<LockKeyhole size={18} />}
              value={confirmPassword}
              onChange={(e: any) => setConfirmPassword(e.target.value)}
            />
            {error && (
              <p className="form-error">
                <AlertTriangle size={15} />
                {error}
              </p>
            )}
            <button className="btn primary full">{t.save}</button>
          </form>
        )}
        {step === 4 && (
          <>
            <p className="muted">
              {langLabel(
                t,
                "Vous pouvez maintenant vous connecter avec votre nouveau mot de passe.",
                "يمكنك الآن تسجيل الدخول بكلمة المرور الجديدة.",
              )}
            </p>
            <button className="btn primary full" onClick={() => setScreen("login")}>
              {t.returnLogin}
            </button>
          </>
        )}
      </div>
    </main>
  );
}

function langLabel(t: any, fr: string, ar: string) {
  return t.home === "Accueil" ? fr : ar;
}

function AdminLogin({ t, lang, setLang, setScreen, onAuth }: any) {
  const [id, setId] = useState("");
  const [pw, setPw] = useState("");
  const [error, setError] = useState("");
  return (
    <AuthLayout
      t={t}
      lang={lang}
      setLang={setLang}
      setScreen={setScreen}
      title="DDS Administration"
      subtitle={
        lang === "fr" ? "Accès technique sécurisé et audité." : "دخول تقني آمن وخاضع للتدقيق."
      }
    >
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          try {
            const r = await api.post("/auth/login", { identifier: id, password: pw, role: "admin" });
            onAuth(r.token, r.user);
          } catch (err) {
            setError(errMsg(err));
          }
        }}
      >
        <Field
          label={t.phone}
          placeholder="dds-admin"
          icon={<UserRound size={18} />}
          value={id}
          onChange={(e: any) => setId(e.target.value)}
        />
        <Field
          label={t.password}
          placeholder="••••••••"
          type="password"
          icon={<LockKeyhole size={18} />}
          value={pw}
          onChange={(e: any) => setPw(e.target.value)}
        />
        {error && <p className="form-error"><AlertTriangle size={15} />{error}</p>}
        <button className="btn primary full">
          {t.signIn}
          <ShieldCheck size={18} />
        </button>
      </form>
      <div className="secure-note">
        <ShieldCheck size={18} />
        <span>
          {lang === "fr"
            ? "Chaque accès aux données commerciales est enregistré."
            : "يتم تسجيل كل دخول إلى البيانات التجارية."}
        </span>
      </div>
    </AuthLayout>
  );
}

function Field({ label, icon, action, ...props }: any) {
  return (
    <label className="field">
      <span>{label}</span>
      <div className="input-wrap">
        {icon}
        <input required {...props} />
        {action}
      </div>
    </label>
  );
}

function Shell({
  t,
  lang,
  setLang,
  role,
  setRole,
  page,
  setPage,
  online,
  setOnline,
  notificationsOpen,
  setNotificationsOpen,
  modal,
  setModal,
  notify,
  workers,
  setWorkers,
  addWorker,
  currentWorker,
  logout,
}: any) {
  const isAdmin = role === "admin";
  const { user: me, shop } = useApp();
  const { data: dash } = useFetch<any>(role === "owner" ? "/dashboard" : null);
  const alertCount: number = dash?.low_stock?.length ?? 0;
  const initials = (me?.name || "?").split(" ").map((x: string) => x[0]).slice(0, 2).join("").toUpperCase();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const nav: { id: Page; label: string; icon: any }[] = isAdmin
    ? [
        { id: "dashboard", label: t.home, icon: Home },
        { id: "stock", label: lang === "fr" ? "Boutiques" : "المتاجر", icon: Store },
        { id: "history", label: lang === "fr" ? "Journaux" : "السجلات", icon: FileText },
        { id: "settings", label: t.settings, icon: Settings },
      ]
    : role === "worker"
      ? [
          { id: "dashboard", label: t.home, icon: Home },
          { id: "sales", label: t.sales, icon: ShoppingCart },
          { id: "stock", label: t.stock, icon: Package },
          { id: "credit", label: lang === "fr" ? "Crédits clients" : "ديون العملاء", icon: Users },
          { id: "history", label: t.history, icon: History },
          { id: "settings", label: t.settings, icon: Settings },
        ]
      : [
          { id: "dashboard", label: t.home, icon: Home },
          { id: "money", label: t.money, icon: Wallet },
          { id: "debts", label: t.debts, icon: Users },
          { id: "stock", label: t.stock, icon: Package },
          { id: "team", label: lang === "fr" ? "Équipe" : "الفريق", icon: Users },
          { id: "history", label: t.reports, icon: FileText },
          { id: "alerts", label: t.alerts, icon: AlertTriangle },
          { id: "settings", label: t.settings, icon: Settings },
        ];
  return (
    <div className="shell">
      <aside className="sidebar">
        <Brand light />
        <div className="shop-chip">
          <div>{isAdmin ? <ShieldCheck /> : <Store />}</div>
          <span>
            <b>{isAdmin ? "DDS Admin" : shop.name}</b>
            <small>{isAdmin ? t.admin : role === "owner" ? t.owner : t.worker}</small>
          </span>
        </div>
        <nav>
          {nav.map((n) => (
            <button
              key={n.id}
              className={page === n.id ? "active" : ""}
              onClick={() => setPage(n.id)}
            >
              <n.icon size={19} />
              <span>{n.label}</span>
              {n.id === "alerts" && alertCount > 0 && <em>{alertCount}</em>}
            </button>
          ))}
        </nav>
        <div className="side-bottom">
          <button type="button">
            <span className="status-dot" />
            {lang === "fr" ? "Local · hors ligne" : "محلي · دون إنترنت"}
          </button>
          {!isAdmin && (
            <button onClick={logout}>
              <UserRound size={18} />
              {lang === "fr" ? "Changer d’utilisateur" : "تبديل المستخدم"}
            </button>
          )}
          <button onClick={logout}>
            <LogOut size={18} />
            {t.signOut}
          </button>
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <div className="mobile-brand">
            <Brand />
          </div>
          <div className="top-title">
            <h2>{nav.find((n) => n.id === page)?.label}</h2>
            <span>{isAdmin ? "Console support" : shop.name}</span>
          </div>
          <div className="top-actions">
            <button
              className="connection-pill"
              type="button"
            >
              {online ? <Cloud size={16} /> : <CloudOff size={16} />}
              <span>{online ? t.connected : t.offline}</span>
            </button>
            <LanguageButton lang={lang} setLang={setLang} subtle />
            {!isAdmin && (
              <button
                className="notification-btn"
                onClick={() => setNotificationsOpen(!notificationsOpen)}
              >
                <Bell size={20} />
                {alertCount > 0 && <span>{alertCount}</span>}
              </button>
            )}
            <div className="avatar">{isAdmin ? "AD" : initials}</div>
          </div>
        </header>
        {!online && (
          <div className="offline-banner">
            <CloudOff size={18} />
            <span>
              <b>{t.offline}.</b> {t.offlineInfo}
            </span>
            <strong>2 {t.pending}</strong>
          </div>
        )}
        <div className="content">
          {isAdmin ? (
            <AdminDashboard t={t} page={page} setModal={setModal} notify={notify} />
          ) : role === "worker" ? (
            <WorkerContent
              t={t}
              lang={lang}
              page={page}
              setPage={setPage}
              online={online}
              setModal={setModal}
              notify={notify}
              worker={me}
            />
          ) : (
            <OwnerContent
              t={t}
              lang={lang}
              page={page}
              setPage={setPage}
              setModal={setModal}
              notify={notify}
              workers={workers}
              setWorkers={setWorkers}
            />
          )}
        </div>
      </main>
      <nav className="bottom-nav">
        {(role === "owner" ? nav.slice(0, 4) : nav).map((n) => (
          <button
            key={n.id}
            className={page === n.id ? "active" : ""}
            onClick={() => setPage(n.id)}
          >
            <n.icon size={20} />
            <span>{n.label}</span>
          </button>
        ))}
        {role === "owner" && (
          <button
            className={nav.slice(4).some((item) => item.id === page) ? "active" : ""}
            onClick={() => setMobileMenuOpen(true)}
          >
            <Menu size={20} />
            <span>{t.menu}</span>
          </button>
        )}
      </nav>
      {mobileMenuOpen && (
        <>
          <div
            className="drawer-backdrop mobile-menu-backdrop"
            onClick={() => setMobileMenuOpen(false)}
          />
          <aside className="mobile-menu-sheet">
            <div className="drawer-head">
              <div>
                <h2>{t.menu}</h2>
                <span>{shop.name}</span>
              </div>
              <button onClick={() => setMobileMenuOpen(false)}>
                <X />
              </button>
            </div>
            <div className="mobile-menu-grid">
              {nav.map((item) => (
                <button
                  key={item.id}
                  className={page === item.id ? "active" : ""}
                  onClick={() => {
                    setPage(item.id);
                    setMobileMenuOpen(false);
                  }}
                >
                  <item.icon size={20} />
                  <span>{item.label}</span>
                  {item.id === "alerts" && alertCount > 0 && <em>{alertCount}</em>}
                </button>
              ))}
            </div>
          </aside>
        </>
      )}
      {notificationsOpen && (
        <NotificationPanel
          t={t}
          lang={lang}
          close={() => setNotificationsOpen(false)}
          notify={notify}
        />
      )}
      {modal && (
        <Modal
          type={modal}
          t={t}
          lang={lang}
          close={() => setModal(null)}
          notify={notify}
          addWorker={addWorker}
          setModal={setModal}
        />
      )}
    </div>
  );
}

function OwnerContent({ t, lang, page, setPage, setModal, notify, workers, setWorkers }: any) {
  if (page === "dashboard") return <OwnerDashboard t={t} lang={lang} setPage={setPage} />;
  if (page === "money") return <MoneyPage t={t} lang={lang} setModal={setModal} notify={notify} />;
  if (page === "debts") return <DebtsPage t={t} lang={lang} setModal={setModal} />;
  if (page === "stock") return <StockPage t={t} lang={lang} setModal={setModal} />;
  if (page === "team")
    return (
      <TeamPage
        t={t}
        lang={lang}
        workers={workers}
        setWorkers={setWorkers}
        setModal={setModal}
        notify={notify}
      />
    );
  if (page === "history") return <ReportsPage t={t} lang={lang} notify={notify} setModal={setModal} />;
  if (page === "alerts") return <AlertsPage t={t} lang={lang} notify={notify} />;
  return <OwnerSettingsPage t={t} lang={lang} setPage={setPage} setModal={setModal} />;
}

function OwnerDashboard({ t, lang, setPage }: any) {
  const { user } = useApp();
  const [period, setPeriod] = useState("day");
  const { data: d } = useFetch<any>(`/dashboard?period=${period}`);
  if (!d) return <div className="page-heading"><p>…</p></div>;
  const kindTitle = (k: string, note: string | null) =>
    k === "SALE"
      ? `${lang === "fr" ? "Vente" : "عملية بيع"} ${note || ""}`
      : k === "DEBT_REPAYMENT"
        ? lang === "fr" ? "Paiement de dette" : "دفعة دين"
        : k === "EXPENSE"
          ? note || (lang === "fr" ? "Dépense" : "مصروف")
          : note || k;
  return (
    <>
      <div className="page-heading">
        <div>
          <p>{t.hello}</p>
          <h1>{user?.name}</h1>
          <span>{formatDate(lang)}</span>
        </div>
        <PeriodFilter t={t} period={period} setPeriod={setPeriod} />
      </div>
      <div className="metrics-grid">
        <Metric
          icon={<ArrowDownIcon />}
          label={t.received}
          amount={num(d.received)}
          lang={lang}
          tone="green"
          note={`${d.received_ops} ${lang === "fr" ? "opérations" : "عملية"}`}
        />
        <Metric
          icon={<ArrowUpIcon />}
          label={t.spent}
          amount={num(d.spent)}
          lang={lang}
          tone="orange"
          note={`${d.expense_count} ${lang === "fr" ? "dépenses" : "مصروفات"}`}
        />
        <Metric
          icon={<Wallet />}
          label={t.available}
          amount={num(d.available)}
          lang={lang}
          tone="navy"
          split={`${t.cash}: ${money(num(d.cash), lang)} · ${t.mobile}: ${money(num(d.mobile), lang)}`}
        />
        <Metric
          icon={<TrendingUp />}
          label={t.balance}
          amount={num(d.balance)}
          lang={lang}
          tone="blue"
          note={t.included}
        />
      </div>
      <div className="dashboard-grid">
        <section className="card debts-card">
          <CardTitle title={t.debts} action={t.seeAll} onClick={() => setPage("debts")} />
          <div className="debt-row positive">
            <span>
              <Users size={20} />
              <b>{t.customersOwe}</b>
              <small>{d.receivable_people} {t.people}</small>
            </span>
            <strong>{money(num(d.receivables), lang)}</strong>
          </div>
          <div className="debt-row negative">
            <span>
              <CreditCard size={20} />
              <b>{t.iOwe}</b>
              <small>{d.payable_people} {t.people}</small>
            </span>
            <strong>{money(num(d.payables), lang)}</strong>
          </div>
        </section>
        <section className="card stock-card">
          <CardTitle title={t.stock} action={t.seeAll} onClick={() => setPage("stock")} />
          <div className="stock-stats">
            <span>
              <b>{d.products_count}</b>
              <small>{t.products}</small>
            </span>
            <span className="warn">
              <b>{d.low_count}</b>
              <small>{t.low}</small>
            </span>
            <span className="danger">
              <b>{d.out_count}</b>
              <small>{t.out}</small>
            </span>
          </div>
          {d.low_stock[0] && (
            <div className="stock-alert">
              <AlertTriangle size={17} />
              <span>
                {lang === "fr"
                  ? `Stock bas : ${d.low_stock[0].name_fr} (${d.low_stock[0].stock_qty} ${d.low_stock[0].base_unit})`
                  : `مخزون منخفض: ${d.low_stock[0].name_ar || d.low_stock[0].name_fr}`}
              </span>
            </div>
          )}
        </section>
        <section className="card best-card">
          <CardTitle title={t.best} action={t.seeAll} />
          {d.best_sellers.map((p: any, i: number) => (
            <div className="rank-row" key={i}>
              <span className="rank">{i + 1}</span>
              <div>
                <b>{p.label}</b>
                <small>
                  {formatNumber(num(p.qty), lang)} {t.piece}
                </small>
              </div>
              <strong>{money(num(p.revenue), lang)}</strong>
            </div>
          ))}
        </section>
        <section className="card activity-card">
          <CardTitle title={t.recent} action={t.seeAll} onClick={() => setPage("history")} />
          {d.recent.map((r: any, i: number) => (
            <Activity
              key={i}
              icon={r.kind === "SALE" ? <ShoppingBag /> : r.kind === "DEBT_REPAYMENT" ? <Users /> : <Wallet />}
              title={kindTitle(r.kind, r.note)}
              time={new Date(r.created_at).toLocaleTimeString(lang === "ar" ? "ar-MA" : "fr-FR", { hour: "2-digit", minute: "2-digit" })}
              amount={Math.abs(num(r.amount))}
              lang={lang}
              plus={num(r.amount) > 0}
            />
          ))}
        </section>
      </div>
      <OwnerInsights lang={lang} period={period} />
    </>
  );
}

function PeriodFilter({ t, period, setPeriod }: any) {
  return (
    <div className="period">
      {[
        ["day", t.daily],
        ["week", t.weekly],
        ["month", t.monthly],
      ].map((x) => (
        <button
          key={x[0]}
          className={period === x[0] ? "active" : ""}
          onClick={() => setPeriod(x[0])}
        >
          {x[1]}
        </button>
      ))}
    </div>
  );
}
function ArrowDownIcon() {
  return <span className="arrow-glyph">↙</span>;
}
function ArrowUpIcon() {
  return <span className="arrow-glyph">↗</span>;
}
function Metric({ icon, label, amount, lang, tone, note, split, raw = false }: any) {
  return (
    <div className={`metric ${tone}`}>
      <div className="metric-icon">{icon}</div>
      <span>{label}</span>
      <strong>{raw ? formatNumber(amount, lang) : money(amount, lang)}</strong>
      <small>{split || note}</small>
    </div>
  );
}
function CardTitle({ title, action, onClick }: any) {
  return (
    <div className="card-title">
      <h3>{title}</h3>
      {action && (
        <button onClick={onClick}>
          {action}
          <ChevronRight size={15} />
        </button>
      )}
    </div>
  );
}
function Activity({ icon, title, time, amount, lang, plus }: any) {
  return (
    <div className="activity">
      <span className="activity-icon">{icon}</span>
      <div>
        <b>{title}</b>
        <small>{time}</small>
      </div>
      <strong className={plus ? "plus" : "minus"}>
        {lang === "ar" ? ltr(`${plus ? "+" : "−"}${money(amount, lang)}`) : `${plus ? "+" : "−"}${money(amount, lang)}`}
      </strong>
    </div>
  );
}

function MoneyPage({ t, lang, setModal, notify }: any) {
  const { data: bal } = useFetch<any>("/finance/balances");
  const today = new Date().toLocaleDateString("sv-SE");
  const { data: led } = useFetch<any[]>(`/finance/ledger?date_from=${today}&date_to=${today}`);
  const icon = (k: string) =>
    k === "SALE" ? <ShoppingBag /> : k === "DEBT_REPAYMENT" ? <Users /> : k === "STOCK_PURCHASE" ? <Package /> : k === "SUPPLIER_PAYMENT" ? <CreditCard /> : <Wallet />;
  const label = (e: any) =>
    e.kind === "SALE"
      ? `${lang === "fr" ? "Vente" : "بيع"} ${e.note || ""}`
      : e.kind === "DEBT_REPAYMENT"
        ? lang === "fr" ? "Remboursement client" : "سداد دين عميل"
        : e.kind === "VOID_REVERSAL"
          ? lang === "fr" ? "Annulation de vente" : "إلغاء عملية بيع"
          : e.note || e.kind;
  const rows = led || [];
  const income = rows.filter((e) => num(e.amount) > 0);
  const out = rows.filter((e) => num(e.amount) < 0);
  const by = bal?.by_method || {};
  return (
    <>
      <div className="page-heading row">
        <div>
          <h1>{t.money}</h1>
          <p>{lang === "fr" ? "Comprenez clairement chaque mouvement." : "افهم كل حركة مالية بوضوح."}</p>
        </div>
        <button className="btn primary" onClick={() => setModal("expense")}>
          <Plus size={18} />
          {t.addExpense}
        </button>
      </div>
      <div className="balance-strip">
        <div>
          <span>{t.cash}</span>
          <strong>{money(num(bal?.cash), lang)}</strong>
        </div>
        <div>
          <span>Orange Money</span>
          <strong>{money(num(by.orange), lang)}</strong>
        </div>
        <div>
          <span>Moov Money</span>
          <strong>{money(num(by.moov), lang)}</strong>
        </div>
        {num(by.wave) !== 0 && (
          <div>
            <span>Wave</span>
            <strong>{money(num(by.wave), lang)}</strong>
          </div>
        )}
        <div className="total">
          <span>{t.available}</span>
          <strong>{money(num(bal?.total), lang)}</strong>
        </div>
      </div>
      <RegisterCard t={t} lang={lang} notify={notify} />
      <div className="two-cols">
        <section className="card">
          <CardTitle title={t.income} />
          {income.map((e) => (
            <Activity key={e.id} icon={icon(e.kind)} title={label(e)} time={hhmm(e.created_at, lang)} amount={num(e.amount)} lang={lang} plus />
          ))}
        </section>
        <section className="card">
          <CardTitle title={t.expenses} />
          {out.map((e) => (
            <Activity key={e.id} icon={icon(e.kind)} title={label(e)} time={hhmm(e.created_at, lang)} amount={Math.abs(num(e.amount))} lang={lang} />
          ))}
        </section>
      </div>
      <div className="info-callout">
        <CircleHelp size={20} />
        <p>
          <b>{lang === "fr" ? "À retenir" : "معلومة مهمة"}</b>
          {lang === "fr"
            ? "Un remboursement client augmente votre argent disponible, mais ne compte pas comme une nouvelle vente."
            : "سداد العميل يزيد الأموال المتاحة، لكنه لا يُحسب مبيعة جديدة."}
        </p>
      </div>
    </>
  );
}

function RegisterCard({ t, lang, notify }: any) {
  const { refresh } = useApp();
  const { data: reg } = useFetch<any>("/finance/register/current");
  const [cash, setCash] = useState("");
  const [mobile, setMobile] = useState("");
  const [err, setErr] = useState("");
  const fr = lang === "fr";
  const act = async (e: any) => {
    e.preventDefault();
    try {
      if (!reg) await api.post("/finance/register/open", { opening_cash: cash, opening_mobile: mobile || 0 });
      else {
        const r = await api.post("/finance/register/close", { counted_cash: cash, counted_mobile: mobile || 0 });
        notify(`${fr ? "Écart caisse" : "فرق الصندوق"}: ${money(num(r.diff_cash), lang)}`);
      }
      setCash("");
      setMobile("");
      setErr("");
      refresh();
    } catch (x) {
      setErr(errMsg(x));
    }
  };
  return (
    <section className="card">
      <CardTitle title={reg ? (fr ? "Caisse ouverte clôture" : "الصندوق مفتوح إغلاق") : fr ? "Ouvrir la caisse du jour" : "فتح صندوق اليوم"} />
      <form onSubmit={act}>
        <div className="form-grid">
          <Field label={reg ? (fr ? "Espèces comptées" : "النقد المعدود") : fr ? "Espèces en caisse" : "النقد في الصندوق"} type="number" step="0.01" icon={<Banknote size={18} />} value={cash} onChange={(e: any) => setCash(e.target.value)} />
          <Field label="Mobile Money" type="number" step="0.01" required={false} icon={<CreditCard size={18} />} value={mobile} onChange={(e: any) => setMobile(e.target.value)} />
        </div>
        {err && <p className="form-error"><AlertTriangle size={15} />{err}</p>}
        <button className="btn primary">{reg ? (fr ? "Clôturer la caisse" : "إغلاق الصندوق") : fr ? "Ouvrir la caisse" : "فتح الصندوق"}</button>
      </form>
    </section>
  );
}

function DebtsPage({ t, lang, setModal }: any) {
  const [tab, setTab] = useState("mine");
  const { data } = useFetch<any>("/finance/debts");
  const dir = tab === "mine" ? "RECEIVABLE" : "PAYABLE";
  const rows = (data?.items || []).filter((d: any) => d.direction === dir);
  return (
    <>
      <div className="page-heading row">
        <div>
          <h1>{t.debts}</h1>
          <p>{lang === "fr" ? "Suivez simplement ce qui reste à payer." : "تابع بسهولة ما تبقى من الديون."}</p>
        </div>
        <div className="action-group">
          <button className="btn secondary" onClick={() => { modalStore.data = null; setModal("deposit"); }}>
            <Banknote size={18} />
            {lang === "fr" ? "Avance client" : "سلفة عميل"}
          </button>
          <button className="btn secondary" onClick={() => { modalStore.data = null; setModal("credit"); }}>
            <ShoppingCart size={18} />
            {lang === "fr" ? "Crédit client (articles)" : "دين عميل (منتجات)"}
          </button>
          <button className="btn primary" onClick={() => { modalStore.data = { direction: dir }; setModal("debt"); }}>
            <Plus size={18} />
            {t.addDebt}
          </button>
        </div>
      </div>
      <div className="tabs">
        <button className={tab === "mine" ? "active" : ""} onClick={() => setTab("mine")}>
          {t.owedToMe}
          <span>{money(num(data?.total_receivable), lang)}</span>
        </button>
        <button className={tab === "theirs" ? "active" : ""} onClick={() => setTab("theirs")}>
          {t.owedByMe}
          <span>{money(num(data?.total_payable), lang)}</span>
        </button>
      </div>
      <section className="card table-card">
        <div className="people-list">
          {rows.map((r: any) => (
            <div className="person-row" key={r.id}>
              <div className="person-avatar">{r.party_name.split(" ").map((x: string) => x[0]).join("").slice(0, 2)}</div>
              <div className="person-name">
                <b>{r.party_name}</b>
                <small>{ltr(r.phone || "")}</small>
                {r.items?.length > 0 && <small>{r.items.join(" · ")}</small>}
                {num(r.deposit_balance) > 0 && (
                  <small>{lang === "fr" ? "Avance détenue" : "سلفة محفوظة"}: {money(num(r.deposit_balance), lang)}</small>
                )}
              </div>
              <div>
                <small>{lang === "fr" ? "Dette initiale" : "الدين الأصلي"}</small>
                <b>{money(num(r.original_amount), lang)}</b>
              </div>
              <div>
                <small>{t.remaining}</small>
                <strong>{money(num(r.balance), lang)}</strong>
              </div>
              <button className="btn small secondary" onClick={() => { modalStore.data = { debt: r }; setModal("payment"); }}>
                {t.recordPayment}
              </button>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}

function StockPage({ t, lang, setModal, readOnly = false }: any) {
  const { user } = useApp();
  const canReceive = user?.role === "OWNER" || !!user?.can_receive_stock;
  const [query, setQuery] = useState("");
  const { data } = useFetch<any[]>("/products");
  const all = data || [];
  const list = all.filter((p) => ((lang === "ar" && p.name_ar) || p.name_fr).toLowerCase().includes(query.toLowerCase()));
  const low = all.filter((p) => num(p.stock_qty) > 0 && num(p.stock_qty) <= num(p.low_stock_threshold)).length;
  const out = all.filter((p) => num(p.stock_qty) <= 0).length;
  return (
    <>
      <div className="page-heading row">
        <div>
          <h1>{t.stock}</h1>
          <p>
            {lang === "fr"
              ? `${all.length} produits · ${low} stocks faibles · ${out} ruptures`
              : `${formatNumber(all.length, lang)} منتجاً · ${formatNumber(low, lang)} منخفضة · ${formatNumber(out, lang)} نفدت`}
          </p>
        </div>
        <div className="action-group">
          {canReceive && (
            <button className="btn secondary" onClick={() => { modalStore.data = null; setModal("receive"); }}>
              <Package size={18} />
              {lang === "fr" ? "Réception" : "استلام"}
            </button>
          )}
          <button className="btn primary" onClick={() => { modalStore.data = null; setModal("product"); }}>
            <Plus size={18} />
            {t.addProduct}
          </button>
        </div>
      </div>
      <div className="search-wide">
        <Search size={19} />
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t.search} />
      </div>
      <section className="card product-table">
        <div className="table-head">
          <span>{t.products}</span>
          <span>{t.currentStock}</span>
          <span>{t.price}</span>
          <span>{t.status}</span>
          <span />
        </div>
        {list.map((p) => {
          const q = num(p.stock_qty);
          return (
            <div className="product-line" key={p.id}>
              <div className="product-id">
                <span style={{ background: p.color || "#F0E9D5" }}>
                  <Package size={20} />
                </span>
                <b>{(lang === "ar" && p.name_ar) || p.name_fr}</b>
              </div>
              <strong>{formatNumber(q, lang)} {p.base_unit}</strong>
              <span>{money(num(p.price), lang)}</span>
              <span className={`badge ${q <= 0 ? "red" : q <= num(p.low_stock_threshold) ? "amber" : "green"}`}>
                {q <= 0 ? t.out : q <= num(p.low_stock_threshold) ? t.low : lang === "fr" ? "Disponible" : "متوفر"}
              </span>
              {!readOnly ? (
                <button className="icon-only" onClick={() => { modalStore.data = { product: p }; setModal("product"); }}>
                  <ChevronRight size={18} />
                </button>
              ) : <span />}
            </div>
          );
        })}
      </section>
    </>
  );
}

function ReportsPage({ t, lang, notify, setModal }: any) {
  const today = new Date().toLocaleDateString("sv-SE");
  const [from, setFrom] = useState(today);
  const [to, setTo] = useState(today);
  const { data: s } = useFetch<any>(`/reports/summary?date_from=${from}&date_to=${to}`);
  const { data: inv } = useFetch<any[]>(`/invoices?date_from=${from}&date_to=${to}&limit=100`);
  const { data: d } = useFetch<any>("/dashboard");
  const fr = lang === "fr";
  return (
    <>
      <div className="page-heading row">
        <div>
          <h1>{t.reports}</h1>
          <p>{formatDate(lang)}</p>
        </div>
        <div className="action-group">
          <button className="btn secondary" onClick={() => window.print()}>
            <Printer size={18} />
            {t.print}
          </button>
        </div>
      </div>
      <div className="form-grid">
        <Field label={fr ? "Du" : "من"} type="date" value={from} onChange={(e: any) => setFrom(e.target.value)} />
        <Field label={fr ? "Au" : "إلى"} type="date" value={to} onChange={(e: any) => setTo(e.target.value)} />
      </div>
      <div className="report-hero">
        <div>
          <span>{fr ? "Chiffre d’affaires (ventes)" : "رقم المبيعات"}</span>
          <strong>{money(num(s?.revenue), lang)}</strong>
          <small>
            {fr ? "Bénéfice brut (produits du catalogue) : " : "الربح الإجمالي (الكتالوج): "}
            {money(num(s?.gross_profit_catalog), lang)}
          </small>
        </div>
        <TrendingUp size={52} />
      </div>
      <div className="summary-grid">
        <Summary label={t.received} value={money(num(s?.cash_in_from_sales) + num(s?.cash_in_from_debt_repayments), lang)} />
        <Summary label={t.spent} value={money(num(s?.expenses), lang)} />
        <Summary label={t.customersOwe} value={money(num(d?.receivables), lang)} />
        <Summary label={t.iOwe} value={money(num(d?.payables), lang)} />
      </div>
      <section className="card">
        <CardTitle title={fr ? "Résumé des opérations" : "ملخص العمليات"} />
        <Activity icon={<ShoppingBag />} title={`${s?.invoices ?? 0} ${fr ? "ventes" : "عملية بيع"}${s?.voided ? ` · ${s.voided} ${fr ? "annulées" : "ملغاة"}` : ""}`} time="" amount={num(s?.revenue)} lang={lang} plus />
        <Activity icon={<Wallet />} title={fr ? "Dépenses" : "مصروفات"} time="" amount={num(s?.expenses)} lang={lang} />
        {(s?.by_worker || []).map((w: any) => (
          <Activity key={w.worker} icon={<UserRound />} title={`${w.worker} · ${w.invoices}`} time="" amount={num(w.revenue)} lang={lang} plus />
        ))}
      </section>
      <section className="card">
        <CardTitle title={fr ? "Factures" : "الفواتير"} />
        <InvoiceList t={t} lang={lang} list={inv || []} setModal={setModal} />
      </section>
    </>
  );
}

function InvoiceList({ t, lang, list, setModal }: any) {
  const fr = lang === "fr";
  return (
    <div className="people-list">
      {list.map((i: any) => (
        <div className="person-row" key={i.id}>
          <div className="person-name">
            <b>{ltr(i.receipt_no)}</b>
            <small>
              {new Date(i.created_at).toLocaleString(lang === "ar" ? "ar-MA" : "fr-FR")} · {i.worker.name}
            </small>
            {i.status === "VOIDED" && <small className="danger-text">{fr ? "Annulée" : "ملغاة"} {i.void_reason}</small>}
          </div>
          <strong>{money(num(i.total), lang)}</strong>
          <button className="btn small secondary" onClick={() => { receiptStore.invoice = i; setModal("receipt"); }}>
            <ReceiptText size={15} />
          </button>
          {i.status === "COMPLETED" && (
            <button className="btn small secondary" onClick={() => { modalStore.data = { invoice: i }; setModal("void"); }}>
              {fr ? "Annuler" : "إلغاء"}
            </button>
          )}
        </div>
      ))}
    </div>
  );
}

function Summary({ label, value }: any) {
  return (
    <div className="summary-box">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function AlertsPage({ t, lang, notify }: any) {
  const [reviewed, setReviewed] = useState<string[]>([]);
  const { data: d } = useFetch<any>("/dashboard");
  const { data: regs } = useFetch<any[]>("/finance/register/history");
  const { data: au } = useFetch<any>("/admin/audit?limit=60");
  const fr = lang === "fr";
  const alerts: any[] = [];
  (regs || []).filter((r) => r.status === "CLOSED" && (num(r.diff_cash) !== 0 || num(r.diff_mobile) !== 0)).slice(0, 5).forEach((r) =>
    alerts.push({ id: `reg${r.id}`, type: "danger", title: fr ? "Écart de caisse détecté" : "تم اكتشاف فرق في الصندوق", text: `${t.expected}: ${money(num(r.expected_cash), lang)} · ${t.counted}: ${money(num(r.counted_cash), lang)}`, amount: money(num(r.diff_cash), lang), at: r.closed_at }),
  );
  (au?.items || []).filter((a: any) => ["INVOICE_VOIDED", "PRICE_OVERRIDE", "ADMIN_PW_FAILED"].includes(a.action)).slice(0, 8).forEach((a: any) =>
    alerts.push({ id: `au${a.id}`, type: "warn", title: a.action === "INVOICE_VOIDED" ? (fr ? "Facture annulée" : "فاتورة ملغاة") : a.action === "PRICE_OVERRIDE" ? (fr ? "Prix modifié à la vente" : "تعديل سعر عند البيع") : fr ? "Mot de passe administrateur incorrect" : "كلمة مرور المدير خاطئة", text: `${a.actor || ""}${a.reason ? " " + a.reason : ""}`, amount: "", at: a.ts }),
  );
  (d?.low_stock || []).forEach((p: any) =>
    alerts.push({ id: `st${p.id}`, type: "warn", title: fr ? `Stock bas ${p.name_fr}` : `مخزون منخفض ${p.name_ar || p.name_fr}`, text: `${p.stock_qty} ${p.base_unit}`, amount: "", at: null }),
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>{t.alerts}</h1>
          <p>{fr ? "Points importants à vérifier aujourd’hui." : "أمور مهمة يجب التحقق منها اليوم."}</p>
        </div>
      </div>
      <div className="alerts-list">
        {alerts.map((a) => (
          <div className={`alert-card ${a.type}`} key={a.id}>
            <span className="alert-symbol">
              <AlertTriangle />
            </span>
            <div>
              <b>{a.title}</b>
              <p>{a.text}</p>
              {a.at && <small>{new Date(a.at).toLocaleString(lang === "ar" ? "ar-MA" : "fr-FR")}</small>}
            </div>
            <strong>{a.amount}</strong>
            <button className={`btn small ${reviewed.includes(a.id) ? "reviewed" : "secondary"}`} onClick={() => { setReviewed([...reviewed, a.id]); notify(t.reviewed); }}>
              {reviewed.includes(a.id) ? <Check size={16} /> : null}
              {reviewed.includes(a.id) ? t.reviewed : t.review}
            </button>
          </div>
        ))}
      </div>
      <div className="info-callout">
        <CircleHelp size={20} />
        <p>
          <b>{fr ? "Une différence n’est pas une accusation." : "وجود الفرق لا يعني توجيه اتهام."}</b>
          {fr ? "Examinez les opérations et ajoutez une explication avant de corriger." : "راجع العمليات وأضف تفسيراً قبل إجراء التصحيح."}
        </p>
      </div>
    </>
  );
}

function TeamPage({ t, lang, workers, setModal, notify }: any) {
  const { refresh } = useApp();
  const fr = lang === "fr";
  const patch = async (id: number, body: any, msg: string) => {
    try {
      await api.patch(`/workers/${id}`, body);
      refresh();
      notify(msg);
    } catch (e) {
      notify(errMsg(e));
    }
  };
  return (
    <>
      <div className="page-heading row">
        <div>
          <h1>{fr ? "Mon équipe" : "فريقي"}</h1>
          <p>{fr ? `${workers.length} employés liés à la même boutique` : `${formatNumber(workers.length, lang)} موظفين مرتبطين بالمتجر نفسه`}</p>
        </div>
        <button className="btn primary" onClick={() => setModal("worker")}>
          <Plus size={18} />
          {fr ? "Ajouter un employé" : "إضافة موظف"}
        </button>
      </div>
      <div className="role-explainer">
        <ShieldCheck size={20} />
        <p>
          <b>{fr ? "Accès limité pour les employés" : "صلاحيات محدودة للموظفين"}</b>
          {fr
            ? "Ils peuvent vendre, imprimer des reçus et voir leurs propres ventes. Ils ne peuvent ni modifier les prix, ni supprimer ou annuler une facture sans votre mot de passe administrateur."
            : "يمكنهم البيع وطباعة الإيصالات ورؤية مبيعاتهم فقط. لا يمكنهم تعديل الأسعار أو حذف أو إلغاء فاتورة دون كلمة مرور المدير."}
        </p>
      </div>
      <section className="card team-list">
        {workers.map((w: WorkerAccount) => (
          <div className="team-member" key={w.id}>
            <div className="person-avatar">{w.name.split(" ").map((p) => p[0]).join("").slice(0, 2)}</div>
            <div className="team-name">
              <b>{w.name}</b>
              <small>
                <span dir="ltr">{w.phone}</span> · <span dir="ltr">{w.username}</span>
              </small>
            </div>
            <span className={`badge ${w.active ? "green" : "red"}`}>{w.active ? (fr ? "Actif" : "نشط") : fr ? "Suspendu" : "موقوف"}</span>
            <button className="btn small secondary" onClick={() => patch(w.id, { active: !w.active }, w.active ? (fr ? "Compte suspendu" : "تم إيقاف الحساب") : fr ? "Compte réactivé" : "تمت إعادة تفعيل الحساب")}>
              {w.active ? (fr ? "Suspendre" : "إيقاف") : fr ? "Réactiver" : "إعادة التفعيل"}
            </button>
            <button className="btn small secondary" onClick={() => patch(w.id, { can_sell_credit: !w.canCredit }, fr ? "Permission crédit modifiée" : "تم تغيير إذن الدين")}>
              {fr ? "Crédit" : "دين"}: {w.canCredit ? "✓" : "✗"}
            </button>
            <button
              className="icon-only"
              title={fr ? "Nouveau mot de passe" : "كلمة مرور جديدة"}
              onClick={async () => {
                try {
                  const r = await api.post(`/workers/${w.id}/reset-password`);
                  modalStore.data = { name: w.name, username: r.username, password: r.password, recovery: r.recovery_code };
                  setModal("creds");
                } catch (e) {
                  notify(errMsg(e));
                }
              }}
            >
              <KeyRound size={17} />
            </button>
          </div>
        ))}
      </section>
    </>
  );
}

function OwnerSettingsPage({ t, lang, setPage, setModal }: any) {
  const { shop } = useApp();
  const { data: ws } = useFetch<any[]>("/workers");
  const fr = lang === "fr";
  const open = (m: string) => { modalStore.data = null; setModal(m); };
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>{t.settings}</h1>
          <p>{fr ? "Boutique, équipe et préférences." : "المتجر والفريق والتفضيلات."}</p>
        </div>
      </div>
      <div className="settings-grid">
        <section className="card">
          <CardTitle title={fr ? "Ma boutique" : "متجري"} />
          <SettingsRow icon={<Store />} title={shop.name} sub={ltr(shop.phone)} />
          <SettingsRow icon={<Users />} title={fr ? "Équipe" : "الفريق"} sub={fr ? `1 propriétaire · ${ws?.length ?? 0} employés` : `مالك واحد · ${ws?.length ?? 0} موظفين`} onClick={() => setPage("team")} />
          <SettingsRow icon={<ReceiptText />} title={fr ? "Format des reçus" : "تنسيق الإيصالات"} sub="58 mm · 80 mm · A4" />
        </section>
        <section className="card">
          <CardTitle title={fr ? "Sauvegarde (clé USB)" : "النسخ الاحتياطي (USB)"} />
          <SettingsRow icon={<Download />} title={fr ? "Sauvegarder maintenant" : "حفظ نسخة الآن"} sub={fr ? "Enregistre la base sur une clé USB ou un dossier" : "يحفظ القاعدة على USB أو مجلد"} onClick={() => open("backup")} />
          <SettingsRow icon={<RefreshCw />} title={fr ? "Restaurer une sauvegarde" : "استعادة نسخة"} sub={fr ? "Mot de passe administrateur requis" : "يتطلب كلمة مرور المدير"} onClick={() => open("restore")} />
        </section>
        <section className="card">
          <CardTitle title={fr ? "Sécurité" : "الأمان"} />
          <SettingsRow icon={<ShieldCheck />} title={fr ? "Mot de passe administrateur" : "كلمة مرور المدير"} sub={fr ? "Prix, annulations, restauration" : "الأسعار والإلغاء والاستعادة"} onClick={() => open("adminpw")} />
          <SettingsRow icon={<LockKeyhole />} title={fr ? "Changer mon mot de passe" : "تغيير كلمة المرور"} sub="" onClick={() => open("chpw")} />
          <SettingsRow icon={<KeyRound />} title={fr ? "Code PIN rapide" : "رمز PIN سريع"} sub={fr ? "Changement d’utilisateur rapide" : "تبديل سريع للمستخدم"} onClick={() => open("pin")} />
        </section>
      </div>
    </>
  );
}
function SettingsRow({ icon, title, sub, onClick }: any) {
  return (
    <button className="settings-row" onClick={onClick}>
      <span>{icon}</span>
      <div>
        <b>{title}</b>
        <small>{sub}</small>
      </div>
      <ChevronRight size={18} />
    </button>
  );
}

function WorkerSettingsPage({ t, lang, worker, setModal }: any) {
  const fr = lang === "fr";
  const open = (m: string) => { modalStore.data = null; setModal(m); };
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>{fr ? "Mon compte employé" : "حساب الموظف"}</h1>
          <p>{fr ? "Vos informations personnelles et cet appareil." : "معلوماتك الشخصية وهذا الجهاز."}</p>
        </div>
      </div>
      <div className="settings-grid">
        <section className="card">
          <CardTitle title={fr ? "Mon accès" : "بيانات دخولي"} />
          <SettingsRow icon={<UserRound />} title={worker?.name} sub={worker?.username} />
          <SettingsRow icon={<LockKeyhole />} title={fr ? "Changer mon mot de passe" : "تغيير كلمة المرور"} sub="" onClick={() => open("chpw")} />
          <SettingsRow icon={<KeyRound />} title={fr ? "Code PIN rapide" : "رمز PIN سريع"} sub={fr ? "Pour changer d’utilisateur rapidement" : "لتبديل المستخدم بسرعة"} onClick={() => open("pin")} />
        </section>
        <section className="card">
          <CardTitle title={fr ? "Mon appareil" : "جهازي"} />
          <SettingsRow icon={<ShieldCheck />} title={fr ? "Données locales protégées" : "البيانات المحلية محمية"} sub={fr ? "Cet ordinateur uniquement" : "على هذا الجهاز فقط"} />
          <SettingsRow icon={<ReceiptText />} title={fr ? "Imprimante de reçus" : "طابعة الإيصالات"} sub={fr ? "Impression via l’imprimante par défaut" : "الطباعة عبر الطابعة الافتراضية"} />
        </section>
      </div>
      <div className="worker-permission-note">
        <LockKeyhole size={18} />
        <p>
          {fr
            ? "Votre compte ne permet pas de modifier les prix ni de supprimer ou annuler une facture sans le mot de passe administrateur du propriétaire."
            : "لا يسمح حسابك بتعديل الأسعار أو حذف أو إلغاء فاتورة دون كلمة مرور مدير المالك."}
        </p>
      </div>
    </>
  );
}

function WorkerContent({ t, lang, page, setPage, online, setModal, notify, worker }: any) {
  const { shop } = useApp();
  const today = new Date().toLocaleDateString("sv-SE");
  const { data: mine } = useFetch<any[]>(page === "history" || page === "dashboard" ? `/invoices?date_from=${today}&date_to=${today}&limit=200` : null);
  const fr = lang === "fr";
  if (page === "sales") return <POS t={t} lang={lang} online={online} setModal={setModal} notify={notify} />;
  if (page === "stock") return <StockPage t={t} lang={lang} setModal={setModal} readOnly />;
  if (page === "credit") return <CustomerCreditPage t={t} lang={lang} setModal={setModal} />;
  if (page === "history")
    return (
      <>
        <div className="page-heading">
          <div>
            <h1>{t.history}</h1>
            <p>{fr ? "Mes ventes uniquement" : "مبيعاتي فقط"}</p>
          </div>
        </div>
        <section className="card">
          <InvoiceList t={t} lang={lang} list={mine || []} setModal={setModal} />
        </section>
      </>
    );
  if (page === "settings") return <WorkerSettingsPage t={t} lang={lang} worker={worker} setModal={setModal} />;
  const done = (mine || []).filter((i) => i.status === "COMPLETED");
  const total = done.reduce((a, i) => a + num(i.total), 0);
  const cashIn = done.reduce((a, i) => a + (i.paid_method === "cash" ? num(i.paid_amount) : 0), 0);
  return (
    <>
      <div className="worker-hero">
        <div>
          <p>{t.hello}</p>
          <h1>{worker?.name?.split(" ")[0]}</h1>
          <span>{formatDate(lang)} · {shop.name}</span>
        </div>
        <button className="sale-cta" onClick={() => setPage("sales")}>
          <ShoppingCart size={28} />
          <div>
            <b>{t.newSale}</b>
            <small>{fr ? "Rapide et simple" : "سريع وسهل"}</small>
          </div>
          <ChevronRight />
        </button>
      </div>
      <div className="worker-stats">
        <div>
          <span>{fr ? "Mes ventes aujourd’hui" : "مبيعاتي اليوم"}</span>
          <strong>{money(total, lang)}</strong>
          <small>{done.length} {fr ? "ventes" : "عملية بيع"}</small>
        </div>
        <div>
          <span>{fr ? "Espèces encaissées" : "النقد المقبوض"}</span>
          <strong>{money(cashIn, lang)}</strong>
          <small>{t.cash}</small>
        </div>
        {worker?.can_receive_stock && (
          <button className="sale-cta" style={{ minHeight: 0 }} onClick={() => { modalStore.data = null; setModal("receive"); }}>
            <Package size={22} />
            <div>
              <b>{fr ? "Réception de stock" : "استلام بضاعة"}</b>
              <small>{fr ? "Cartons, boîtes, pièces…" : "كراتين، علب، قطع…"}</small>
            </div>
          </button>
        )}
        <button className="sale-cta" style={{ minHeight: 0 }} onClick={() => { modalStore.data = null; setModal("product"); }}>
          <Plus size={22} />
          <div>
            <b>{t.addProduct}</b>
            <small>{fr ? "Nouveau produit, prêt à vendre" : "منتج جديد جاهز للبيع"}</small>
          </div>
        </button>
      </div>
      <section className="card">
        <CardTitle title={t.recent} action={t.seeAll} onClick={() => setPage("history")} />
        {done.slice(0, 5).map((i) => (
          <Activity key={i.id} icon={<ShoppingBag />} title={`${ltr(i.receipt_no)} · ${i.payment_method}`} time={hhmm(i.created_at, lang)} amount={num(i.total)} lang={lang} plus />
        ))}
      </section>
    </>
  );
}

type CartLine = { key: number; product: any; unit: string; qty: number };
function POS({ t, lang, online, setModal, notify }: any) {
  const { refresh } = useApp();
  const fr = lang === "fr";
  const [query, setQuery] = useState("");
  const [cat, setCat] = useState("");
  const [cart, setCart] = useState<CartLine[]>([]);
  const [payment, setPayment] = useState("cash");
  const [customerId, setCustomerId] = useState("");
  const [cartOpen, setCartOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [ref, setRef] = useState(() => crypto.randomUUID());
  const { data: prods } = useFetch<any[]>("/products");
  const { data: custs } = useFetch<any[]>("/customers");
  const all = prods || [];
  const cats = Array.from(new Set(all.map((p) => p.category).filter(Boolean))) as string[];
  const list = all.filter(
    (p) =>
      (!cat || p.category === cat) &&
      ((lang === "ar" && p.name_ar) || p.name_fr).toLowerCase().includes(query.toLowerCase()),
  );
  const unitPrice = (l: CartLine) => num(l.product.units.find((u: any) => u.name === l.unit)?.price);
  const total = useMemo(() => cart.reduce((s, l) => s + unitPrice(l) * l.qty, 0), [cart]);
  const count = cart.length;
  const addProduct = (p: any) =>
    setCart((c) => {
      const ex = c.find((l) => l.product.id === p.id && l.unit === p.base_unit);
      return ex ? c.map((l) => (l === ex ? { ...l, qty: l.qty + 1 } : l)) : [...c, { key: Date.now() + Math.random(), product: p, unit: p.base_unit, qty: 1 }];
    });
  const patchLine = (key: number, patch: Partial<CartLine>) => setCart((c) => c.map((l) => (l.key === key ? { ...l, ...patch } : l)));
  useEffect(() => {
    if (cart.length === 0) setCartOpen(false);
  }, [cart.length]);
  const confirm = async () => {
    setBusy(true);
    try {
      const inv = await api.post("/invoices", {
        client_ref: ref,
        payment_method: payment,
        customer_id: customerId ? Number(customerId) : null,
        lines: cart.map((l) => ({ product_id: l.product.id, unit_name: l.unit, quantity: String(l.qty) })),
      });
      receiptStore.invoice = inv;
      setCart([]);
      setCartOpen(false);
      setRef(crypto.randomUUID());
      refresh();
      setModal("receipt");
      notify(t.saleSuccess);
    } catch (e) {
      notify(errMsg(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="pos-layout">
      <section className="pos-products">
        <div className="page-heading row">
          <div>
            <h1>{t.newSale}</h1>
            <p>{fr ? "Vendez d’abord, cataloguez ensuite." : "بع أولاً ثم أضف إلى الكتالوج لاحقاً."}</p>
          </div>
          <button className="btn secondary" onClick={() => { modalStore.data = null; setModal("quick"); }}>
            <Plus size={18} />
            {fr ? "Vente directe" : "بيع مباشر"}
          </button>
        </div>
        <div className="search-wide">
          <Search size={19} />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t.search} />
        </div>
        <div className="category-pills">
          <button className={cat === "" ? "active" : ""} onClick={() => setCat("")}>{fr ? "Tous" : "الكل"}</button>
          {cats.map((c) => (
            <button key={c} className={cat === c ? "active" : ""} onClick={() => setCat(c)}>{c}</button>
          ))}
        </div>
        <div className="product-grid">
          {list.map((p) => {
            const q = num(p.stock_qty);
            return (
              <button disabled={q <= 0} className="product-card" key={p.id} onClick={() => addProduct(p)}>
                <span className="product-art" style={{ background: p.color || "#F0E9D5" }}>
                  <Package size={28} />
                </span>
                <b>{(lang === "ar" && p.name_ar) || p.name_fr}</b>
                <strong>{money(num(p.price), lang)}</strong>
                <small className={q <= num(p.low_stock_threshold) ? "danger-text" : ""}>
                  {q <= 0 ? t.out : `${formatNumber(q, lang)} ${p.base_unit}`}
                </small>
              </button>
            );
          })}
        </div>
      </section>
      {total > 0 && (
        <button className="cart-bar" onClick={() => setCartOpen(true)}>
          <span className="cart-bar-count">
            <ShoppingCart size={20} />
            <em>{count}</em>
          </span>
          <span className="cart-bar-label">{t.cart}</span>
          <strong>{money(total, lang)}</strong>
          <ChevronRight size={18} />
        </button>
      )}
      {cartOpen && <div className="cart-backdrop" onClick={() => setCartOpen(false)} />}
      <aside className={`cart-panel ${cartOpen ? "open" : ""}`}>
        <div className="cart-head">
          <h2>{t.cart}</h2>
          <span>{count}</span>
          <button className="cart-close" aria-label="Close" onClick={() => setCartOpen(false)}>
            <X size={18} />
          </button>
        </div>
        {cart.length === 0 ? (
          <div className="empty-cart">
            <ShoppingCart />
            <b>{t.emptyCart}</b>
            <p>{t.addItems}</p>
          </div>
        ) : (
          <>
            <div className="cart-items">
              {cart.map((l) => (
                <div className="cart-item" key={l.key}>
                  <div>
                    <b>{(lang === "ar" && l.product.name_ar) || l.product.name_fr}</b>
                    <small>
                      {money(unitPrice(l), lang)} ×{" "}
                      <select value={l.unit} onChange={(e) => patchLine(l.key, { unit: e.target.value })}>
                        {l.product.units.map((u: any) => (
                          <option key={u.name} value={u.name}>{u.name}</option>
                        ))}
                      </select>
                    </small>
                  </div>
                  <div className="qty">
                    <button onClick={() => patchLine(l.key, { qty: Math.max(0, +(l.qty - 1).toFixed(3)) })}>
                      <Minus size={14} />
                    </button>
                    <input
                      style={{ width: 54, textAlign: "center", border: 0, background: "transparent", font: "inherit" }}
                      inputMode="decimal"
                      value={l.qty}
                      onChange={(e) => patchLine(l.key, { qty: Number(e.target.value.replace(",", ".")) || 0 })}
                    />
                    <button onClick={() => patchLine(l.key, { qty: +(l.qty + 1).toFixed(3) })}>
                      <Plus size={14} />
                    </button>
                  </div>
                  <strong>{money(unitPrice(l) * l.qty, lang)}</strong>
                </div>
              ))}
            </div>
            <div className="cart-bottom">
              <div className="cart-total">
                <span>{t.total}</span>
                <strong>{money(total, lang)}</strong>
              </div>
              <label>{t.payment}</label>
              <div className="payment-grid">
                {[
                  ["cash", t.cash],
                  ["orange", "Orange Money"],
                  ["moov", "Moov Money"],
                  ["credit", fr ? "À crédit" : "بالدين"],
                ].map((x) => (
                  <button className={payment === x[0] ? "active" : ""} onClick={() => setPayment(x[0])} key={x[0]}>
                    {x[0] === "cash" ? <Banknote /> : <CreditCard />}
                    <span>{x[1]}</span>
                  </button>
                ))}
              </div>
              <label className="field">
                <span>{fr ? "Client" : "العميل"}{payment === "credit" ? " *" : ""}</span>
                <div className="select-wrap">
                  <select value={customerId} onChange={(e) => (e.target.value === "new" ? (modalStore.data = null, setModal("customer")) : setCustomerId(e.target.value))}>
                    <option value="">{fr ? "— Aucun" : "— بدون"}</option>
                    {(custs || []).map((c) => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                    <option value="new">{fr ? "+ Nouveau client" : "+ عميل جديد"}</option>
                  </select>
                </div>
              </label>
              <button className="btn primary full sale-confirm" disabled={busy || total <= 0} onClick={confirm}>
                <Check size={19} />
                {t.confirmSale}
              </button>
            </div>
          </>
        )}
      </aside>
    </div>
  );
}

function AdminDashboard({ t, page, setModal, notify }: any) {
  const { refresh } = useApp();
  const { data: ov } = useFetch<any>(page === "dashboard" || page === "settings" ? "/admin/overview" : null);
  const { data: users } = useFetch<any[]>(page === "stock" ? "/admin/users" : null);
  const { data: au } = useFetch<any>(page === "history" ? "/admin/audit?limit=200" : null);
  const fmtSize = (b: number) => `${(b / 1048576).toFixed(2)} Mo`;
  if (page === "stock")
    return (
      <>
        <div className="page-heading"><div><h1>Boutiques</h1><p>Comptes de la boutique · toutes les consultations sont auditées</p></div></div>
        <section className="card">
          {(users || []).map((u) => (
            <div className="team-member" key={u.id}>
              <div className="person-avatar">{u.name.split(" ").map((p: string) => p[0]).join("").slice(0, 2)}</div>
              <div className="team-name"><b>{u.name}</b><small dir="ltr">{u.username} · {u.role}</small></div>
              <span className={`badge ${u.active ? "green" : "red"}`}>{u.active ? "Actif" : "Suspendu"}</span>
              {u.role !== "DDS_ADMIN" && (
                <button className="btn small secondary" onClick={async () => {
                  try {
                    const r = await api.post(`/admin/users/${u.id}/reset-password`);
                    modalStore.data = { name: u.name, username: r.username, password: r.password, recovery: r.recovery_code };
                    setModal("creds");
                    refresh();
                  } catch (e) { notify(errMsg(e)); }
                }}>
                  <KeyRound size={15} /> Réinitialiser
                </button>
              )}
            </div>
          ))}
        </section>
      </>
    );
  if (page === "history")
    return (
      <>
        <div className="page-heading"><div><h1>Journaux techniques</h1><p>Journal d’audit inviolable · chaîne {au?.chain?.ok ? "vérifiée ✓" : au ? "ALTÉRÉE ✗" : "…"} ({au?.chain?.checked ?? 0} entrées)</p></div></div>
        <section className="card">
          {(au?.items || []).map((a: any) => (
            <div className="health-row" key={a.id}>
              <span><b>{a.action}</b> · {a.actor || "—"}{a.reason ? ` · ${a.reason}` : ""}</span>
              <b dir="ltr">{new Date(a.ts).toLocaleString("fr-FR")}</b>
            </div>
          ))}
        </section>
      </>
    );
  if (page === "settings")
    return (
      <>
        <div className="page-heading"><div><h1>{t.settings}</h1><p>Support technique</p></div></div>
        <section className="card">
          <CardTitle title="Base de données locale" />
          <SettingsRow icon={<Store />} title="Emplacement" sub={ov?.db_path || ""} />
          <SettingsRow icon={<Download />} title="Créer une sauvegarde" sub={ov ? fmtSize(ov.db_size) : ""} onClick={() => { modalStore.data = null; setModal("backup"); }} />
        </section>
      </>
    );
  return (
    <>
      <div className="page-heading row">
        <div><p>DDS Support</p><h1>Vue d’ensemble</h1><span>{ov?.shop_name} · v{ov?.version}</span></div>
        <span className={`badge ${ov?.audit_chain?.ok ? "green" : "red"}`}>{ov?.audit_chain?.ok ? "Journal d’audit intègre" : "Journal d’audit altéré"}</span>
      </div>
      <div className="admin-metrics">
        <Metric raw icon={<Store />} label="Boutique" amount={1} lang="fr" tone="navy" note={ov?.shop_name || ""} />
        <Metric raw icon={<Users />} label="Comptes utilisateurs" amount={ov?.users ?? 0} lang="fr" tone="blue" note={`${ov?.owners ?? 0} propriétaire · ${ov?.workers ?? 0} employés`} />
        <Metric raw icon={<Package />} label="Produits" amount={ov?.products ?? 0} lang="fr" tone="green" note="Catalogue" />
        <Metric raw icon={<ReceiptText />} label="Factures" amount={ov?.invoices ?? 0} lang="fr" tone="orange" note="Toutes périodes" />
      </div>
      <section className="card">
        <CardTitle title="Santé technique" />
        <div className="health-row"><span>Serveur local</span><b>Opérationnel</b></div>
        <div className="health-row"><span>Base SQLite (WAL)</span><b>{ov ? fmtSize(ov.db_size) : "…"}</b></div>
        <div className="health-row"><span>Employés actifs</span><b>{ov?.active_workers ?? 0}</b></div>
      </section>
    </>
  );
}

function NotificationPanel({ t, lang, close, notify }: any) {
  const [read, setRead] = useState<number[]>([]);
  const { user } = useApp();
  const { data: d } = useFetch<any>(user?.role === "OWNER" ? "/dashboard" : null);
  const items: string[] = (d?.low_stock || []).map((p: any) =>
    lang === "fr" ? `Stock bas : ${p.name_fr} (${p.stock_qty} ${p.base_unit})` : `مخزون منخفض: ${p.name_ar || p.name_fr}`,
  );
  return (
    <>
      <div className="drawer-backdrop" onClick={close} />
      <aside className="notification-panel">
        <div className="drawer-head">
          <div>
            <h2>{t.notifications}</h2>
            <span>{items.length - read.length} {lang === "fr" ? "non lues" : "غير مقروءة"}</span>
          </div>
          <button onClick={close}><X /></button>
        </div>
        <button className="mark-all" onClick={() => { setRead(items.map((_, i) => i)); notify(t.markAll); }}>{t.markAll}</button>
        <div className="notification-list">
          {items.map((item, i) => (
            <button key={i} className={read.includes(i) ? "read" : ""} onClick={() => setRead([...read, i])}>
              <span className="notification-icon warning"><AlertTriangle /></span>
              <div><b>{item}</b></div>
              {!read.includes(i) && <em />}
            </button>
          ))}
        </div>
      </aside>
    </>
  );
}

function Modal({ type, t, lang, close, notify, addWorker, setModal }: any) {
  if (type === "receipt") return <ReceiptModal t={t} lang={lang} close={close} notify={notify} />;
  if (type === "credit" || type === "deposit")
    return <CustomerCreditModal type={type} t={t} lang={lang} close={close} notify={notify} setModal={setModal} />;
  if (type === "worker")
    return <WorkerAccountModal t={t} lang={lang} close={close} notify={notify} addWorker={addWorker} />;
  if (type === "creds") {
    const c = modalStore.data || {};
    return (
      <div className="modal-layer">
        <div className="modal-backdrop" onClick={close} />
        <div className="modal worker-modal">
          <div className="modal-head">
            <div>
              <span><Check /></span>
              <h2>{lang === "fr" ? "Nouvelle fiche d’accès" : "بطاقة دخول جديدة"}</h2>
            </div>
            <button onClick={close}><X /></button>
          </div>
          <CredentialsCard lang={lang} title={lang === "fr" ? "Transmettez cette fiche" : "سلّم هذه البطاقة"} name={c.name} username={c.username} password={c.password} recoveryCode={c.recovery} notify={notify} />
          <button className="btn primary full" onClick={close}>{t.back}</button>
        </div>
      </div>
    );
  }
  return <FormModal key={type} type={type} t={t} lang={lang} close={close} notify={notify} setModal={setModal} />;
}

const PAY_METHODS = (t: any): [string, string][] => [
  ["cash", t.cash],
  ["orange", "Orange Money"],
  ["moov", "Moov Money"],
  ["wave", "Wave"],
];
const parseUnits = (text: string) =>
  text
    .split(/[,;\n]/)
    .map((x) => x.trim())
    .filter(Boolean)
    .map((x) => {
      const [name, factor] = x.split("=").map((y) => y.trim());
      return { name, factor: (factor || "").replace(",", ".") };
    });

function FormModal({ type, t, lang, close, notify, setModal }: any) {
  const { user, refresh } = useApp();
  const fr = lang === "fr";
  const ctx = modalStore.data || {};
  const editing = ctx.product;
  const isOwner = user?.role === "OWNER";
  const [v, setV] = useState<Record<string, string>>(() => ({
    method: "cash",
    unit: "",
    label: "",
    qty: "1",
    ...(editing
      ? {
          name_fr: editing.name_fr,
          name_ar: editing.name_ar || "",
          base_unit: editing.base_unit,
          price: String(num(editing.price)),
          cost: String(num(editing.cost)),
          units: editing.units.filter((u: any) => !u.base).map((u: any) => `${u.name}=${num(u.factor)}`).join(", "),
          threshold: String(num(editing.low_stock_threshold)),
          category: editing.category || "",
        }
      : { base_unit: "Pièce", threshold: "5", stock_unit: "" }),
  }));
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k: string) => (e: any) => setV((x) => ({ ...x, [k]: e.target.value }));
  const { data: prods } = useFetch<any[]>(type === "receive" ? "/products" : null);
  const prod = type === "receive" ? (prods || []).find((p) => String(p.id) === v.product_id) : null;
  const titles: Record<string, string> = {
    expense: t.addExpense, debt: t.addDebt, payment: t.recordPayment,
    product: editing ? (fr ? "Modifier le produit" : "تعديل المنتج") : t.addProduct,
    quick: fr ? "Vente directe" : "بيع مباشر", receive: fr ? "Réception de stock" : "استلام بضاعة",
    void: fr ? "Annuler la facture" : "إلغاء الفاتورة", customer: fr ? "Nouveau client" : "عميل جديد",
    backup: fr ? "Sauvegarde" : "نسخ احتياطي", restore: fr ? "Restaurer" : "استعادة",
    adminpw: fr ? "Mot de passe administrateur" : "كلمة مرور المدير",
    chpw: fr ? "Changer mon mot de passe" : "تغيير كلمة المرور", pin: fr ? "Code PIN rapide" : "رمز PIN سريع",
  };
  const submit = async (e: any) => {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      let msg = fr ? "Enregistré avec succès" : "تم الحفظ بنجاح";
      if (type === "expense") await api.post("/finance/expenses", { description: v.description, amount: v.amount, method: v.method });
      else if (type === "debt") await api.post("/finance/debts", { direction: ctx.direction || "RECEIVABLE", party_name: v.person, amount: v.amount });
      else if (type === "payment") {
        if (v.method === "deposit") await api.post(`/finance/debts/${ctx.debt.id}/apply-deposit`, { amount: v.amount });
        else await api.post(`/finance/debts/${ctx.debt.id}/payments`, { amount: v.amount, method: v.method });
      }
      else if (type === "customer") {
        await api.post("/customers", { name: v.person, phone: v.phone || null });
      } else if (type === "product") {
        const body: any = { name_fr: v.name_fr, name_ar: v.name_ar || null, category: v.category || null, price: v.price, cost: v.cost || "0", units: parseUnits(v.units || ""), low_stock_threshold: v.threshold || "5" };
        if (editing) await api.patch(`/products/${editing.id}`, { ...body, admin_password: v.admin_password });
        else {
          const st = (v.stock_qty || "").replace(",", ".");
          await api.post("/products", {
            ...body,
            base_unit: v.base_unit,
            initial_stock: st && Number(st) > 0 ? st : null,
            initial_stock_unit: st && Number(st) > 0 && v.stock_unit ? v.stock_unit : null,
          });
        }
      } else if (type === "receive") {
        await api.post("/stock/receive", { product_id: Number(v.product_id), unit_name: v.unit || null, quantity: v.qty, unit_cost: v.cost || null });
      } else if (type === "quick") {
        const inv = await api.post("/invoices", { payment_method: v.method, lines: [{ label: v.label || null, unit_name: v.unit || "pièce", quantity: v.qty, unit_price: v.price }] });
        receiptStore.invoice = inv;
        refresh();
        setModal("receipt");
        notify(t.saleSuccess);
        return;
      } else if (type === "void") {
        await api.post(`/invoices/${ctx.invoice.id}/void`, { reason: v.reason, admin_password: v.admin_password });
        msg = fr ? "Facture annulée stock et caisse corrigés" : "تم إلغاء الفاتورة وتصحيح المخزون والصندوق";
      } else if (type === "backup") {
        let dir: string | null = null;
        if (window.shopDesktop?.chooseFolder) {
          dir = await window.shopDesktop.chooseFolder();
          if (!dir) return;
        }
        const r = await api.post("/backup/export", { target_dir: dir });
        msg = `${fr ? "Sauvegarde créée" : "تم إنشاء النسخة"} : ${r.file}`;
      } else if (type === "restore") {
        let path = v.path;
        if (window.shopDesktop?.chooseBackupFile && !path) path = (await window.shopDesktop.chooseBackupFile()) || "";
        if (!path) throw new Error("path");
        await api.post("/backup/restore-path", { path, admin_password: v.admin_password });
        setToken(null);
        window.location.reload();
        return;
      } else if (type === "adminpw") {
        if (v.new1 !== v.new2) throw new Error(fr ? "Les deux mots de passe diffèrent." : "كلمتا المرور مختلفتان.");
        await api.post("/owner/admin-password", { current_admin_password: v.admin_password, new_admin_password: v.new1 });
      } else if (type === "chpw") {
        if (v.new1 !== v.new2) throw new Error(fr ? "Les deux mots de passe diffèrent." : "كلمتا المرور مختلفتان.");
        await api.post("/auth/change-password", { current_password: v.current, new_password: v.new1 });
      } else if (type === "pin") await api.post("/auth/pin", { pin: v.pin });
      refresh();
      notify(msg);
      close();
    } catch (x: any) {
      setErr(x instanceof ApiError ? x.message : x?.message === "path" ? "" : x?.message || "Erreur");
    } finally {
      setBusy(false);
    }
  };
  const pm = (
    <label className="field">
      <span>{t.payment}</span>
      <div className="select-wrap">
        <select value={v.method} onChange={set("method")}>
          {PAY_METHODS(t).map((m) => <option key={m[0]} value={m[0]}>{m[1]}</option>)}
        </select>
      </div>
    </label>
  );
  const pw = (label?: string) => (
    <Field label={label || (fr ? "Mot de passe administrateur" : "كلمة مرور المدير")} type="password" placeholder="••••••••" icon={<ShieldCheck size={18} />} value={v.admin_password || ""} onChange={set("admin_password")} />
  );
  const Icon = type === "expense" ? Wallet : type === "product" || type === "receive" ? Package : type === "quick" ? ShoppingCart : type === "void" || type === "adminpw" ? ShieldCheck : Users;
  return (
    <div className="modal-layer">
      <div className="modal-backdrop" onClick={close} />
      <div className="modal">
        <div className="modal-head">
          <div>
            <span><Icon /></span>
            <h2>{titles[type]}</h2>
          </div>
          <button onClick={close}><X /></button>
        </div>
        <form onSubmit={submit}>
          {type === "expense" && (
            <>
              <Field label={t.description} placeholder={fr ? "Ex. Transport" : "مثال: النقل"} icon={<FileText size={18} />} value={v.description || ""} onChange={set("description")} />
              <Field label={t.amount} placeholder="0" type="number" step="0.01" icon={<Banknote size={18} />} value={v.amount || ""} onChange={set("amount")} />
              {pm}
            </>
          )}
          {type === "debt" && (
            <>
              <Field label={fr ? "Nom de la personne" : "اسم الشخص"} placeholder={fr ? "Nom complet" : "الاسم الكامل"} icon={<UserRound size={18} />} value={v.person || ""} onChange={set("person")} />
              <Field label={t.amount} placeholder="0" type="number" step="0.01" icon={<Banknote size={18} />} value={v.amount || ""} onChange={set("amount")} />
            </>
          )}
          {type === "payment" && (
            <>
              <p className="muted">{ctx.debt?.party_name} {t.remaining}: {money(num(ctx.debt?.balance), lang)}</p>
              <Field label={t.amount} placeholder="0" type="number" step="0.01" icon={<Banknote size={18} />} value={v.amount || ""} onChange={set("amount")} />
              <label className="field">
                <span>{t.payment}</span>
                <div className="select-wrap">
                  <select value={v.method} onChange={set("method")}>
                    {PAY_METHODS(t).map((m) => <option key={m[0]} value={m[0]}>{m[1]}</option>)}
                    {num(ctx.debt?.deposit_balance) > 0 && (
                      <option value="deposit">{fr ? `Avance du client (${money(num(ctx.debt.deposit_balance), lang)})` : `سلفة العميل (${money(num(ctx.debt.deposit_balance), lang)})`}</option>
                    )}
                  </select>
                </div>
              </label>
            </>
          )}
          {type === "customer" && (
            <>
              <Field label={fr ? "Nom du client" : "اسم العميل"} icon={<UserRound size={18} />} value={v.person || ""} onChange={set("person")} />
              <Field label={t.phone} required={false} icon={<UserRound size={18} />} value={v.phone || ""} onChange={set("phone")} />
            </>
          )}
                    {type === "product" && (
            <>
              <Field label={fr ? "Nom du produit" : "اسم المنتج"} placeholder={fr ? "Ex. Chewing-gum menthe" : "مثال: علكة"} icon={<Package size={18} />} value={v.name_fr || ""} onChange={set("name_fr")} />
              {editing ? (
                <Field label={fr ? "Unité de base" : "وحدة البيع الأساسية"} disabled icon={<Box size={18} />} value={v.base_unit || ""} onChange={() => {}} />
              ) : (
                <div className="field">
                  <span>{fr ? "Vendu à la / au" : "يُباع بـ"}</span>
                  <div className="category-pills">
                    {BASE_UNITS.map((u) => (
                      <button type="button" key={u} className={v.base_unit === u ? "active" : ""} onClick={() => setV((x) => ({ ...x, base_unit: u }))}>
                        {u}
                      </button>
                    ))}
                    <button type="button" className={!BASE_UNITS.includes(v.base_unit || "") ? "active" : ""} onClick={() => setV((x) => ({ ...x, base_unit: "" }))}>
                      {fr ? "Autre" : "أخرى"}
                    </button>
                  </div>
                  {!BASE_UNITS.includes(v.base_unit || "") && (
                    <div className="input-wrap">
                      <input required placeholder={fr ? "Ex. Mètre, Bouteille…" : "مثال: متر"} value={v.base_unit || ""} onChange={set("base_unit")} />
                    </div>
                  )}
                </div>
              )}
              <MoneyField label={fr ? `Prix de vente (par ${v.base_unit || "unité"})` : "سعر البيع لكل وحدة"} icon={<Banknote size={18} />} value={v.price || ""} onChange={(x: string) => setV((s) => ({ ...s, price: x }))} />
              {editing ? (
                <Field label={fr ? "Autres unités (ex. Carton=12, Boîte=6)" : "وحدات أخرى (مثال: Carton=12)"} required={false} icon={<Box size={18} />} value={v.units || ""} onChange={set("units")} />
              ) : (
                <PackagingBuilder
                  lang={lang}
                  baseUnit={v.base_unit || ""}
                  onChange={(units: string) =>
                    setV((x) => ({
                      ...x,
                      units,
                      stock_unit: parseUnits(units).some((u) => u.name === x.stock_unit) ? x.stock_unit : "",
                    }))
                  }
                />
              )}
              <div className="form-grid">
                <MoneyField label={fr ? "Coût d’achat (par unité de base)" : "تكلفة الشراء"} required={false} icon={<Banknote size={18} />} value={v.cost || ""} onChange={(x: string) => setV((s) => ({ ...s, cost: x }))} />
                <Field label={fr ? "Seuil stock bas" : "حد المخزون المنخفض"} type="number" step="0.001" icon={<AlertTriangle size={18} />} value={v.threshold || ""} onChange={set("threshold")} />
              </div>
              {!editing && (
                <>
                  <div className="form-grid">
                    <Field label={fr ? "Stock reçu (quantité)" : "الكمية المستلمة"} required={false} type="number" step="0.001" icon={<Box size={18} />} value={v.stock_qty || ""} onChange={set("stock_qty")} />
                    <label className="field">
                      <span>{fr ? "Reçu en" : "مستلم بـ"}</span>
                      <div className="select-wrap">
                        <select value={v.stock_unit || ""} onChange={set("stock_unit")}>
                          <option value="">{v.base_unit || "Unité"}</option>
                          {parseUnits(v.units || "").filter((u) => Number(u.factor) > 0).map((u) => <option key={u.name} value={u.name}>{u.name} (×{u.factor})</option>)}
                        </select>
                      </div>
                    </label>
                  </div>
                  {(() => {
                    const q = Number((v.stock_qty || "").replace(",", ".")) || 0;
                    const f = v.stock_unit ? Number(parseUnits(v.units || "").find((u) => u.name === v.stock_unit)?.factor) || 1 : 1;
                    return q > 0 ? (
                      <p className="muted"><b>{formatNumber(+(q * f).toFixed(3), lang)} {v.base_unit}</b>{v.stock_unit ? ` = ${formatNumber(q, lang)} ${v.stock_unit} × ${formatNumber(f, lang)}` : ""} {fr ? "seront ajoutés au stock" : "ستضاف إلى المخزون"}</p>
                    ) : null;
                  })()}
                </>
              )}
              {!editing && !isOwner && (
                <p className="muted">{fr ? "Le prix de vente ne pourra plus être changé que par le propriétaire (mot de passe administrateur)." : "لن يتمكن من تغيير سعر البيع بعد ذلك إلا المالك (بكلمة مرور المدير)."}</p>
              )}
              <Field label={fr ? "Catégorie" : "الفئة"} required={false} icon={<Box size={18} />} value={v.category || ""} onChange={set("category")} />
              {editing && pw()}
            </>
          )}
          

                    {type === "receive" && (
            <>
              <label className="field">
                <span>{fr ? "Produit" : "المنتج"}</span>
                <div className="select-wrap">
                  <select required value={v.product_id || ""} onChange={(e) => setV({ ...v, product_id: e.target.value, unit: "" })}>
                    <option value="">—</option>
                    {(prods || []).map((p) => <option key={p.id} value={p.id}>{p.name_fr}</option>)}
                  </select>
                </div>
              </label>
              <div className="form-grid">
                <label className="field">
                  <span>{fr ? "Unité reçue" : "وحدة الاستلام"}</span>
                  <div className="select-wrap">
                    <select value={v.unit} onChange={set("unit")}>
                      {(prod?.units || []).map((u: any) => <option key={u.name} value={u.name}>{u.name}{u.base ? "" : ` (×${num(u.factor)})`}</option>)}
                    </select>
                  </div>
                </label>
                <Field label={t.quantity} type="number" step="0.001" icon={<Box size={18} />} value={v.qty} onChange={set("qty")} />
              </div>
              {prod && (
                <AddPackagingForm
                  lang={lang}
                  product={prod}
                  onAdded={(n: string) => {
                    refresh();
                    setV((x) => ({ ...x, unit: n }));
                  }}
                />
              )}
              <MoneyField label={fr ? "Coût d’achat par unité reçue" : "تكلفة الشراء لكل وحدة"} required={false} icon={<Banknote size={18} />} value={v.cost || ""} onChange={(x: string) => setV((s) => ({ ...s, cost: x }))} />
              {prod && (() => {
                const q = Number((v.qty || "").replace(",", ".")) || 0;
                const f = Number(prod.units.find((u: any) => u.name === (v.unit || prod.base_unit))?.factor) || 1;
                const total = +(q * f).toFixed(3);
                return (
                  <p className="muted">
                    <b>{formatNumber(q, lang)} {v.unit || prod.base_unit}{f !== 1 ? ` × ${formatNumber(f, lang)}` : ""} = {formatNumber(total, lang)} {prod.base_unit}</b>
                    {" · "}{fr ? "stock après" : "المخزون بعد الإضافة"}: {formatNumber(+(num(prod.stock_qty) + total).toFixed(3), lang)} {prod.base_unit}
                    {v.cost && f > 0 ? ` · ${fr ? "coût par" : "التكلفة لكل"} ${prod.base_unit}: ${formatNumber(+(Number(v.cost) / f).toFixed(2), lang)}` : ""}
                  </p>
                );
              })()}
              <button type="button" className="btn small secondary" onClick={() => { modalStore.data = null; setModal("product"); }}>
                <Plus size={15} />
                {fr ? "Produit introuvable ? Le créer" : "المنتج غير موجود؟ أنشئه"}
              </button>
            </>
          )}


          {type === "quick" && (
            <>
              <Field label={fr ? "Article" : "المنتج"} required={false} placeholder="Article Divers" icon={<FileText size={18} />} value={v.label} onChange={set("label")} />
              <div className="form-grid">
                <Field label={t.quantity} type="number" step="0.001" icon={<Box size={18} />} value={v.qty} onChange={set("qty")} />
                <Field label={fr ? "Unité" : "الوحدة"} required={false} list="quick-units" placeholder="pièce" icon={<Box size={18} />} value={v.unit} onChange={set("unit")} />
              </div>
              <datalist id="quick-units">
                {["pièce", "litre", "kg", "paquet", "boîte", "carton"].map((u) => <option key={u} value={u} />)}
              </datalist>
              <MoneyField label={fr ? "Prix unitaire" : "سعر الوحدة"} icon={<Banknote size={18} />} value={v.price || ""} onChange={(x: string) => setV((s) => ({ ...s, price: x }))} />
              {pm}
            </>
          )}
          {type === "void" && (
            <>
              <p className="muted">{ltr(ctx.invoice?.receipt_no || "")} {money(num(ctx.invoice?.total), lang)}</p>
              <Field label={fr ? "Motif (obligatoire)" : "السبب (إلزامي)"} icon={<FileText size={18} />} value={v.reason || ""} onChange={set("reason")} />
              {pw()}
              <p className="muted">{fr ? "Le stock et la caisse seront corrigés automatiquement. Action enregistrée dans le journal d’audit." : "سيتم تصحيح المخزون والصندوق تلقائياً وتسجيل العملية في سجل التدقيق."}</p>
            </>
          )}
          {type === "backup" && (
            <p className="muted">{fr ? "Branchez votre clé USB puis choisissez le dossier de destination." : "وصّل مفتاح USB ثم اختر المجلد."}</p>
          )}
          {type === "restore" && (
            <>
              <p className="muted">{fr ? "Les données actuelles seront remplacées par la sauvegarde choisie (une copie de sécurité est créée avant)." : "ستُستبدل البيانات الحالية بالنسخة المختارة (تُنشأ نسخة أمان أولاً)."}</p>
              {!window.shopDesktop?.chooseBackupFile && <Field label={fr ? "Chemin du fichier .db" : "مسار الملف"} icon={<FileText size={18} />} value={v.path || ""} onChange={set("path")} />}
              {pw()}
            </>
          )}
          {type === "adminpw" && (
            <>
              {pw(fr ? "Mot de passe administrateur actuel" : "كلمة مرور المدير الحالية")}
              <Field label={fr ? "Nouveau mot de passe administrateur" : "كلمة مرور المدير الجديدة"} type="password" icon={<ShieldCheck size={18} />} value={v.new1 || ""} onChange={set("new1")} />
              <Field label={t.confirmPassword} type="password" icon={<ShieldCheck size={18} />} value={v.new2 || ""} onChange={set("new2")} />
            </>
          )}
          {type === "chpw" && (
            <>
              <Field label={fr ? "Mot de passe actuel" : "كلمة المرور الحالية"} type="password" icon={<LockKeyhole size={18} />} value={v.current || ""} onChange={set("current")} />
              <Field label={t.newPassword} type="password" icon={<LockKeyhole size={18} />} value={v.new1 || ""} onChange={set("new1")} />
              <Field label={t.confirmPassword} type="password" icon={<LockKeyhole size={18} />} value={v.new2 || ""} onChange={set("new2")} />
            </>
          )}
          {type === "pin" && <Field label="PIN (4–8)" type="password" inputMode="numeric" pattern="\d{4,8}" icon={<KeyRound size={18} />} value={v.pin || ""} onChange={set("pin")} />}
          {err && <p className="form-error"><AlertTriangle size={15} />{err}</p>}
          <div className="modal-actions">
            <button type="button" className="btn secondary" onClick={close}>{t.back}</button>
            <button className="btn primary" disabled={busy}>
              {type === "backup" ? (fr ? "Choisir le dossier" : "اختيار المجلد") : t.save}
              <Check size={17} />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function WorkerAccountModal({ t, lang, close, notify, addWorker }: any) {
  const [worker, setWorker] = useState<WorkerAccount | null>(null);
  return (
    <div className="modal-layer">
      <div className="modal-backdrop" onClick={close} />
      <div className="modal worker-modal">
        <div className="modal-head">
          <div>
            <span>{worker ? <Check /> : <Users />}</span>
            <h2>
              {worker
                ? lang === "fr"
                  ? "Compte employé prêt"
                  : "حساب الموظف جاهز"
                : lang === "fr"
                  ? "Ajouter un employé"
                  : "إضافة موظف"}
            </h2>
          </div>
          <button onClick={close}>
            <X />
          </button>
        </div>
        {!worker ? (
          <WorkerSetupForm
            t={t}
            lang={lang}
            cancel={close}
            onCreated={(created: WorkerAccount) => {
              addWorker(created);
              setWorker(created);
            }}
          />
        ) : (
          <div className="credentials-step">
            <CredentialsCard
              lang={lang}
              title={
                lang === "fr" ? "Transmettez cette fiche à l’employé" : "سلّم هذه البطاقة للموظف"
              }
              name={worker.name}
              username={worker.username}
              password={worker.password}
              recoveryCode={worker.recoveryCode}
              notify={notify}
            />
            <button
              className="btn primary full"
              onClick={() => {
                notify(
                  lang === "fr" ? "Employé ajouté à la boutique" : "تمت إضافة الموظف إلى المتجر",
                );
                close();
              }}
            >
              <Check size={18} />
              {lang === "fr" ? "J’ai sauvegardé la fiche" : "حفظت البطاقة"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function ReceiptModal({ t, lang, close, notify }: any) {
  const inv = receiptStore.invoice;
  const [size, setSize] = useState("58");
  const doPrint = async (pdf: boolean) => {
    let st = document.getElementById("page-size-style");
    if (!st) {
      st = document.createElement("style");
      st.id = "page-size-style";
      document.head.appendChild(st);
    }
    st.textContent = size === "A4" ? "@page{size:A4;margin:12mm}" : `@page{size:${size}mm auto;margin:2mm}`;
    if (window.shopDesktop) {
      if (pdf) {
        const f = await window.shopDesktop.savePdf?.(size, inv.receipt_no);
        if (f) notify(lang === "fr" ? "PDF enregistré" : "تم حفظ PDF");
      } else if (await window.shopDesktop.printReceipt?.(size)) notify(lang === "fr" ? "Impression envoyée" : "تم إرسال الطباعة");
    } else window.print(); // browser: choose a printer or "Save as PDF"
  };
  const shareText = () => {
    const text = [inv.shop.name, inv.receipt_no, ...inv.lines.map((l: any) => `${l.label} ${l.quantity} ${l.unit_name} = ${l.line_total}`), `TOTAL ${inv.total} FCFA`].join("\n");
    void navigator.clipboard?.writeText(text);
    notify(lang === "fr" ? "Reçu copié" : "تم نسخ الإيصال");
  };
  if (!inv) return null;
  const bodyRef = useRef<HTMLDivElement>(null);
  const paperRef = useRef<HTMLDivElement>(null);
  // Width of the preview area's content box (padding, scrollbar and scrollbar-gutter excluded)
  const [avail, setAvail] = useState(0);
  useLayoutEffect(() => {
    const el = bodyRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setAvail(entry.contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  // The paper's real width lives in CSS (--paper-w on .paper-58/-80/-A4): single source of truth.
  const paperW = (() => {
    const el = paperRef.current;
    const v = el ? parseFloat(getComputedStyle(el).getPropertyValue("--paper-w")) : NaN;
    return Number.isFinite(v) && v > 0 ? v : 0;
  })();
  const fit = avail > 0 && paperW > 0 ? Math.min(1, Math.floor((avail / paperW) * 1000) / 1000) : 1;
  // Re-measure after the size class changes so a stale --paper-w is never used
  const [, force] = useState(0);
  useLayoutEffect(() => force((n) => n + 1), [size]);
  return (
    <div className="modal-layer receipt-layer">
      <div className="modal-backdrop" onClick={close} />
      <div className="receipt-modal">
        <div className="receipt-toolbar">
          <div>
            <button onClick={close}>
              <X />
            </button>
            <h2>
              {t.receipt} <span>{ltr(inv.receipt_no)}</span>
            </h2>
          </div>
          <div className="receipt-sizes">
            {["58", "80", "A4"].map((x) => (
              <button className={size === x ? "active" : ""} onClick={() => setSize(x)} key={x}>
                {ltr(x !== "A4" ? `${x} mm` : x)}
              </button>
            ))}
          </div>
        </div>
        <div className="receipt-body" ref={bodyRef}>
          <div ref={paperRef} className={`paper paper-${size}`} style={{ zoom: fit } as any}>
            <div className="paper-logo">
              <Store />
              <b>{inv.shop.name}</b>
              <span>{ltr(inv.shop.phone || "")} {inv.shop.city ? `· ${inv.shop.city}` : ""}</span>
            </div>
            <div className="receipt-meta">
              <span>{t.newReceipt}</span>
              <b>{ltr(inv.receipt_no)}</b>
              <span>{lang === "fr" ? "Date" : "التاريخ"}</span>
              <b>{new Date(inv.created_at).toLocaleString(lang === "ar" ? "ar-MA" : "fr-FR", { dateStyle: "short", timeStyle: "short" })}</b>
              <span>{t.worker}</span>
              <b>{inv.worker.name}</b>
            </div>
            <div className="receipt-lines">
              <div>
                <b>{lang === "fr" ? "Article" : "المنتج"}</b>
                <b>{t.total}</b>
              </div>
              {inv.lines.map((l: any) => (
                <div key={l.id}>
                  <span>
                    {l.label}
                    <small>{l.quantity} {l.unit_name} × {money(num(l.unit_price), lang)}</small>
                  </span>
                  <b>{money(num(l.line_total), lang)}</b>
                </div>
              ))}
            </div>
            {inv.status === "VOIDED" && <p className="receipt-thanks"><b>{lang === "fr" ? "ANNULÉE" : "ملغاة"}</b></p>}
            <div className="receipt-total">
              <span>{t.total}</span>
              <strong>{money(num(inv.total), lang)}</strong>
            </div>
            <div className="receipt-payment">
              <span>{t.payment}</span>
              <b>{inv.payment_method === "cash" ? t.cash : inv.payment_method === "credit" ? (lang === "fr" ? "À crédit" : "بالدين") : inv.payment_method}</b>
              <span>{lang === "fr" ? "Montant payé" : "المبلغ المدفوع"}</span>
              <b>{money(num(inv.paid_amount), lang)}</b>
            </div>
            <p className="receipt-thanks">
              {t.thanks}
              <small>{inv.shop.name}</small>
            </p>
          </div>
        </div>
        <div className="receipt-actions">
          <button
            className="btn secondary"
            onClick={() => void doPrint(true)}
          >
            <Download size={18} />
            {t.download}
          </button>
          <button
            className="btn secondary"
            onClick={shareText}
          >
            <Share2 size={18} />
            {t.share}
          </button>
          <button
            className="btn primary"
            onClick={() => void doPrint(false)}
          >
            <Printer size={18} />
            {t.print}
          </button>
        </div>
      </div>
    </div>
  );
}

// Isolate Latin phone numbers / IDs so RTL text can't reorder them
const ltr = (value: string) => `\u2066${value}\u2069`;
function money(value: number, lang: Lang) {
  const locale = lang === "ar" ? "ar-MA" : "fr-FR";
  const text = `${new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(value)} FCFA`;
  // Keep "amount FCFA" in reading order inside RTL text (LRI … PDI isolate)
  return lang === "ar" ? `\u2066${text}\u2069` : text;
}
function hhmm(iso: string, lang: Lang) {
  return new Date(iso).toLocaleTimeString(lang === "ar" ? "ar-MA" : "fr-FR", { hour: "2-digit", minute: "2-digit" });
}
function formatNumber(value: number, lang: Lang) {
  return new Intl.NumberFormat(lang === "ar" ? "ar-MA" : "fr-FR").format(value);
}
function formatDate(lang: Lang) {
  return new Intl.DateTimeFormat(lang === "ar" ? "ar-MA" : "fr-FR", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(new Date(2026, 4, 14));
}

export default App;

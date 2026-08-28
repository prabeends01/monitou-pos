import { Badge, Button, Tab, TabList, makeStyles, tokens } from "@fluentui/react-components";
import { useState } from "react";

import { AppServicesProvider, useAppServices } from "./AppContext";
import FeatureGate from "./components/FeatureGate";
import BarcodeAdmin from "./screens/BarcodeAdmin";
import Dashboard from "./screens/Dashboard";
import Login from "./screens/Login";
import PlanSubscription from "./screens/PlanSubscription";
import PosBilling from "./screens/PosBilling";
import ProductAdmin from "./screens/ProductAdmin";
import Reports from "./screens/Reports";
import StockAdmin from "./screens/StockAdmin";
import PlatformAdminApp from "./platformAdmin/PlatformAdminApp";
import PlatformAdminLogin from "./platformAdmin/PlatformAdminLogin";
import { usePlatformAdminStore } from "./stores/platformAdminStore";
import { useSessionStore } from "./stores/sessionStore";
import type { Role } from "./types";

type TabKey = "pos" | "reports" | "dashboard" | "products" | "stock" | "barcodes" | "settings";

interface NavItem {
  key: TabKey;
  label: string;
  /** Plan-entitlement layer — checked via FeatureGate (CLAUDE.md Section
   * 11.7). Every existing screen maps to a feature every plan currently
   * enables (see Section 11.5's Basic list), so this is a no-op for them
   * today; "barcodes" is the first one where it actually differs by plan.
   * Omitted for "settings" — the Plan & Subscription page must stay
   * reachable on every plan (including exactly the plans it's telling you
   * to upgrade off of), so it isn't itself a gated catalog feature. */
  requiredFeature?: string;
  /** RBAC layer — a *different* check than the one above (Section 11's
   * "Tenant Entitlement + ... + User Permission" principle): a Basic
   * tenant's sales user is blocked by role regardless of plan, and an
   * Enterprise tenant's sales user is still blocked by role too. */
  adminOnly?: boolean;
  render: () => React.ReactNode;
}

const NAV_ITEMS: NavItem[] = [
  { key: "pos", label: "POS Billing", requiredFeature: "BASIC_SALES_ORDER", render: () => <PosBilling /> },
  { key: "reports", label: "Sales history", requiredFeature: "BASIC_SALES_ORDER", render: () => <Reports /> },
  {
    key: "dashboard",
    label: "Dashboard",
    requiredFeature: "BASIC_DASHBOARD",
    adminOnly: true,
    render: () => <Dashboard />,
  },
  {
    key: "products",
    label: "Products",
    requiredFeature: "PRODUCT_MASTER",
    adminOnly: true,
    render: () => <ProductAdmin />,
  },
  {
    key: "stock",
    label: "Stock",
    requiredFeature: "STOCK_ADJUSTMENT",
    adminOnly: true,
    render: () => <StockAdmin />,
  },
  {
    key: "barcodes",
    label: "Barcodes",
    requiredFeature: "BARCODE_GENERATION",
    adminOnly: true,
    render: () => <BarcodeAdmin />,
  },
  {
    key: "settings",
    label: "Settings",
    adminOnly: true,
    render: () => <PlanSubscription />,
  },
];

const useStyles = makeStyles({
  shell: {
    display: "flex",
    flexDirection: "column",
    height: "100%",
    backgroundColor: tokens.colorNeutralBackground1,
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "10px 16px",
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    backgroundColor: tokens.colorNeutralBackground2,
  },
  headerLeft: {
    display: "flex",
    alignItems: "center",
    gap: "20px",
  },
  wordmark: {
    fontSize: "15px",
    fontWeight: 700,
    letterSpacing: "0.1em",
    color: tokens.colorNeutralForeground1,
    textTransform: "uppercase",
    whiteSpace: "nowrap",
  },
  wordmarkAccent: {
    color: tokens.colorBrandForeground1,
  },
  headerRight: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
  },
  content: {
    flex: 1,
    overflow: "auto",
  },
});

function visibleFor(item: NavItem, role: Role | null): boolean {
  return !item.adminOnly || role === "admin";
}

function MainApp() {
  const styles = useStyles();
  const { api } = useAppServices();
  const role = useSessionStore((s) => s.role);
  const username = useSessionStore((s) => s.username);
  const logOut = useSessionStore((s) => s.logOut);
  const [tab, setTab] = useState<TabKey>("pos");

  const rbacVisible = NAV_ITEMS.filter((item) => visibleFor(item, role));
  const activeItem = rbacVisible.find((item) => item.key === tab);

  return (
    <div className={styles.shell}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <div className={styles.wordmark}>
            MONI<span className={styles.wordmarkAccent}>TOU</span>
          </div>
          <TabList selectedValue={tab} onTabSelect={(_, data) => setTab(data.value as TabKey)}>
            {rbacVisible.map((item) =>
              item.requiredFeature ? (
                <FeatureGate key={item.key} feature={item.requiredFeature} mode="hide">
                  <Tab value={item.key}>{item.label}</Tab>
                </FeatureGate>
              ) : (
                <Tab key={item.key} value={item.key}>
                  {item.label}
                </Tab>
              ),
            )}
          </TabList>
        </div>
        <div className={styles.headerRight}>
          {role && <Badge appearance="tint" color={role === "admin" ? "brand" : "informative"}>{role}</Badge>}
          <Button size="small" onClick={() => logOut(api)}>
            Log out {username ? `(${username})` : ""}
          </Button>
        </div>
      </div>
      <div className={styles.content}>
        {activeItem &&
          (activeItem.requiredFeature ? (
            <FeatureGate feature={activeItem.requiredFeature} mode="hide">
              {activeItem.render()}
            </FeatureGate>
          ) : (
            activeItem.render()
          ))}
      </div>
    </div>
  );
}

function Shell() {
  const role = useSessionStore((s) => s.role);
  const platformAdminUsername = usePlatformAdminStore((s) => s.username);
  const [loginMode, setLoginMode] = useState<"tenant" | "platform-admin">("tenant");

  // Platform Admin and tenant sessions are two independent credential
  // spaces (CLAUDE.md Section 11.9.6/Stage 11) — a platform-admin session
  // always wins here since it can only ever exist by an explicit,
  // separate sign-in, not as a side effect of any tenant action.
  if (platformAdminUsername) return <PlatformAdminApp />;
  if (role) return <MainApp />;
  if (loginMode === "platform-admin") return <PlatformAdminLogin onBack={() => setLoginMode("tenant")} />;
  return <Login onPlatformAdminLogin={() => setLoginMode("platform-admin")} />;
}

export default function App() {
  return (
    <AppServicesProvider>
      <Shell />
    </AppServicesProvider>
  );
}

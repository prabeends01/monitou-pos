import { Badge, Button, Tab, TabList, makeStyles, tokens } from "@fluentui/react-components";
import { useState } from "react";

import { AppServicesProvider, useAppServices } from "./AppContext";
import Dashboard from "./screens/Dashboard";
import Login from "./screens/Login";
import PosBilling from "./screens/PosBilling";
import ProductAdmin from "./screens/ProductAdmin";
import Reports from "./screens/Reports";
import StockAdmin from "./screens/StockAdmin";
import { useSessionStore } from "./stores/sessionStore";

type TabKey = "pos" | "reports" | "dashboard" | "products" | "stock";

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

function MainApp() {
  const styles = useStyles();
  const { api } = useAppServices();
  const role = useSessionStore((s) => s.role);
  const username = useSessionStore((s) => s.username);
  const logOut = useSessionStore((s) => s.logOut);
  const [tab, setTab] = useState<TabKey>("pos");

  return (
    <div className={styles.shell}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <div className={styles.wordmark}>
            MONI<span className={styles.wordmarkAccent}>TOU</span>
          </div>
          <TabList selectedValue={tab} onTabSelect={(_, data) => setTab(data.value as TabKey)}>
            <Tab value="pos">POS Billing</Tab>
            <Tab value="reports">Sales history</Tab>
            {role === "admin" && <Tab value="dashboard">Dashboard</Tab>}
            {role === "admin" && <Tab value="products">Products</Tab>}
            {role === "admin" && <Tab value="stock">Stock</Tab>}
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
        {tab === "pos" && <PosBilling />}
        {tab === "reports" && <Reports />}
        {tab === "dashboard" && role === "admin" && <Dashboard />}
        {tab === "products" && role === "admin" && <ProductAdmin />}
        {tab === "stock" && role === "admin" && <StockAdmin />}
      </div>
    </div>
  );
}

function Shell() {
  const role = useSessionStore((s) => s.role);
  return role ? <MainApp /> : <Login />;
}

export default function App() {
  return (
    <AppServicesProvider>
      <Shell />
    </AppServicesProvider>
  );
}

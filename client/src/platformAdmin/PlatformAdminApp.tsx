import { Badge, Button, Tab, TabList, makeStyles, tokens } from "@fluentui/react-components";
import { useState } from "react";

import { useAppServices } from "../AppContext";
import { usePlatformAdminStore } from "../stores/platformAdminStore";
import PlatformAdminDashboard from "./PlatformAdminDashboard";
import PlatformAdminTenants from "./PlatformAdminTenants";
import PlatformAdminUpgradeRequests from "./PlatformAdminUpgradeRequests";

type TabKey = "dashboard" | "tenants" | "upgrade-requests";

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
    // deliberately different chrome from MainApp's header (App.tsx) — this
    // is not "the tenant app with an extra tab," it's a visibly separate
    // internal surface (CLAUDE.md Section 11.13).
    backgroundColor: tokens.colorPaletteDarkOrangeBackground2,
  },
  headerLeft: {
    display: "flex",
    alignItems: "center",
    gap: "20px",
  },
  wordmark: {
    fontSize: "13px",
    fontWeight: 700,
    letterSpacing: "0.12em",
    textTransform: "uppercase",
    whiteSpace: "nowrap",
  },
  content: {
    flex: 1,
    overflow: "auto",
  },
});

export default function PlatformAdminApp() {
  const styles = useStyles();
  const { api } = useAppServices();
  const username = usePlatformAdminStore((s) => s.username);
  const logOut = usePlatformAdminStore((s) => s.logOut);
  const [tab, setTab] = useState<TabKey>("dashboard");

  return (
    <div className={styles.shell}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <div className={styles.wordmark}>Platform Admin</div>
          <TabList selectedValue={tab} onTabSelect={(_, data) => setTab(data.value as TabKey)}>
            <Tab value="dashboard">Dashboard</Tab>
            <Tab value="tenants">Tenants</Tab>
            <Tab value="upgrade-requests">Upgrade requests</Tab>
          </TabList>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Badge appearance="filled" color="danger">
            internal
          </Badge>
          <Button size="small" onClick={() => logOut(api)}>
            Log out {username ? `(${username})` : ""}
          </Button>
        </div>
      </div>
      <div className={styles.content}>
        {tab === "dashboard" && <PlatformAdminDashboard />}
        {tab === "tenants" && <PlatformAdminTenants />}
        {tab === "upgrade-requests" && <PlatformAdminUpgradeRequests />}
      </div>
    </div>
  );
}

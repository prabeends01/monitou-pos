import {
  Button,
  Field,
  Input,
  MessageBar,
  MessageBarActions,
  MessageBarBody,
  makeStyles,
  tokens,
} from "@fluentui/react-components";
import { useState } from "react";

import { ApiError } from "../api/client";
import { useAppServices } from "../AppContext";
import LoginBackground from "../components/LoginBackground";
import { saveSession } from "../session";
import { useSessionStore } from "../stores/sessionStore";
import type { Role } from "../types";

const useStyles = makeStyles({
  root: {
    position: "relative",
    height: "100%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  },
  card: {
    position: "relative",
    zIndex: 1,
    width: "380px",
    padding: "40px 36px",
    borderRadius: tokens.borderRadiusXLarge,
    backgroundColor: "rgba(255, 255, 255, 0.92)",
    backdropFilter: "blur(14px)",
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    boxShadow: "0 24px 60px -16px rgba(20, 20, 20, 0.25), 0 4px 16px -4px rgba(20, 20, 20, 0.1)",
    display: "flex",
    flexDirection: "column",
    gap: "20px",
  },
  brandRow: {
    display: "flex",
    flexDirection: "column",
    gap: "4px",
    marginBottom: "4px",
  },
  wordmark: {
    fontSize: "26px",
    fontWeight: 700,
    letterSpacing: "0.14em",
    color: tokens.colorNeutralForeground1,
    textTransform: "uppercase",
  },
  wordmarkAccent: {
    color: tokens.colorBrandForeground1,
  },
  tagline: {
    fontSize: "12px",
    letterSpacing: "0.12em",
    textTransform: "uppercase",
    color: tokens.colorNeutralForeground3,
  },
  divider: {
    height: "1px",
    background: `linear-gradient(90deg, ${tokens.colorBrandBackground} 0%, transparent 70%)`,
    opacity: 0.6,
  },
  form: {
    display: "flex",
    flexDirection: "column",
    gap: "14px",
  },
  submit: {
    marginTop: "6px",
  },
});

export default function Login() {
  const styles = useStyles();
  const { api } = useAppServices();
  const loggedIn = useSessionStore((s) => s.loggedIn);
  const loggedOutReason = useSessionStore((s) => s.loggedOutReason);
  const clearLoggedOutReason = useSessionStore((s) => s.clearLoggedOutReason);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!username || !password) {
      setError("Enter username and password");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const role = await api.login(username, password);
      if (api.token) await saveSession({ token: api.token, role: role as Role, username });
      loggedIn(role as Role, username);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("Incorrect username or password");
      } else {
        setError(err instanceof Error ? err.message : "Cannot reach server");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className={styles.root}>
      <LoginBackground />
      <form className={styles.card} onSubmit={handleSubmit}>
        <div className={styles.brandRow}>
          <div className={styles.wordmark}>
            MONI<span className={styles.wordmarkAccent}>TOU</span>
          </div>
          <div className={styles.tagline}>Spare Parts · POS &amp; Inventory</div>
        </div>
        <div className={styles.divider} />
        {loggedOutReason && (
          <MessageBar intent="warning">
            <MessageBarBody>{loggedOutReason}</MessageBarBody>
            <MessageBarActions>
              <Button appearance="transparent" size="small" onClick={clearLoggedOutReason}>
                Dismiss
              </Button>
            </MessageBarActions>
          </MessageBar>
        )}
        <div className={styles.form}>
          <Field label="Username">
            <Input value={username} onChange={(_, data) => setUsername(data.value)} autoFocus size="large" />
          </Field>
          <Field label="Password" validationMessage={error ?? undefined} validationState={error ? "error" : "none"}>
            <Input
              type="password"
              value={password}
              onChange={(_, data) => setPassword(data.value)}
              size="large"
            />
          </Field>
          <Button className={styles.submit} appearance="primary" type="submit" size="large" disabled={submitting}>
            {submitting ? "Logging in…" : "Log in"}
          </Button>
        </div>
      </form>
    </div>
  );
}

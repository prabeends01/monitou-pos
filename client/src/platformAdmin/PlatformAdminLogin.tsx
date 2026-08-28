import { Button, Field, Input, MessageBar, MessageBarBody, makeStyles, tokens } from "@fluentui/react-components";
import { useState } from "react";

import { useAppServices } from "../AppContext";
import { ApiError } from "../api/client";
import { usePlatformAdminStore } from "../stores/platformAdminStore";

const useStyles = makeStyles({
  root: {
    height: "100%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: tokens.colorNeutralBackground3,
  },
  card: {
    width: "360px",
    padding: "36px 32px",
    borderRadius: tokens.borderRadiusXLarge,
    backgroundColor: tokens.colorNeutralBackground1,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    boxShadow: "0 24px 60px -16px rgba(20, 20, 20, 0.25)",
    display: "flex",
    flexDirection: "column",
    gap: "16px",
  },
  wordmark: {
    fontSize: "13px",
    fontWeight: 700,
    letterSpacing: "0.14em",
    textTransform: "uppercase",
    color: tokens.colorNeutralForeground3,
  },
  form: {
    display: "flex",
    flexDirection: "column",
    gap: "14px",
  },
});

/** A deliberately plain, separate login — no shop code field, no
 * persisted session, different visual chrome from the tenant Login.tsx.
 * This is not "the same login with extra permissions"; it authenticates
 * against a completely different credential space (CLAUDE.md Stage 11). */
export default function PlatformAdminLogin({ onBack }: { onBack: () => void }) {
  const styles = useStyles();
  const { api } = useAppServices();
  const loggedIn = usePlatformAdminStore((s) => s.loggedIn);
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
      await api.platformAdminLogin(username, password);
      loggedIn(username);
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
      <form className={styles.card} onSubmit={handleSubmit}>
        <div className={styles.wordmark}>Monitou · Platform Admin</div>
        <MessageBar intent="warning">
          <MessageBarBody>Internal use only. This is a separate account from any shop's login.</MessageBarBody>
        </MessageBar>
        <div className={styles.form}>
          <Field label="Username">
            <Input value={username} onChange={(_, d) => setUsername(d.value)} autoFocus />
          </Field>
          <Field label="Password" validationMessage={error ?? undefined} validationState={error ? "error" : "none"}>
            <Input type="password" value={password} onChange={(_, d) => setPassword(d.value)} />
          </Field>
          <Button appearance="primary" type="submit" disabled={submitting}>
            {submitting ? "Signing in…" : "Sign in"}
          </Button>
        </div>
        <Button appearance="transparent" size="small" onClick={onBack} type="button">
          ← Back to shop login
        </Button>
      </form>
    </div>
  );
}

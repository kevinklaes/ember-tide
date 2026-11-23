import { useState } from "react";
import { api } from "../api";
import type { OuraStatus } from "./Oura";

/**
 * Connect a cloud account by a key the person makes themselves (Garmin's Personal API key). The key goes to this home's
 * server once, which checks it with Garmin and keeps it encrypted; it never comes back. The field is cleared after every
 * try. Server: core/embertide/cloud/garmin.py (connect_kind = "key").
 */

const KEY_PAGE = "https://connect.garmin.com/app/settings/personalApiToken";

const ago = (t: number) => {
  const s = Date.now() / 1000 - t;
  return s < 120 ? "just now" : s < 3600 ? `${Math.round(s / 60)} min ago` : s < 86400 ? `${Math.round(s / 3600)} h ago` : `${Math.round(s / 86400)} days ago`;
};

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

/** "2026-11-30" → "30 November" (the day the person typed; no time zone shift). */
const dayMonth = (s: string) => {
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { day: "numeric", month: "long" });
};

export default function KeyConnect({ provider, name, person, st, compact, reload }: {
  provider: string; name: string; person: string; st: OuraStatus; compact: boolean; reload: () => void;
}) {
  const [key, setKey] = useState("");
  const [until, setUntil] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [replacing, setReplacing] = useState(false);

  const run = async (label: string, f: () => Promise<unknown>) => {
    setBusy(label); setMsg(null);
    try { await f(); return true; } catch (e) { setMsg((e as Error).message); return false; } finally { setBusy(null); reload(); }
  };
  const connect = async () => {
    const k = key.trim();
    setKey("");                                    // cleared whether or not it works
    const ok = await run("connect", () => api.post(`/api/cloud/me/${provider}/connect`, { person, key: k, expires: until || null }));
    if (ok) { setUntil(""); setReplacing(false); }
  };

  const today = new Date();
  const max = new Date(today); max.setFullYear(today.getFullYear() + 1);
  const connected = st.connected && !st.needs_reconnect;
  const showForm = !connected || replacing;

  const soon = connected && st.key_expires_soon && st.key_expires
    ? (st.key_expires >= iso(today)
      ? `Your ${name} key runs out on ${dayMonth(st.key_expires)}. Make a new one at ${name} Connect and paste it here.`
      : `Your ${name} key was due to run out on ${dayMonth(st.key_expires)}. If nights stop arriving, make a new one at ${name} Connect and paste it here.`)
    : null;

  return (
    <div className={`keycard${compact ? " compact" : ""}`}>
      {connected && <>
        <div className="row"><span><b style={{ fontWeight: 500 }}>{name} connected</b><br />
          <small className="mute">{st.last_sync ? `Last looked ${ago(st.last_sync)}` : "First look in a moment"}. It checks after you wake, then every hour.</small></span>
          <button className="pill" disabled={!!busy} onClick={() => run("sync", () => api.post(`/api/cloud/me/${provider}/sync`, { person }))}>{busy === "sync" ? "Looking…" : "Look now"}</button></div>
        {soon && <p className="warn-text">{soon}</p>}
        {st.last_error && <p className="warn-text">{st.last_error}</p>}
        {!replacing && <div className="keycard-acts">
          <button className="pill" disabled={!!busy} onClick={() => { setReplacing(true); setMsg(null); }}>Replace key</button>
          <button className="link" disabled={!!busy} onClick={() => run("off", () => api.post(`/api/cloud/me/${provider}/disconnect`, { person }))}>{busy === "off" ? "Disconnecting…" : `Disconnect ${name}`}</button>
        </div>}
        {!replacing && <small className="mute">You can also delete the key at {name} Connect.</small>}
      </>}
      {st.needs_reconnect && <p className="warn-text">{st.last_error || `Your ${name} key has run out or was deleted. Make a new one at ${name} Connect and paste it here.`}</p>}
      {showForm && <>
        <ol className="keycard-steps mute">
          <li>Open {name} Connect on the web and go to your Personal API key page.{" "}
            <a className="keycard-out" href={KEY_PAGE} target="_blank" rel="noreferrer">Open {name}'s key page</a></li>
          <li>Choose Create Key and accept {name}'s terms there.</li>
          <li>Choose how long it lasts and copy the key. {name} shows it only once.</li>
          <li>Paste it here.</li>
        </ol>
        <div className="keycard-fields">
          <label className="field"><span>Your {name} key</span>
            <input type="password" autoComplete="off" spellCheck={false} autoCapitalize="off" autoCorrect="off"
              value={key} disabled={!!busy} onChange={e => setKey(e.target.value)} /></label>
          <label className="field"><span>Runs out on (optional)</span>
            <input type="date" min={iso(today)} max={iso(max)} value={until} disabled={!!busy} onChange={e => setUntil(e.target.value)} />
            <small className="mute">Add the date and this card reminds you a week before.</small></label>
        </div>
        <small className="mute">Use only your own key. It stays on this home's server and is used only to read your sleep, heart rate and HRV from {name}.</small>
        <div className="keycard-acts">
          <button className="btn pri" disabled={!!busy || !key.trim()} onClick={connect}>{busy === "connect" ? "Connecting…" : `Connect ${name}`}</button>
          {replacing && <button className="btn" disabled={!!busy} onClick={() => { setReplacing(false); setKey(""); setUntil(""); setMsg(null); }}>Cancel</button>}
        </div>
      </>}
      {msg && <p className="warn-text" role="alert">{msg}</p>}
    </div>
  );
}

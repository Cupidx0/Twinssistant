import React, { useEffect, useState } from "react";
import { Refresh, WarningAmber } from "@mui/icons-material";
import { CostAPI } from "../../Utils/Assistant";

const gbp = (n, digits = 2) => `£${Number(n || 0).toFixed(digits)}`;
const LABELS = {
  "claude-haiku-5-5": "Haiku 5.5",
  "claude-sonnet-5-5": "Sonnet 5.5",
  "claude-opus-5-5": "Opus 5.5",
  "text-embedding-3-small": "Embeddings",
  tavily_search: "Tavily search",
  elevenlabs_chars: "ElevenLabs voice",
};

function Meter({ value, max, label }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs text-muted-foreground">
        <span>{label}</span>
        <span className="font-mono text-foreground">
          {gbp(value)} / {gbp(max, 0)}
        </span>
      </div>
      <div
        className="h-2 overflow-hidden rounded-full bg-muted"
        role="meter"
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={value}
        aria-label={label}
      >
        <div className="h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

// One series, one hue: bars are ranked, each row names its value in text.
function BarList({ title, data, formatKey = (k) => LABELS[k] || k }) {
  const rows = Object.entries(data || {}).sort((a, b) => b[1] - a[1]);
  const max = Math.max(...rows.map(([, v]) => v), 0);
  return (
    <div className="glass rounded-2xl p-4">
      <h3 className="m-0 mb-3 text-[11px] font-bold uppercase tracking-[0.14em] text-muted-foreground">{title}</h3>
      {rows.length === 0 ? (
        <p className="m-0 text-sm text-muted-foreground">Nothing logged yet.</p>
      ) : (
        <div className="flex flex-col gap-2">
          {rows.map(([k, v]) => (
            <div key={k} className="grid grid-cols-[minmax(0,9rem)_1fr_4.5rem] items-center gap-3 text-[13px]" title={`${formatKey(k)}: ${gbp(v, 4)}`}>
              <span className="truncate text-foreground">{formatKey(k)}</span>
              <div className="h-3 rounded-r bg-muted/40">
                <div className="h-full rounded-r bg-primary" style={{ width: `${max ? Math.max((v / max) * 100, 1.5) : 0}%` }} />
              </div>
              <span className="text-right font-mono text-muted-foreground">{gbp(v, v < 0.1 ? 3 : 2)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function DailyBars({ byDay }) {
  const days = Object.entries(byDay || {});
  const max = Math.max(...days.map(([, v]) => v), 0);
  return (
    <div className="glass rounded-2xl p-4">
      <h3 className="m-0 mb-3 text-[11px] font-bold uppercase tracking-[0.14em] text-muted-foreground">Spend per day</h3>
      {days.length === 0 ? (
        <p className="m-0 text-sm text-muted-foreground">Nothing logged yet.</p>
      ) : (
        <>
          <div className="flex h-32 items-end gap-[2px]" role="img" aria-label="Daily spend this month">
            {days.map(([d, v]) => (
              <div key={d} className="group relative flex h-full flex-1 items-end">
                <div
                  className="w-full rounded-t bg-primary transition group-hover:brightness-125"
                  style={{ height: `${max ? Math.max((v / max) * 100, 2) : 0}%` }}
                />
                <span className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-1 hidden -translate-x-1/2 whitespace-nowrap rounded-md border border-border bg-card px-2 py-1 font-mono text-[11px] text-foreground group-hover:block">
                  {d.slice(5)} · {gbp(v, 3)}
                </span>
              </div>
            ))}
          </div>
          <div className="mt-1 flex justify-between font-mono text-[10.5px] text-muted-foreground">
            <span>{days[0][0].slice(5)}</span>
            <span>{days[days.length - 1][0].slice(5)}</span>
          </div>
        </>
      )}
    </div>
  );
}

export default function Usage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const load = () => {
    setLoading(true);
    setError("");
    CostAPI.fetchCosts()
      .then(setData)
      .catch((e) => setError(e.response?.data?.error || "Could not load usage."))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  const saving = data ? data.claude_pro_gbp - data.total_gbp : 0;
  return (
    <div className="mx-auto flex max-w-[860px] flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="m-0 text-2xl font-semibold">Usage &amp; costs</h1>
        <button onClick={load} disabled={loading} className="flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 text-xs font-semibold text-muted-foreground hover:text-foreground disabled:opacity-50">
          <Refresh sx={{ fontSize: 14 }} className={loading ? "animate-spin" : ""} /> Refresh
        </button>
      </div>
      {error ? <p className="m-0 text-sm text-destructive">{error}</p> : null}
      {data ? (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="glass rounded-2xl p-4">
              <div className="text-[11px] font-bold uppercase tracking-[0.14em] text-muted-foreground">This month</div>
              <div className="mt-1 text-[32px] font-semibold tracking-tight">{gbp(data.total_gbp)}</div>
              <div className="text-xs text-muted-foreground">{data.requests} logged calls · {data.month}</div>
            </div>
            <div className="glass rounded-2xl p-4">
              <div className="text-[11px] font-bold uppercase tracking-[0.14em] text-muted-foreground">vs Claude Pro</div>
              <div className="mt-1 text-[32px] font-semibold tracking-tight">{gbp(Math.abs(saving))}</div>
              <div className="text-xs text-muted-foreground">{saving >= 0 ? "saved" : "over"} against {gbp(data.claude_pro_gbp, 0)}/month</div>
            </div>
            <div className="glass flex flex-col justify-center gap-3 rounded-2xl p-4">
              <Meter value={data.total_gbp} max={data.claude_pro_gbp} label="Claude Pro price" />
              <Meter value={data.total_gbp} max={data.budget_gbp} label="Your budget" />
            </div>
          </div>
          {data.over_budget ? (
            <p className="m-0 flex items-center gap-2 rounded-xl border border-warning/40 bg-warning/10 px-4 py-2 text-sm text-warning">
              <WarningAmber sx={{ fontSize: 16 }} /> Budget reached: chat now uses the cheaper model except writing and grading.
            </p>
          ) : null}
          <DailyBars byDay={data.by_day} />
          <div className="grid gap-4 md:grid-cols-2">
            <BarList title="By model or service" data={data.by_model} />
            <BarList title="By feature" data={data.by_feature} formatKey={(k) => k.replace(/_/g, " ")} />
          </div>
          <p className="m-0 text-xs text-muted-foreground">
            Estimates from logged tokens and list prices, converted at the USD_TO_GBP rate in .env. Check provider bills for exact figures.
          </p>
        </>
      ) : !error ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : null}
    </div>
  );
}

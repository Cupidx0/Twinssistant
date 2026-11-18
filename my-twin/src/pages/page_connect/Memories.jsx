import React, { useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import { DeleteOutline, EditOutlined, Check, Close } from "@mui/icons-material";
import { MemoryAPI } from "../../Utils/Assistant";

const input =
  "w-full rounded-[10px] border border-border bg-secondary px-3 py-2 text-[13px] text-foreground outline-none placeholder:text-muted-foreground focus:border-primary/40";
const card = "glass rounded-2xl p-4";
const heading = "m-0 mb-3 text-[11px] font-bold uppercase tracking-[0.14em] text-muted-foreground";

function ProfileCard() {
  const [profile, setProfile] = useState({ name: "", course: "", location: "", goals: "", preferences: "", about: "" });
  useEffect(() => {
    MemoryAPI.getProfile()
      .then(({ profile: p = {} }) =>
        setProfile((cur) => ({
          ...cur,
          ...p,
          preferences: Array.isArray(p.preferences) ? p.preferences.join(", ") : p.preferences || "",
        })),
      )
      .catch(() => {});
  }, []);
  const save = async () => {
    try {
      await MemoryAPI.saveProfile({
        ...profile,
        preferences: profile.preferences.split(",").map((s) => s.trim()).filter(Boolean),
      });
      toast.success("Profile saved");
    } catch {
      toast.error("Could not save profile");
    }
  };
  const field = (key, label, multiline) => (
    <label className="flex flex-col gap-1 text-xs text-muted-foreground">
      {label}
      {multiline ? (
        <textarea rows={2} className={input} value={profile[key] || ""} onChange={(e) => setProfile({ ...profile, [key]: e.target.value })} />
      ) : (
        <input className={input} value={profile[key] || ""} onChange={(e) => setProfile({ ...profile, [key]: e.target.value })} />
      )}
    </label>
  );
  return (
    <div className={card}>
      <h3 className={heading}>Profile (always known to Ashen)</h3>
      <div className="grid gap-3 sm:grid-cols-2">
        {field("name", "Name")}
        {field("course", "Course")}
        {field("location", "Location")}
        {field("goals", "Goals")}
        {field("preferences", "Preferences (comma separated)")}
        {field("about", "Anything else", true)}
      </div>
      <button onClick={save} className="mt-3 rounded-[10px] bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground hover:bg-primary-glow">
        Save profile
      </button>
    </div>
  );
}

function FactRow({ fact, onChanged }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(fact.text);
  const save = async () => {
    try {
      await MemoryAPI.edit(fact.id, text);
      setEditing(false);
      onChanged();
    } catch (e) {
      toast.error(e.response?.data?.error || "Could not update");
    }
  };
  const remove = async () => {
    try {
      await MemoryAPI.remove(fact.id);
      onChanged();
      toast.success("Forgotten");
    } catch {
      toast.error("Could not delete");
    }
  };
  return (
    <div className="flex items-start gap-2 border-t border-border py-2.5 first:border-t-0">
      <div className="min-w-0 flex-1">
        {editing ? (
          <textarea rows={2} className={input} value={text} onChange={(e) => setText(e.target.value)} />
        ) : (
          <p className="m-0 text-[13.5px] leading-snug text-foreground">{fact.text}</p>
        )}
        <div className="mt-1 flex flex-wrap gap-x-3 text-[11px] text-muted-foreground">
          {fact.topic ? <span>{fact.topic}</span> : null}
          {fact.entities?.length ? <span>{fact.entities.join(", ")}</span> : null}
          {fact.updated_at ? <span>{new Date(fact.updated_at).toLocaleDateString("en-GB")}</span> : null}
          {fact.history?.length ? <span title={fact.history.map((h) => h.text).join("\n")}>previously: {fact.history[fact.history.length - 1].text}</span> : null}
        </div>
      </div>
      {editing ? (
        <>
          <button onClick={save} title="Save" className="grid h-8 w-8 place-items-center rounded-lg text-primary hover:bg-muted"><Check sx={{ fontSize: 17 }} /></button>
          <button onClick={() => { setEditing(false); setText(fact.text); }} title="Cancel" className="grid h-8 w-8 place-items-center rounded-lg text-muted-foreground hover:bg-muted"><Close sx={{ fontSize: 17 }} /></button>
        </>
      ) : (
        <>
          <button onClick={() => setEditing(true)} title="Edit" className="grid h-8 w-8 place-items-center rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground"><EditOutlined sx={{ fontSize: 16 }} /></button>
          <button onClick={remove} title="Forget" className="grid h-8 w-8 place-items-center rounded-lg text-muted-foreground hover:bg-muted hover:text-destructive"><DeleteOutline sx={{ fontSize: 17 }} /></button>
        </>
      )}
    </div>
  );
}

function SamplesCard() {
  const [samples, setSamples] = useState([]);
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const load = () => MemoryAPI.listSamples().then((d) => setSamples(d.samples || [])).catch(() => {});
  useEffect(() => { load(); }, []);
  const add = async () => {
    if (!text.trim()) return;
    try {
      await MemoryAPI.addSample(title || "Untitled", text);
      setTitle("");
      setText("");
      load();
    } catch {
      toast.error("Could not save sample");
    }
  };
  return (
    <div className={card}>
      <h3 className={heading}>Writing samples (used to match your voice)</h3>
      {samples.map((s) => (
        <div key={s.id} className="flex items-center gap-2 border-t border-border py-2 first:border-t-0 text-[13px]">
          <span className="flex-1 truncate">{s.title} <span className="text-muted-foreground">· {s.text?.split(/\s+/).length} words</span></span>
          <button onClick={() => MemoryAPI.removeSample(s.id).then(load)} title="Delete" className="grid h-8 w-8 place-items-center rounded-lg text-muted-foreground hover:text-destructive"><DeleteOutline sx={{ fontSize: 16 }} /></button>
        </div>
      ))}
      <div className="mt-3 flex flex-col gap-2">
        <input className={input} placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
        <textarea rows={4} className={input} placeholder="Paste 300 to 1,000 words of your own writing" value={text} onChange={(e) => setText(e.target.value)} />
        <button onClick={add} disabled={!text.trim()} className="self-start rounded-[10px] border border-border bg-secondary px-4 py-2 text-xs font-semibold disabled:opacity-50">Add sample</button>
      </div>
    </div>
  );
}

export default function Memories() {
  const [facts, setFacts] = useState([]);
  const [aliases, setAliases] = useState([]);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);

  const load = () =>
    MemoryAPI.list()
      .then((d) => {
        setFacts(d.facts || []);
        setAliases(d.aliases || []);
      })
      .catch(() => toast.error("Could not load memories"))
      .finally(() => setLoading(false));
  useEffect(() => { load(); }, []);

  const shown = useMemo(() => {
    const q = filter.trim().toLowerCase();
    return q ? facts.filter((f) => `${f.text} ${f.topic} ${(f.entities || []).join(" ")}`.toLowerCase().includes(q)) : facts;
  }, [facts, filter]);

  return (
    <div className="mx-auto flex max-w-[860px] flex-col gap-4">
      <h1 className="m-0 text-2xl font-semibold">Memory</h1>
      <p className="m-0 text-sm text-muted-foreground">
        Facts Ashen has learned from your chats. Edit or forget anything here, or type "forget …" in chat.
        Passwords, keys, card and ID numbers are never stored.
      </p>
      <ProfileCard />
      <div className={card}>
        <div className="mb-3 flex items-center gap-3">
          <h3 className={`${heading} mb-0 flex-1`}>Saved facts · {facts.length}</h3>
          <input className={`${input} max-w-[240px]`} placeholder="Filter…" value={filter} onChange={(e) => setFilter(e.target.value)} />
        </div>
        {loading ? <p className="m-0 text-sm text-muted-foreground">Loading…</p> : null}
        {!loading && shown.length === 0 ? <p className="m-0 text-sm text-muted-foreground">No facts yet.</p> : null}
        {shown.map((f) => <FactRow key={f.id} fact={f} onChanged={load} />)}
      </div>
      {aliases.length ? (
        <div className={card}>
          <h3 className={heading}>Aliases</h3>
          <div className="flex flex-wrap gap-2">
            {aliases.map((a) => (
              <span key={`${a.name}-${a.refers_to}`} className="rounded-lg border border-border bg-secondary px-2.5 py-1 text-xs">
                {a.name} → {a.refers_to}
              </span>
            ))}
          </div>
        </div>
      ) : null}
      <SamplesCard />
    </div>
  );
}

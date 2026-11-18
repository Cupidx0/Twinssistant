import React, { useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { AutorenewOutlined, CheckCircleOutline, HighlightOff, ContentCopy, Download, UploadFile } from "@mui/icons-material";
import { StudioAPI, UploadAPI } from "../../Utils/Assistant";
import { Markdown } from "../../components/ChatMessage";

const input =
  "w-full rounded-[10px] border border-border bg-secondary px-3 py-2 text-[13px] text-foreground outline-none placeholder:text-muted-foreground focus:border-primary/40";
const card = "glass rounded-2xl p-4";
const heading = "m-0 mb-3 text-[11px] font-bold uppercase tracking-[0.14em] text-muted-foreground";

function useJob() {
  const [job, setJob] = useState(null);
  const timer = useRef(null);
  const stop = () => clearInterval(timer.current);
  useEffect(() => stop, []);
  const start = async (promise) => {
    try {
      const { job_id } = await promise;
      setJob({ status: "running", progress: "Starting" });
      stop();
      timer.current = setInterval(async () => {
        try {
          const j = await StudioAPI.job(job_id);
          setJob(j);
          if (j.status !== "running") stop();
        } catch {
          /* keep polling */
        }
      }, 3000);
    } catch (e) {
      toast.error(e.response?.data?.error || "Could not start the job");
    }
  };
  return [job, start];
}

function Progress({ job }) {
  if (!job) return null;
  if (job.status === "error") return <p className="m-0 text-sm text-destructive">Failed: {job.error}</p>;
  if (job.status !== "running") return null;
  return (
    <p className="m-0 flex items-center gap-2 text-sm text-muted-foreground">
      <AutorenewOutlined className="animate-spin text-primary" sx={{ fontSize: 16 }} /> {job.progress}… this can take a few minutes.
    </p>
  );
}

function Check({ ok, children }) {
  return (
    <li className="flex items-start gap-2 text-[13px]">
      {ok ? <CheckCircleOutline className="mt-px text-success" sx={{ fontSize: 16 }} /> : <HighlightOff className="mt-px text-destructive" sx={{ fontSize: 16 }} />}
      <span>{children}</span>
    </li>
  );
}

function WriteTab() {
  const [brief, setBrief] = useState("");
  const [criteria, setCriteria] = useState("");
  const [words, setWords] = useState(1500);
  const [job, start] = useJob();
  const r = job?.status === "done" ? job.result : null;

  const download = () => {
    const blob = new Blob([r.final], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    Object.assign(document.createElement("a"), { href: url, download: `${(r.title || "draft").replace(/[^\w-]+/g, "_")}.md` }).click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-col gap-4">
      <div className={card}>
        <div className="flex flex-col gap-3">
          <textarea rows={5} className={input} placeholder="Assignment brief or what you need written" value={brief} onChange={(e) => setBrief(e.target.value)} />
          <textarea rows={4} className={input} placeholder="Assessment criteria (e.g. P1 ..., M1 ..., D1 ...)" value={criteria} onChange={(e) => setCriteria(e.target.value)} />
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            Target words
            <input type="number" min={100} max={10000} step={100} className={`${input} w-28`} value={words} onChange={(e) => setWords(e.target.value)} />
          </label>
          <button
            disabled={!brief.trim() || job?.status === "running"}
            onClick={() => start(StudioAPI.write({ brief, criteria, word_count: Number(words) }))}
            className="self-start rounded-[10px] bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground hover:bg-primary-glow disabled:opacity-50"
          >
            Plan, draft, critique and revise
          </button>
          <Progress job={job} />
        </div>
      </div>
      {r ? (
        <>
          <div className={card}>
            <h3 className={heading}>Checks</h3>
            <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
              <Check ok={r.checks.dashes.em_dashes === 0}>No em dashes ({r.checks.dashes.em_dashes} found)</Check>
              <Check ok={r.checks.word_count.within_tolerance}>
                {r.checks.word_count.words} words (target {r.checks.word_count.target}, ±10%)
              </Check>
              <Check ok={!r.checks.citations.missing_from_references.length}>
                {r.checks.citations.citations} in-text citations, {r.checks.citations.references} references
                {r.checks.citations.missing_from_references.length ? `; missing: ${r.checks.citations.missing_from_references.join(", ")}` : ""}
              </Check>
              <Check ok={!Object.keys(r.checks.us_spellings).length}>
                UK spelling{Object.keys(r.checks.us_spellings).length ? `: check ${Object.keys(r.checks.us_spellings).join(", ")}` : ""}
              </Check>
            </ul>
          </div>
          <div className={card}>
            <div className="mb-3 flex items-center gap-2">
              <h3 className={`${heading} mb-0 flex-1`}>Final draft</h3>
              <button onClick={() => navigator.clipboard.writeText(r.final).then(() => toast.success("Copied"))} className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-muted-foreground hover:bg-muted"><ContentCopy sx={{ fontSize: 13 }} /> Copy</button>
              <button onClick={download} className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-muted-foreground hover:bg-muted"><Download sx={{ fontSize: 14 }} /> .md</button>
            </div>
            <div className="markdown-body text-[14.5px] leading-[1.7] [&_p]:mb-3"><Markdown text={r.final} /></div>
          </div>
          <details className={card}>
            <summary className="cursor-pointer text-sm font-semibold">Examiner critique</summary>
            <div className="mt-3 text-[13.5px] leading-relaxed"><Markdown text={r.critique} /></div>
          </details>
          {r.sources?.length ? (
            <div className={card}>
              <h3 className={heading}>Sources used</h3>
              <ol className="m-0 pl-5 text-[13px]">
                {r.sources.map((s) => (
                  <li key={s.url}><a href={s.url} target="_blank" rel="noreferrer" className="text-primary-glow underline">{s.title}</a></li>
                ))}
              </ol>
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

function GradeTab() {
  const [brief, setBrief] = useState("");
  const [criteria, setCriteria] = useState("");
  const [submission, setSubmission] = useState("");
  const [upload, setUpload] = useState(null);
  const [job, start] = useJob();
  const r = job?.status === "done" ? job.result : null;

  const onFile = async (file) => {
    if (!file) return;
    try {
      const res = await UploadAPI.upload(file);
      setUpload(res);
    } catch (e) {
      toast.error(e.response?.data?.error || "Upload failed");
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div className={card}>
        <div className="flex flex-col gap-3">
          <textarea rows={4} className={input} placeholder="Full assignment brief" value={brief} onChange={(e) => setBrief(e.target.value)} />
          <textarea rows={5} className={input} placeholder="Criteria per learning outcome, e.g. P1 ..., M1 ..., D1 ..." value={criteria} onChange={(e) => setCriteria(e.target.value)} />
          <textarea rows={6} className={input} placeholder="Paste the submission, or upload a PDF / docx below" value={submission} onChange={(e) => setSubmission(e.target.value)} />
          <label className="flex cursor-pointer items-center gap-2 self-start rounded-[10px] border border-border bg-secondary px-3 py-2 text-xs font-semibold">
            <UploadFile sx={{ fontSize: 15 }} /> {upload ? upload.name : "Upload submission"}
            <input type="file" hidden accept=".pdf,.docx,.txt,.md" onChange={(e) => onFile(e.target.files?.[0])} />
          </label>
          <button
            disabled={!brief.trim() || !criteria.trim() || (!submission.trim() && !upload) || job?.status === "running"}
            onClick={() => start(StudioAPI.grade({ brief, criteria, submission, upload_id: upload?.upload_id }))}
            className="self-start rounded-[10px] bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground hover:bg-primary-glow disabled:opacity-50"
          >
            Grade strictly
          </button>
          <Progress job={job} />
        </div>
      </div>
      {r ? (
        <>
          <div className={card}>
            <div className="flex flex-wrap items-baseline gap-3">
              <span className="text-[28px] font-semibold tracking-tight">{r.overall_grade}</span>
              <span className="text-xs text-muted-foreground">
                runs: {r.consistency?.runs?.join(", ")} · {r.consistency?.agreed ? "consistent" : "majority vote"} · confidence {Math.round((r.confidence || 0) * 100)}%
              </span>
            </div>
            {r.rule_notes?.length ? (
              <ul className="mb-0 mt-2 pl-5 text-xs text-warning">{r.rule_notes.map((n) => <li key={n}>{n}</li>)}</ul>
            ) : null}
          </div>
          <div className={card}>
            <h3 className={heading}>Criteria</h3>
            <div className="flex flex-col">
              {r.criteria.map((c) => (
                <div key={c.id} className="border-t border-border py-3 first:border-t-0">
                  <div className="flex items-center gap-2 text-sm font-semibold">
                    {c.met ? <CheckCircleOutline className="text-success" sx={{ fontSize: 17 }} /> : <HighlightOff className="text-destructive" sx={{ fontSize: 17 }} />}
                    {c.id} <span className="font-normal text-muted-foreground">{c.met ? "met" : "not met"}</span>
                  </div>
                  <p className="mb-1 mt-1 text-[13px] text-foreground/85">{c.description}</p>
                  {c.evidence?.map((q) => (
                    <blockquote key={q} className="my-1 border-l-2 border-primary/50 pl-3 text-[12.5px] italic text-muted-foreground">"{q}"</blockquote>
                  ))}
                  {c.missing ? <p className="m-0 mt-1 text-[12.5px]"><b>Missing:</b> {c.missing}</p> : null}
                  {c.fix ? <p className="m-0 mt-0.5 text-[12.5px]"><b>Fix:</b> {c.fix}</p> : null}
                </div>
              ))}
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            {[["Priority fixes", r.priority_fixes], ["Strengths", r.strengths], ["Style issues", r.style_issues]].map(([title, items]) => (
              <div key={title} className={card}>
                <h3 className={heading}>{title}</h3>
                <ul className="m-0 pl-5 text-[13px]">{(items || []).map((x) => <li key={x}>{x}</li>)}</ul>
              </div>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}

export default function Studio() {
  const [tab, setTab] = useState("write");
  return (
    <div className="mx-auto flex max-w-[860px] flex-col gap-4">
      <h1 className="m-0 text-2xl font-semibold">Writing &amp; grading</h1>
      <p className="m-0 text-sm text-muted-foreground">
        Use these for planning, feedback and checking your own work. Follow your college's AI policy for anything you submit.
      </p>
      <div className="flex gap-2">
        {[["write", "Write"], ["grade", "Grade"]].map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`rounded-[10px] px-4 py-1.5 text-xs font-semibold ${tab === key ? "bg-primary text-primary-foreground" : "border border-border text-muted-foreground"}`}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === "write" ? <WriteTab /> : <GradeTab />}
    </div>
  );
}

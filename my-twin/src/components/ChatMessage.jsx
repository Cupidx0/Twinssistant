import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github-dark.css";
import toast from "react-hot-toast";
import {
  ContentCopy,
  ExpandMore,
  ChevronRight,
  Psychology,
  CheckCircleOutline,
  AutorenewOutlined,
  WebAsset,
} from "@mui/icons-material";

const ARTIFACT_RE = /<artifact\s+type="([\w-]+)"\s+title="([^"]*)"\s*>([\s\S]*?)<\/artifact>/g;
const OPEN_ARTIFACT_RE = /<artifact\s+type="([\w-]+)"\s+title="([^"]*)"\s*>[\s\S]*$/;

// Split a reply into markdown parts and artifacts. An unfinished artifact
// (still streaming) is hidden behind a placeholder.
function splitArtifacts(text = "") {
  const parts = [];
  let last = 0;
  for (const m of text.matchAll(ARTIFACT_RE)) {
    if (m.index > last) parts.push({ kind: "md", text: text.slice(last, m.index) });
    parts.push({ kind: "artifact", type: m[1], title: m[2] || "Untitled", html: m[3].trim() });
    last = m.index + m[0].length;
  }
  const rest = text.slice(last);
  const open = rest.match(OPEN_ARTIFACT_RE);
  if (open) {
    if (open.index > 0) parts.push({ kind: "md", text: rest.slice(0, open.index) });
    parts.push({ kind: "building", title: open[2] || "artifact" });
  } else if (rest) {
    parts.push({ kind: "md", text: rest });
  }
  return parts;
}

const hastText = (node) => {
  if (!node) return "";
  if (node.type === "text") return node.value;
  return (node.children || []).map(hastText).join("");
};

const copy = (text) =>
  navigator.clipboard.writeText(text).then(
    () => toast.success("Copied"),
    () => toast.error("Copy failed"),
  );

function CodeBlock({ node, children }) {
  const code = hastText(node).replace(/\n$/, "");
  const codeEl = node?.children?.[0];
  const lang = (codeEl?.properties?.className || [])
    .map(String)
    .find((c) => c.startsWith("language-"))
    ?.replace("language-", "");
  return (
    <div className="code-wrap">
      <div className="code-wrap__bar">
        <span>{lang || "code"}</span>
        <button type="button" onClick={() => copy(code)}>
          <ContentCopy sx={{ fontSize: 12 }} /> Copy
        </button>
      </div>
      <pre>{children}</pre>
    </div>
  );
}

export function Markdown({ text }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[[rehypeHighlight, { detect: true }]]}
      components={{
        pre: CodeBlock,
        a: ({ href, children }) => (
          <a href={href} target="_blank" rel="noreferrer">
            {children}
          </a>
        ),
      }}
    >
      {text}
    </ReactMarkdown>
  );
}

function ThinkingPanel({ text, streaming }) {
  const [open, setOpen] = useState(false);
  if (!text) return null;
  return (
    <div className="mb-3 rounded-xl border border-border bg-card/60">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs font-semibold text-muted-foreground hover:text-foreground"
      >
        {open ? <ExpandMore sx={{ fontSize: 16 }} /> : <ChevronRight sx={{ fontSize: 16 }} />}
        <Psychology sx={{ fontSize: 15 }} />
        {streaming ? "Thinking…" : "Thought process"}
      </button>
      {open ? (
        <div className="whitespace-pre-wrap border-t border-border px-4 py-3 text-[13px] leading-relaxed text-muted-foreground">
          {text}
        </div>
      ) : null}
    </div>
  );
}

function ToolChips({ tools }) {
  if (!tools?.length) return null;
  return (
    <div className="mb-3 flex flex-wrap gap-2">
      {tools.map((t, i) => (
        <span
          key={`${t.name}-${i}`}
          className="flex items-center gap-1.5 rounded-full border border-border bg-secondary px-2.5 py-1 text-[11.5px] font-semibold text-muted-foreground"
          title={t.input ? JSON.stringify(t.input) : undefined}
        >
          {t.done ? (
            <CheckCircleOutline className="text-primary-glow" sx={{ fontSize: 13 }} />
          ) : (
            <AutorenewOutlined className="animate-spin text-primary" sx={{ fontSize: 13 }} />
          )}
          {t.label}
          {t.input?.query ? `: ${String(t.input.query).slice(0, 40)}` : ""}
          {t.done ? "" : "…"}
        </span>
      ))}
    </div>
  );
}

export default function ChatMessage({ message, onOpenArtifact }) {
  const parts = splitArtifacts(message.text || "");
  const savedArtifacts = message.artifacts || [];
  let artifactIndex = 0;
  return (
    <>
      <ThinkingPanel text={message.thinking} streaming={message.streaming && !message.text} />
      <ToolChips tools={message.tools} />
      <div className="markdown-body max-w-[65ch] text-[15px] leading-[1.7] text-foreground/90 [&_a]:text-primary-glow [&_a]:underline [&_:not(pre)>code]:rounded [&_:not(pre)>code]:bg-muted [&_:not(pre)>code]:px-1 [&_code]:font-mono [&_code]:text-[13px] [&_p]:mb-3 [&_p]:mt-0 [&_ul]:my-2 [&_ul]:pl-5 [&_ol]:my-2 [&_ol]:pl-5 [&_table]:my-3 [&_table]:border-collapse [&_td]:border [&_td]:border-border [&_td]:px-2 [&_td]:py-1 [&_th]:border [&_th]:border-border [&_th]:px-2 [&_th]:py-1">
        {parts.map((p, i) => {
          if (p.kind === "md") return <Markdown key={i} text={p.text} />;
          if (p.kind === "building")
            return (
              <div key={i} className="my-3 flex items-center gap-2 rounded-xl border border-border bg-card px-4 py-3 text-sm text-muted-foreground">
                <AutorenewOutlined className="animate-spin text-primary" sx={{ fontSize: 16 }} />
                Building {p.title}…
              </div>
            );
          const saved = savedArtifacts[artifactIndex++];
          return (
            <button
              key={i}
              type="button"
              onClick={() => onOpenArtifact?.({ ...p, id: saved?.id })}
              className="my-3 flex w-full items-center gap-3 rounded-xl border border-primary/30 bg-primary/10 px-4 py-3 text-left transition hover:border-primary/60"
            >
              <WebAsset className="text-primary" sx={{ fontSize: 22 }} />
              <span className="flex flex-col">
                <span className="text-sm font-semibold text-foreground">{p.title}</span>
                <span className="text-xs text-muted-foreground">
                  Open preview{saved?.version > 1 ? ` · version ${saved.version}` : ""}
                </span>
              </span>
            </button>
          );
        })}
        {message.streaming && message.text ? <span className="stream-caret" /> : null}
      </div>
    </>
  );
}

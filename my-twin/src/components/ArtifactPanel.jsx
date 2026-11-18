import React, { useEffect, useState } from "react";
import { Close, Download, ContentCopy, Code, Visibility } from "@mui/icons-material";
import toast from "react-hot-toast";
import { ArtifactAPI } from "../Utils/Assistant";

// Artifacts run in a sandboxed iframe with allow-scripts only. Never add
// allow-same-origin: artifact code must not reach the app's cookies or tokens.
export default function ArtifactPanel({ artifact, onClose }) {
  const [versions, setVersions] = useState([]);
  const [index, setIndex] = useState(-1);
  const [view, setView] = useState("preview");

  useEffect(() => {
    setVersions([]);
    setIndex(-1);
    setView("preview");
    if (!artifact?.id) return;
    ArtifactAPI.get(artifact.id)
      .then((data) => {
        const list = data.versions || [];
        setVersions(list);
        setIndex(list.length - 1);
      })
      .catch(() => {});
  }, [artifact?.id, artifact?.html]);

  if (!artifact) return null;
  const html = index >= 0 && versions[index] ? versions[index].html : artifact.html;

  const download = () => {
    const blob = new Blob([html], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${(artifact.title || "artifact").replace(/[^\w-]+/g, "_")}.html`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[760px] flex-col border-l border-border bg-background shadow-2xl">
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <h2 className="m-0 min-w-0 flex-1 truncate text-sm font-semibold">{artifact.title}</h2>
        {versions.length > 1 ? (
          <select
            value={index}
            onChange={(e) => setIndex(Number(e.target.value))}
            className="rounded-lg border border-border bg-secondary px-2 py-1 text-xs"
            aria-label="Version"
          >
            {versions.map((v, i) => (
              <option key={i} value={i}>
                Version {i + 1}
              </option>
            ))}
          </select>
        ) : null}
        <button
          type="button"
          onClick={() => setView(view === "preview" ? "code" : "preview")}
          title={view === "preview" ? "Show code" : "Show preview"}
          className="grid h-8 w-8 place-items-center rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          {view === "preview" ? <Code sx={{ fontSize: 17 }} /> : <Visibility sx={{ fontSize: 17 }} />}
        </button>
        <button
          type="button"
          onClick={() => navigator.clipboard.writeText(html).then(() => toast.success("Copied"))}
          title="Copy HTML"
          className="grid h-8 w-8 place-items-center rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <ContentCopy sx={{ fontSize: 16 }} />
        </button>
        <button
          type="button"
          onClick={download}
          title="Download"
          className="grid h-8 w-8 place-items-center rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <Download sx={{ fontSize: 17 }} />
        </button>
        <button
          type="button"
          onClick={onClose}
          title="Close"
          className="grid h-8 w-8 place-items-center rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <Close sx={{ fontSize: 18 }} />
        </button>
      </div>
      {view === "preview" ? (
        <iframe
          title={artifact.title || "artifact"}
          sandbox="allow-scripts"
          srcDoc={html}
          className="w-full flex-1 border-0 bg-white"
        />
      ) : (
        <pre className="m-0 flex-1 overflow-auto bg-card p-4 font-mono text-[12.5px] text-foreground/90">{html}</pre>
      )}
    </div>
  );
}

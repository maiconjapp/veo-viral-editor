import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft,
  Download,
  Loader2,
  Film,
  Mic2,
  Clock,
  AlertTriangle,
} from "lucide-react";
import { getProject, downloadUrl, streamUrl } from "../lib/api";
import { Button } from "../components/ui/button";

const STATUS_LABEL = {
  draft: "Draft",
  queued: "Queued",
  analyzing: "Analysing with Gemini",
  planning: "Planning viral structure",
  rendering: "Rendering timeline",
  done: "Ready",
  failed: "Failed",
};

export default function Project() {
  const { id } = useParams();
  const [p, setP] = useState(null);
  const [err, setErr] = useState(null);
  const logRef = useRef(null);

  useEffect(() => {
    let cancel = false;
    const tick = async () => {
      try {
        const next = await getProject(id);
        if (!cancel) setP(next);
      } catch (e) {
        if (!cancel) setErr(e?.response?.data?.detail || "Failed to load");
      }
    };
    tick();
    const t = setInterval(tick, 2500);
    return () => {
      cancel = true;
      clearInterval(t);
    };
  }, [id]);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [p?.logs?.length]);

  if (err) {
    return <Centered msg={err} />;
  }
  if (!p) {
    return <Centered msg="Loading…" spin />;
  }

  const working = ["queued", "analyzing", "planning", "rendering"].includes(p.status);
  const done = p.status === "done";

  return (
    <div className="max-w-6xl mx-auto px-6 py-10 md:py-14">
      <Link
        to="/"
        data-testid="link-back"
        className="inline-flex items-center gap-1.5 text-sm text-[#c9bfae] hover:text-[#e6bb77]"
      >
        <ArrowLeft className="w-4 h-4" />
        All projects
      </Link>

      <div className="mt-6 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1
            data-testid="project-name"
            className="text-3xl md:text-5xl leading-tight"
            style={{ fontStyle: "italic", fontWeight: 600 }}
          >
            {p.name}
          </h1>
          <div
            className="mt-2 flex items-center gap-3 text-xs text-[#8a7f6d]"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            <span>{new Date(p.created_at).toLocaleString()}</span>
            <span>·</span>
            <span>{p.language}</span>
            <span>·</span>
            <span>{p.voice}</span>
          </div>
        </div>
        <StatusBadge status={p.status} />
      </div>

      {working && (
        <div className="mt-8 p-5 rounded-2xl border border-[#c29d5f]/20 bg-[#1a140c]/70">
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm text-[#f4ede3]">{STATUS_LABEL[p.status]}</div>
            <div
              className="text-xs text-[#8a7f6d]"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              {p.progress}%
            </div>
          </div>
          <div className="h-2 rounded-full bg-[#2a241b] overflow-hidden">
            <div
              data-testid="progress-bar"
              className="h-full bg-[#e6bb77] transition-all"
              style={{ width: `${p.progress || 0}%` }}
            />
          </div>
          <div
            ref={logRef}
            data-testid="logs"
            className="mt-4 max-h-48 overflow-y-auto text-xs text-[#8a7f6d] space-y-1"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            {(p.logs || []).map((l, i) => (
              <div key={i}>{l}</div>
            ))}
          </div>
        </div>
      )}

      {p.status === "failed" && (
        <div className="mt-8 p-5 rounded-2xl border border-[#e68a7a]/40 bg-[#3a1f1f]/40 text-[#ffb8a8]">
          <div className="flex items-center gap-2 font-medium mb-1">
            <AlertTriangle className="w-4 h-4" />
            Processing failed
          </div>
          <div
            className="text-xs text-[#ffc9bc]"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            {p.error || "Unknown error"}
          </div>
        </div>
      )}

      {done && (
        <div className="mt-8 grid md:grid-cols-[auto_1fr] gap-8 items-start">
          <div className="relative w-full md:w-[360px] aspect-[9/16] rounded-2xl overflow-hidden bg-black shadow-[0_30px_80px_-20px_rgba(194,157,95,0.35)] ring-1 ring-[#c29d5f]/30">
            <video
              data-testid="final-video"
              src={streamUrl(p.id)}
              controls
              playsInline
              preload="metadata"
              className="w-full h-full object-cover"
            />
          </div>
          <div className="space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              <Stat label="Duration" value={`${p.output.duration_s}s`} icon={<Clock className="w-3.5 h-3.5" />} />
              <Stat label="Size" value={`${p.output.size_mb} MB`} icon={<Film className="w-3.5 h-3.5" />} />
              <Stat label="Voice" value={p.voice?.split("-").slice(-1)[0].replace("Neural", "")} icon={<Mic2 className="w-3.5 h-3.5" />} />
            </div>
            <a
              data-testid="button-download"
              href={downloadUrl(p.id)}
              download
              className="inline-flex items-center gap-2 px-6 h-11 rounded-full bg-[#e6bb77] text-[#1a140c] font-medium hover:bg-[#f3cd8a] transition-all shadow-[0_8px_24px_-8px_rgba(230,187,119,0.6)]"
              style={{ fontFamily: "'Inter', sans-serif" }}
            >
              <Download className="w-4 h-4" />
              Download final MP4
            </a>
          </div>
        </div>
      )}

      {p.plan?.timeline && (
        <section className="mt-12">
          <h2
            className="text-base text-[#e6bb77] mb-3 tracking-wide"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            &#47;&#47; reorder timeline
          </h2>
          {p.plan.structure_rationale && (
            <p className="text-sm text-[#c9bfae] mb-4 max-w-2xl">
              {p.plan.structure_rationale}
            </p>
          )}
          <ol className="space-y-2" data-testid="timeline">
            {p.plan.timeline.map((seg, i) => (
              <li
                key={i}
                className="flex items-start gap-4 p-3 rounded-lg bg-[#1a140c]/60 border border-[#c29d5f]/15"
              >
                <span
                  className="text-[10px] uppercase tracking-widest text-[#e6bb77] pt-1 w-24 shrink-0"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  {String(i + 1).padStart(2, "0")} {seg.label}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-[#f4ede3]">{seg.desc}</div>
                  <div
                    className="text-xs text-[#8a7f6d] mt-0.5"
                    style={{ fontFamily: "'JetBrains Mono', monospace" }}
                  >
                    clip {seg.source_idx} · {Number(seg.start).toFixed(1)}s → {Number(seg.end).toFixed(1)}s · {(seg.end - seg.start).toFixed(1)}s
                  </div>
                </div>
              </li>
            ))}
          </ol>
        </section>
      )}

      {p.plan?.vo_script && (
        <section className="mt-10">
          <h2
            className="text-base text-[#e6bb77] mb-3 tracking-wide"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            &#47;&#47; voice-over script
          </h2>
          <div className="p-5 rounded-2xl border border-[#c29d5f]/20 bg-[#1a140c]/60 text-[#c9bfae] leading-relaxed whitespace-pre-wrap">
            {p.plan.vo_script}
          </div>
        </section>
      )}
    </div>
  );
}

function Centered({ msg, spin }) {
  return (
    <div className="min-h-[60vh] flex items-center justify-center text-[#c9bfae] gap-2">
      {spin && <Loader2 className="w-4 h-4 animate-spin" />}
      <span>{msg}</span>
    </div>
  );
}

function StatusBadge({ status }) {
  const color =
    {
      draft: "bg-[#444137] text-[#c9bfae]",
      queued: "bg-[#3a3a1f] text-[#e6bb77]",
      analyzing: "bg-[#3a2a1f] text-[#ffb37a]",
      planning: "bg-[#3a2a1f] text-[#ffb37a]",
      rendering: "bg-[#2a3a1f] text-[#c9e68a]",
      done: "bg-[#1f3a2a] text-[#7cbf5c]",
      failed: "bg-[#3a1f1f] text-[#e68a7a]",
    }[status] || "bg-[#444137] text-[#c9bfae]";
  return (
    <span
      data-testid="project-status"
      className={`text-[10px] uppercase tracking-widest px-3 py-1.5 rounded-full ${color}`}
      style={{ fontFamily: "'JetBrains Mono', monospace" }}
    >
      {STATUS_LABEL[status] || status}
    </span>
  );
}

function Stat({ label, value, icon }) {
  return (
    <div className="p-4 rounded-xl bg-[#1a140c]/60 border border-[#c29d5f]/15">
      <div
        className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.2em] text-[#8a7f6d]"
        style={{ fontFamily: "'JetBrains Mono', monospace" }}
      >
        {icon}
        {label}
      </div>
      <div className="text-lg mt-1 text-[#f4ede3]">{value}</div>
    </div>
  );
}

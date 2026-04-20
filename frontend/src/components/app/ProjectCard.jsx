import { Link } from "react-router-dom";
import { Film, Clock, Mic2 } from "lucide-react";

const STATUS_COLORS = {
  draft: "bg-[#444137] text-[#c9bfae]",
  queued: "bg-[#3a3a1f] text-[#e6bb77]",
  analyzing: "bg-[#3a2a1f] text-[#ffb37a]",
  planning: "bg-[#3a2a1f] text-[#ffb37a]",
  rendering: "bg-[#2a3a1f] text-[#c9e68a]",
  done: "bg-[#1f3a2a] text-[#7cbf5c]",
  failed: "bg-[#3a1f1f] text-[#e68a7a]",
};

export default function ProjectCard({ p }) {
  const color = STATUS_COLORS[p.status] || STATUS_COLORS.draft;
  return (
    <Link
      to={`/project/${p.id}`}
      data-testid={`project-card-${p.id}`}
      className="block p-5 rounded-2xl bg-[#1a140c]/70 border border-[#c29d5f]/15 hover:border-[#c29d5f]/60 hover:bg-[#1a140c] transition-all group"
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0">
          <div className="text-lg text-[#f4ede3] truncate" style={{ fontStyle: "italic" }}>
            {p.name}
          </div>
          <div
            className="text-xs text-[#8a7f6d] mt-0.5"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            {new Date(p.created_at).toLocaleString()}
          </div>
        </div>
        <span
          data-testid={`project-status-${p.id}`}
          className={`text-[10px] uppercase tracking-widest px-2 py-1 rounded-full ${color}`}
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          {p.status}
        </span>
      </div>

      <div className="flex items-center gap-4 text-xs text-[#c9bfae]">
        <span className="inline-flex items-center gap-1.5">
          <Film className="w-3.5 h-3.5 text-[#e6bb77]" />
          {p.source_files?.length || 0} clip{(p.source_files?.length || 0) === 1 ? "" : "s"}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <Mic2 className="w-3.5 h-3.5 text-[#e6bb77]" />
          {p.voice?.split("-").slice(-1)[0].replace("Neural", "") || "—"}
        </span>
        {p.output?.duration_s && (
          <span className="inline-flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-[#e6bb77]" />
            {p.output.duration_s.toFixed(1)}s
          </span>
        )}
      </div>

      {p.status !== "done" && p.status !== "draft" && (
        <div className="mt-4 h-1 rounded-full bg-[#2a241b] overflow-hidden">
          <div
            className="h-full bg-[#e6bb77] transition-all"
            style={{ width: `${p.progress || 0}%` }}
          />
        </div>
      )}
    </Link>
  );
}

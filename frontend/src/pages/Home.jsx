import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Play, Loader2 } from "lucide-react";
import Dropzone from "../components/app/Dropzone";
import ProjectCard from "../components/app/ProjectCard";
import {
  createProject,
  listProjects,
  listVoices,
  processProject,
  uploadFiles,
} from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Label } from "../components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { toast } from "sonner";

const AUDIENCE_PRESETS = [
  "18-25 Gen Z",
  "25-35 millennials",
  "35-50 adults",
  "50+ older adults",
  "Parents",
  "DIY / home-improvement",
  "Entrepreneurs",
  "Fitness enthusiasts",
];

export default function Home() {
  const nav = useNavigate();
  const [projects, setProjects] = useState([]);
  const [voices, setVoices] = useState([]);
  const [languages, setLanguages] = useState([]);
  const [showForm, setShowForm] = useState(false);

  const refresh = async () => {
    const { projects } = await listProjects();
    setProjects(projects);
  };

  useEffect(() => {
    refresh();
    listVoices().then((d) => {
      setVoices(d.voices);
      setLanguages(d.languages);
    });
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="max-w-6xl mx-auto px-6 py-12 md:py-16">
      <Header onNew={() => setShowForm((s) => !s)} showForm={showForm} />

      {showForm && (
        <NewProjectForm
          voices={voices}
          languages={languages}
          onCancel={() => setShowForm(false)}
          onCreated={async (pid) => {
            setShowForm(false);
            toast.success("Project created — starting editor");
            nav(`/project/${pid}`);
          }}
        />
      )}

      <div className="mt-12">
        <h2
          className="text-base text-[#e6bb77] mb-4 tracking-wide"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          &#47;&#47; your projects
        </h2>
        {projects.length === 0 ? (
          <div
            data-testid="empty-state"
            className="text-center py-16 rounded-2xl border border-dashed border-[#c29d5f]/20"
          >
            <div className="text-[#c9bfae] text-lg" style={{ fontStyle: "italic" }}>
              No projects yet.
            </div>
            <div className="text-[#8a7f6d] text-sm mt-1">
              Click “New project” above to upload your first MP4.
            </div>
          </div>
        ) : (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="projects-grid">
            {projects.map((p) => (
              <ProjectCard key={p.id} p={p} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Header({ onNew, showForm }) {
  return (
    <div className="flex items-end justify-between gap-4 flex-wrap">
      <div>
        <div
          className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-[#c29d5f]/40 bg-[#c29d5f]/10 text-[#e6bb77] text-[10px] uppercase tracking-[0.3em]"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-[#7cbf5c] animate-pulse" />
          AI viral editor
        </div>
        <h1
          className="mt-4 text-4xl sm:text-5xl lg:text-6xl leading-[1.03] tracking-tight"
          style={{ fontWeight: 600, fontStyle: "italic" }}
        >
          Turn raw footage into{" "}
          <span className="text-[#e6bb77]">viral cuts.</span>
        </h1>
        <p className="mt-3 max-w-xl text-[#c9bfae] text-base md:text-lg">
          Upload one or many MP4s. An AI director picks the strongest scenes,
          reorders them into a non-linear viral structure, and writes &amp; voices
          a natural voice-over in the language you choose.
        </p>
      </div>
      <Button
        data-testid="button-new-project"
        onClick={onNew}
        className="rounded-full h-11 px-6 bg-[#e6bb77] text-[#1a140c] hover:bg-[#f3cd8a] font-medium shadow-[0_8px_24px_-8px_rgba(230,187,119,0.6)]"
      >
        <Plus className="w-4 h-4 mr-1.5" />
        {showForm ? "Close" : "New project"}
      </Button>
    </div>
  );
}

function NewProjectForm({ voices, languages, onCancel, onCreated }) {
  const [name, setName] = useState("");
  const [language, setLanguage] = useState("en");
  const [voice, setVoice] = useState("en-US-AndrewNeural");
  const [audience, setAudience] = useState("35-50 adults");
  const [targetDuration, setTargetDuration] = useState(85);
  const [userPrompt, setUserPrompt] = useState("");
  const [files, setFiles] = useState([]);
  const [busy, setBusy] = useState(false);
  const [uploadPct, setUploadPct] = useState(0);

  const filteredVoices = useMemo(
    () => voices.filter((v) => v.lang === language),
    [voices, language]
  );

  useEffect(() => {
    // keep voice consistent with language selection
    if (filteredVoices.length && !filteredVoices.find((v) => v.id === voice)) {
      setVoice(filteredVoices[0].id);
    }
  }, [filteredVoices, voice]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!files.length) return toast.error("Add at least one MP4 file");
    setBusy(true);
    try {
      const proj = await createProject({
        name: name || "Untitled viral cut",
        voice,
        language,
        user_prompt: userPrompt,
        audience,
        target_duration_s: Number(targetDuration),
      });
      await uploadFiles(proj.id, files, setUploadPct);
      await processProject(proj.id);
      onCreated(proj.id);
    } catch (err) {
      console.error(err);
      toast.error(err?.response?.data?.detail || "Failed to start project");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      data-testid="new-project-form"
      className="mt-10 p-6 md:p-8 rounded-3xl bg-[#1a140c]/60 border border-[#c29d5f]/20 space-y-6"
    >
      <div className="grid md:grid-cols-2 gap-5">
        <Field label="Project name">
          <Input
            data-testid="input-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Toilet hack for homeowners"
            className="bg-[#0e0b08] border-[#c29d5f]/25 text-[#f4ede3] h-11"
          />
        </Field>
        <Field label="Target audience">
          <Input
            data-testid="input-audience"
            value={audience}
            onChange={(e) => setAudience(e.target.value)}
            list="audience-presets"
            placeholder="e.g. 35-50 adults"
            className="bg-[#0e0b08] border-[#c29d5f]/25 text-[#f4ede3] h-11"
          />
          <datalist id="audience-presets">
            {AUDIENCE_PRESETS.map((a) => (
              <option key={a} value={a} />
            ))}
          </datalist>
        </Field>
        <Field label="Voice-over language">
          <Select value={language} onValueChange={setLanguage}>
            <SelectTrigger
              data-testid="select-language"
              className="bg-[#0e0b08] border-[#c29d5f]/25 text-[#f4ede3] h-11"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {languages.map((l) => (
                <SelectItem key={l.id} value={l.id}>
                  {l.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <Field label="Voice">
          <Select value={voice} onValueChange={setVoice}>
            <SelectTrigger
              data-testid="select-voice"
              className="bg-[#0e0b08] border-[#c29d5f]/25 text-[#f4ede3] h-11"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {filteredVoices.map((v) => (
                <SelectItem key={v.id} value={v.id}>
                  {v.name} — {v.style}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <Field label="Target duration (seconds)">
          <Input
            data-testid="input-duration"
            type="number"
            min="15"
            max="300"
            value={targetDuration}
            onChange={(e) => setTargetDuration(e.target.value)}
            className="bg-[#0e0b08] border-[#c29d5f]/25 text-[#f4ede3] h-11"
          />
        </Field>
        <Field label="Custom instructions (optional)">
          <Textarea
            data-testid="input-prompt"
            rows={3}
            value={userPrompt}
            onChange={(e) => setUserPrompt(e.target.value)}
            placeholder="e.g. Focus on the cleaning scenes. Keep tone humorous. Start with the flush payoff."
            className="bg-[#0e0b08] border-[#c29d5f]/25 text-[#f4ede3]"
          />
        </Field>
      </div>

      <div>
        <div
          className="text-xs uppercase tracking-[0.2em] text-[#8a7f6d] mb-2"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          source footage
        </div>
        <Dropzone files={files} setFiles={setFiles} disabled={busy} />
      </div>

      <div className="flex items-center justify-end gap-3 pt-2">
        {busy && uploadPct > 0 && uploadPct < 100 && (
          <span
            className="text-sm text-[#8a7f6d]"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            uploading {uploadPct}%
          </span>
        )}
        <Button
          type="button"
          variant="ghost"
          onClick={onCancel}
          className="text-[#c9bfae] hover:bg-[#c29d5f]/10"
        >
          Cancel
        </Button>
        <Button
          data-testid="button-submit"
          type="submit"
          disabled={busy || !files.length}
          className="rounded-full h-11 px-6 bg-[#e6bb77] text-[#1a140c] hover:bg-[#f3cd8a] font-medium"
        >
          {busy ? (
            <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
          ) : (
            <Play className="w-4 h-4 mr-1.5" />
          )}
          {busy ? "Processing..." : "Start editing"}
        </Button>
      </div>
    </form>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <Label
        className="text-xs uppercase tracking-[0.2em] text-[#8a7f6d] mb-2 block"
        style={{ fontFamily: "'JetBrains Mono', monospace" }}
      >
        {label}
      </Label>
      {children}
    </div>
  );
}

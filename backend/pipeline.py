"""
Video pipeline: analyze → plan → render.

Takes uploaded MP4 file(s), runs Gemini multimodal analysis, builds a reordered
viral-style edit plan, generates a new voice-over with Microsoft Neural TTS,
cuts + concatenates + muxes a final MP4 with ffmpeg.

All progress is written back to MongoDB on the `projects` collection.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import shlex
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import edge_tts
from google import genai
from google.genai import types as genai_types

def _key():
    return os.environ.get("GOOGLE_API_KEY", "")

def _client():
    return genai.Client(api_key=_key())

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_FALLBACK_MODELS = [
    m.strip() for m in os.environ.get(
        "GEMINI_FALLBACK_MODELS",
        "gemini-2.5-flash-lite,gemini-2.0-flash,gemini-2.0-flash-lite",
    ).split(",") if m.strip()
]
STORAGE_ROOT = Path(__file__).parent / "storage" / "projects"


def _generate_with_retry(client, contents, system_instruction, max_attempts: int = 5):
    """Call Gemini generate_content with backoff on 503/429/500 and model fallback."""
    models_to_try = [GEMINI_MODEL] + [m for m in GEMINI_FALLBACK_MODELS if m != GEMINI_MODEL]
    last_err = None
    for model in models_to_try:
        for attempt in range(max_attempts):
            try:
                return client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=genai_types.GenerateContentConfig(
                        system_instruction=system_instruction,
                    ),
                )
            except Exception as e:
                msg = str(e)
                last_err = e
                retriable = any(code in msg for code in ("503", "429", "500", "UNAVAILABLE", "RESOURCE_EXHAUSTED"))
                if not retriable:
                    raise
                if attempt < max_attempts - 1:
                    wait = min(2 ** attempt, 20)
                    time.sleep(wait)
                    continue
                break  # try next model
    raise last_err if last_err else RuntimeError("Gemini generate_content failed")


# --------------------------- helpers ---------------------------
def _now():
    return datetime.now(timezone.utc).isoformat()


async def _run(cmd: list[str]) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    out, _ = await proc.communicate()
    return proc.returncode, (out or b"").decode(errors="ignore")


async def ffprobe_duration(path: str) -> float:
    # Use ffmpeg -i to read duration (ffprobe may not be available)
    rc, out = await _run(["ffmpeg", "-v", "error", "-i", path, "-f", "null", "-"])
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", out)
    if m:
        return float(m.group(1)) * 3600 + float(m.group(2)) * 60 + float(m.group(3))
    return 0.0


# --------------------------- progress ---------------------------
async def _update(db, project_id: str, **fields):
    fields["updated_at"] = _now()
    await db.projects.update_one({"id": project_id}, {"$set": fields})


async def _log(db, project_id: str, msg: str):
    await db.projects.update_one(
        {"id": project_id},
        {"$push": {"logs": f"[{_now()}] {msg}"}, "$set": {"updated_at": _now()}},
    )


# --------------------------- analysis ---------------------------
ANALYSIS_SYSTEM = (
    "You are a senior short-form video editor. You analyse raw footage and "
    "identify the strongest scenes for a viral, non-linear, high-retention cut. "
    "You respond with compact, precise timestamps in seconds and concise "
    "scene descriptions suitable for programmatic editing."
)


async def analyze_clip(clip_idx: int, path: str, user_prompt: str) -> dict:
    client = _client()

    # Upload video
    video_file = client.files.upload(
        file=path,
        config=genai_types.UploadFileConfig(
            display_name=f"clip-{clip_idx}",
            mime_type="video/mp4",
        ),
    )

    # Wait for processing
    while video_file.state.name == "PROCESSING":
        time.sleep(2)
        video_file = client.files.get(name=video_file.name)

    if video_file.state.name == "FAILED":
        raise RuntimeError(f"Video processing failed for {path}")

    question = (
        "Analyze this video scene-by-scene for a viral rebuild. "
        "User's extra instructions: " + (user_prompt.strip() or "none") + "\n\n"
        "Return a strict JSON object (no markdown fences) with this shape:\n"
        "{\n"
        '  "theme": "one-line video topic",\n'
        '  "scenes": [\n'
        '    { "start": <seconds float>, "end": <seconds float>,\n'
        '      "label": "HOOK|AHA|SATISFYING|EXPLAIN|ACTION|PAYOFF|FILLER|...",\n'
        '      "desc": "short visual description (English)",\n'
        '      "viral_score": <1-10 integer>,\n'
        '      "cut": <true|false (true = weak, repetitive, or filler)>\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Rules:\n"
        "- Cover the entire video end-to-end with NON-overlapping scenes.\n"
        "- Timestamps must be precise floats in seconds.\n"
        "- Mark slow, repetitive, low-impact, or text-heavy moments as cut=true.\n"
        "- Aim for 6-14 distinct scenes."
    )

    response = _generate_with_retry(
        client,
        contents=[video_file, question],
        system_instruction=ANALYSIS_SYSTEM,
    )

    # Clean up file from Gemini storage
    client.files.delete(name=video_file.name)

    return _parse_json(response.text)


# --------------------------- planning ---------------------------
PLANNING_SYSTEM = (
    "You are a world-class viral short-form video director. You take raw scene "
    "analyses from one or more source clips and assemble a REORDERED, non-linear "
    "edit plan plus a voice-over script in the requested language. You optimise "
    "for hook strength, retention, and emotional payoff for the given audience. "
    "You output strict JSON only."
)


async def build_plan(
    source_analyses: list[dict],
    user_prompt: str,
    language: str,
    audience: str,
    target_duration_s: float,
) -> dict:
    lang_map = {"en": "English", "pt": "Brazilian Portuguese", "es": "Latin American Spanish"}
    lang_name = lang_map.get(language, "English")

    total_available = sum(a.get("source_duration", 0) for a in source_analyses)
    min_dur = float(target_duration_s)
    # Cap minimum target if source is shorter than asked
    if total_available < min_dur + 3:
        min_dur = max(20.0, total_available - 3)

    async def _ask(extra: str = "") -> dict:
        client = _client()

        prompt = (
            f"Assemble a viral video edit plan for a {audience} audience.\n"
            f"REQUIRED final duration: AT LEAST {min_dur:.1f} seconds, ideally {min_dur + 2:.1f}–{min_dur + 6:.1f}s.\n"
            f"Voice-over language: {lang_name}.\n"
            f"User's creative instructions: {user_prompt.strip() or 'none'}\n\n"
            f"Total source footage available across all clips: {total_available:.1f} seconds.\n"
            "SOURCE CLIPS (with scene-level analyses):\n"
            + json.dumps(source_analyses, ensure_ascii=False, indent=2)
            + "\n\n"
            + extra
            + "\n\n"
            "Return strict JSON only (no markdown) with this shape:\n"
            "{\n"
            '  "theme": "one-line video topic",\n'
            '  "structure_rationale": "2-3 sentences explaining the chosen reordering",\n'
            '  "timeline": [\n'
            '    { "source_idx": <int>, "start": <float s>, "end": <float s>,\n'
            '      "label": "HOOK|TEASE|PROBLEM|REVEAL|SATISFYING|EXPLAIN|ANGLE|PAYOFF|CTA",\n'
            '      "desc": "what is visually happening" }\n'
            "  ],\n"
            f'  "vo_script": "Full narration in {lang_name}. Natural, engaging, emotional, persuasive. Synchronised end-to-end."\n'
            "}\n\n"
            "CRITICAL rules:\n"
            "- REORDER scenes into a non-linear viral structure (do NOT preserve source order).\n"
            "- Open with the strongest hook (often a payoff or pain visual, not the intro).\n"
            "- Tease an aha moment early to create a curiosity gap.\n"
            "- Timeline segments MUST NOT repeat identical frames.\n"
            f"- The SUM of (end - start) across timeline MUST be >= {min_dur:.1f} seconds.\n"
            "- To reach the target, you MAY include multiple non-overlapping sub-ranges of the same scene, use longer slices, and include less critical but still useful scenes.\n"
            "- Only truly weak/filler moments (cut=true) can be fully excluded.\n"
            "- vo_script word count should be pacing-matched (~2.3 words/sec English, ~2.1 PT/ES)."
        )

        response = _generate_with_retry(
            client,
            contents=prompt,
            system_instruction=PLANNING_SYSTEM,
        )
        return _parse_json(response.text)

    plan = await _ask()
    plan = _validate_timeline(plan, source_analyses)
    total = sum(float(s["end"]) - float(s["start"]) for s in plan.get("timeline", []))

    # If too short, re-ask with explicit correction
    attempts = 0
    while total < min_dur - 0.5 and attempts < 2:
        attempts += 1
        shortfall = min_dur - total
        plan = await _ask(
            extra=(
                f"PREVIOUS ATTEMPT WAS TOO SHORT: total timeline duration was {total:.1f}s, "
                f"which is {shortfall:.1f}s BELOW the required {min_dur:.1f}s. "
                f"ALSO: every timestamp MUST be within the real source durations given above "
                f"(clip 0 max = {source_analyses[0].get('source_duration', 0):.1f}s). "
                "NEVER invent timestamps past the source duration. "
                "Add more scenes, extend existing segments, or include additional sub-ranges of the source. "
                "Rebuild the full JSON from scratch."
            )
        )
        plan = _validate_timeline(plan, source_analyses)
        total = sum(float(s["end"]) - float(s["start"]) for s in plan.get("timeline", []))

    # Deterministic safety net: if still short, pad by extending last segment(s) forward
    if total < min_dur - 0.5 and plan.get("timeline"):
        needed = min_dur - total
        for seg in plan["timeline"]:
            src_dur = source_analyses[int(seg.get("source_idx", 0))].get("source_duration", 0)
            room = src_dur - float(seg["end"]) - 0.1
            if room > 0:
                grow = min(room, needed)
                seg["end"] = float(seg["end"]) + grow
                needed -= grow
                if needed <= 0:
                    break

    return plan


def _validate_timeline(plan: dict, source_analyses: list[dict]) -> dict:
    """Clip every segment to real source bounds and drop invalid ones."""
    cleaned = []
    for seg in plan.get("timeline", []):
        try:
            idx = int(seg.get("source_idx", 0))
            if idx < 0 or idx >= len(source_analyses):
                continue
            src_dur = float(source_analyses[idx].get("source_duration", 0))
            start = max(0.0, float(seg["start"]))
            end = min(src_dur - 0.05, float(seg["end"]))
            if end - start < 0.5:
                continue
            seg["start"] = round(start, 3)
            seg["end"] = round(end, 3)
            cleaned.append(seg)
        except (KeyError, ValueError, TypeError):
            continue
    plan["timeline"] = cleaned
    return plan


def _parse_json(text: str) -> dict:
    # Strip markdown fences if the model returned any
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    # Try to locate the first {...} block
    m = re.search(r"\{.*\}", t, re.DOTALL)
    if m:
        t = m.group(0)
    return json.loads(t)


# --------------------------- rendering ---------------------------
async def generate_voiceover(script: str, voice: str, out_path: str, rate: str = "-2%") -> float:
    communicate = edge_tts.Communicate(script, voice=voice, rate=rate, pitch="+0Hz")
    await communicate.save(out_path)
    return await ffprobe_duration(out_path)


async def cut_segment(src: str, start: float, end: float, out: str):
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{max(start, 0):.3f}",
        "-to", f"{end:.3f}",
        "-i", src,
        "-c:v", "libx264", "-crf", "22", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-r", "30",
        "-vf", "scale='min(1080,iw)':'-2':flags=lanczos,setsar=1",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
        out,
    ]
    rc, out_txt = await _run(cmd)
    if rc != 0:
        raise RuntimeError(f"ffmpeg cut failed: {out_txt[-500:]}")


async def concat_segments(seg_paths: list[str], out: str, workdir: Path):
    list_file = workdir / "concat.txt"
    list_file.write_text("\n".join(f"file '{p}'" for p in seg_paths) + "\n")
    rc, out_txt = await _run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c", "copy", out,
    ])
    if rc != 0:
        raise RuntimeError(f"ffmpeg concat failed: {out_txt[-500:]}")


async def fit_audio(audio_in: str, target_dur: float, audio_out: str) -> float:
    cur = await ffprobe_duration(audio_in)
    if cur <= 0:
        raise RuntimeError("Invalid VO audio")
    tempo = cur / target_dur
    tempo = max(0.85, min(1.15, tempo))  # keep natural
    rc, out_txt = await _run([
        "ffmpeg", "-y", "-i", audio_in,
        "-filter:a", f"atempo={tempo:.4f}",
        "-c:a", "libmp3lame", "-q:a", "2",
        audio_out,
    ])
    if rc != 0:
        raise RuntimeError(f"atempo failed: {out_txt[-500:]}")
    return await ffprobe_duration(audio_out)


async def mux(video: str, audio: str, out: str):
    rc, out_txt = await _run([
        "ffmpeg", "-y", "-i", video, "-i", audio,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
        "-shortest", out,
    ])
    if rc != 0:
        raise RuntimeError(f"ffmpeg mux failed: {out_txt[-500:]}")


# --------------------------- main pipeline ---------------------------
async def run_pipeline(db, project_id: str):
    try:
        proj = await db.projects.find_one({"id": project_id}, {"_id": 0})
        if not proj:
            return
        workdir = STORAGE_ROOT / project_id
        workdir.mkdir(parents=True, exist_ok=True)

        # -------- 1. analyze every uploaded clip --------
        await _update(db, project_id, status="analyzing", progress=5)
        await _log(db, project_id, f"Analysing {len(proj['source_files'])} clip(s) with Gemini {GEMINI_MODEL}")
        source_analyses = []
        for idx, sf in enumerate(proj["source_files"]):
            await _log(db, project_id, f"Analysing clip {idx + 1}/{len(proj['source_files'])}: {sf['filename']}")
            a = await analyze_clip(idx, sf["path"], proj.get("user_prompt", ""))
            a["source_idx"] = idx
            a["source_filename"] = sf["filename"]
            a["source_duration"] = sf.get("duration", 0)
            source_analyses.append(a)
            await _update(db, project_id, progress=5 + int(25 * (idx + 1) / len(proj["source_files"])))

        # -------- 2. build edit plan --------
        await _update(db, project_id, status="planning", progress=35)
        await _log(db, project_id, "Building reordered edit plan + voice-over script")
        plan = await build_plan(
            source_analyses=source_analyses,
            user_prompt=proj.get("user_prompt", ""),
            language=proj.get("language", "en"),
            audience=proj.get("audience", "35-50 year old adults"),
            target_duration_s=float(proj.get("target_duration_s", 85.0)),
        )
        await _update(db, project_id, plan=plan, analyses=source_analyses, progress=45)

        # -------- 3. render segments --------
        await _update(db, project_id, status="rendering", progress=50)
        await _log(db, project_id, f"Cutting {len(plan['timeline'])} segments")
        seg_paths = []
        for i, seg in enumerate(plan["timeline"]):
            src_idx = int(seg.get("source_idx", 0))
            src_path = proj["source_files"][src_idx]["path"]
            out_seg = str(workdir / f"seg_{i:03d}.mp4")
            await cut_segment(src_path, float(seg["start"]), float(seg["end"]), out_seg)
            seg_paths.append(out_seg)
            await _update(db, project_id, progress=50 + int(20 * (i + 1) / len(plan["timeline"])))

        concat_video = str(workdir / "video_reorder.mp4")
        await concat_segments(seg_paths, concat_video, workdir)
        video_dur = await ffprobe_duration(concat_video)
        await _log(db, project_id, f"Reordered video duration: {video_dur:.2f}s")

        # -------- 4. voice-over --------
        await _update(db, project_id, progress=72)
        await _log(db, project_id, f"Generating voice-over with {proj['voice']}")
        vo_path = str(workdir / "voiceover.mp3")
        await generate_voiceover(plan["vo_script"], proj["voice"], vo_path, rate="-2%")

        vo_fit = str(workdir / "voiceover_fit.mp3")
        vo_dur = await fit_audio(vo_path, video_dur, vo_fit)
        await _log(db, project_id, f"Voice-over fitted: {vo_dur:.2f}s")

        # -------- 5. mux --------
        await _update(db, project_id, progress=88)
        final_path = str(workdir / "final.mp4")
        await mux(concat_video, vo_fit, final_path)
        final_dur = await ffprobe_duration(final_path)
        size = os.path.getsize(final_path)

        await _update(
            db,
            project_id,
            status="done",
            progress=100,
            output={
                "path": final_path,
                "filename": "viral_final.mp4",
                "duration_s": round(final_dur, 2),
                "size_bytes": size,
                "size_mb": round(size / (1024 * 1024), 2),
            },
        )
        await _log(db, project_id, f"DONE — final {final_dur:.2f}s, {size // (1024 * 1024)} MB")

    except Exception as e:
        await _update(db, project_id, status="failed", error=str(e))
        await _log(db, project_id, f"ERROR: {e}")

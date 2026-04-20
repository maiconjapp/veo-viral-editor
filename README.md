# Viral Video Editor

Browser-based AI video editor. Upload raw MP4(s), Gemini 2.5 Flash picks the
strongest scenes and reorders them into a non-linear viral structure, a natural
multi-language voice-over is generated with Microsoft Neural TTS (edge-tts),
and ffmpeg produces a final MP4 ready to download.

## Stack
- **Backend**: FastAPI + MongoDB (motor) + ffmpeg + edge-tts + emergentintegrations (Gemini)
- **Frontend**: React 19 + shadcn/ui + TailwindCSS + sonner
- **Infra**: Docker Compose (mongo + backend + frontend/nginx)

## Quick start (Docker)

```bash
cp .env.example .env
# edit .env and set EMERGENT_LLM_KEY

docker compose up -d --build
open http://localhost:8080
```

## Local dev (without Docker)

```bash
# Requires: python 3.11+, node 20+, yarn, ffmpeg, MongoDB running locally

# Backend
cd backend
pip install -r requirements.txt
pip install emergentintegrations==0.1.0 \
  --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/
pip install edge-tts aiofiles python-multipart
export EMERGENT_LLM_KEY=sk-emergent-...
export MONGO_URL=mongodb://localhost:27017
export DB_NAME=viral_editor
export CORS_ORIGINS=*
uvicorn server:app --host 0.0.0.0 --port 8001 --reload

# Frontend
cd ../frontend
echo "REACT_APP_BACKEND_URL=http://localhost:8001" > .env
yarn
yarn start  # opens http://localhost:3000
```

## Architecture

```
upload MP4(s)
      │
      ▼
Gemini 2.5 Flash (multimodal video analysis)
      │  ── scene timestamps + viral_score per scene
      ▼
Gemini 2.5 Flash (planner)
      │  ── REORDERED timeline (non-linear viral structure)
      │  ── voice-over script in target language
      ▼
Timeline validator  (clips to real source bounds, enforces target duration)
      │
      ▼
ffmpeg cut per segment  (H.264 / AAC / 30fps / 1080p max)
      │
      ▼
ffmpeg concat demuxer  ── rebuilt reordered video
      │
      ▼
edge-tts voice-over  (Andrew/Brian/Aria/Antônio/Jorge/... depending on language)
      │
      ▼
ffmpeg atempo  ── fits VO to video duration (±15% clamp)
      │
      ▼
ffmpeg mux   ── new audio + video, drops original audio
      │
      ▼
final.mp4  (MongoDB: status=done, user downloads via /api/projects/{id}/download)
```

## Features
- Upload up to 200 MB per file, unlimited clips per project
- 10 neural voices across English / Portuguese (BR) / Spanish (Latam)
- Custom prompt field for creative instructions to the AI director
- Target audience + target duration knobs
- Live progress bar + streaming logs during rendering
- Timeline view with labels, source timestamps, segment durations
- Generated VO script visible in UI
- One-click MP4 download; in-browser preview player (9:16 vertical)

## License
MIT — do whatever you want, just don't blame us.

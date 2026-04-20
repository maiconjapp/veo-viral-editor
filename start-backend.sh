#!/bin/bash
export GOOGLE_API_KEY=AIzaSyB9DziyuLRIsO8SW5YPiGcw4BtdrKyDxMk
export GEMINI_MODEL=gemini-2.0-flash
export MONGO_URL=mongodb://localhost:27017
export DB_NAME=viral_editor
export CORS_ORIGINS=*

cd /mnt/c/Users/pietr/Downloads/veo/viral-video-editor/viral-video-editor/backend
python3 -m uvicorn server:app --host 0.0.0.0 --port 8001

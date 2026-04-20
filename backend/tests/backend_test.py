"""Backend API tests for the Viral Video Editor."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://engaging-recut.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
SOURCE_VIDEO = "/app/video_work/source.mp4"


# ---------- meta ----------
class TestMeta:
    def test_root(self):
        r = requests.get(f"{API}/")
        assert r.status_code == 200
        data = r.json()
        assert data.get("service") == "viral-video-editor"
        assert data.get("status") == "ok"

    def test_voices(self):
        r = requests.get(f"{API}/voices")
        assert r.status_code == 200
        d = r.json()
        voices = d["voices"]
        langs = {v["lang"] for v in voices}
        assert len(voices) == 10
        assert {"en", "pt", "es"}.issubset(langs)
        assert len(d["languages"]) == 3


# ---------- project CRUD ----------
class TestProjectCRUD:
    created_id = None

    def test_create_project(self):
        payload = {
            "name": "TEST_api_project",
            "voice": "en-US-AndrewNeural",
            "language": "en",
            "user_prompt": "focus on payoff",
            "audience": "35-50 adults",
            "target_duration_s": 60.0,
        }
        r = requests.post(f"{API}/projects", json=payload)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["voice"] == payload["voice"]
        assert d["status"] == "draft"
        assert "id" in d
        TestProjectCRUD.created_id = d["id"]

    def test_create_invalid_voice(self):
        r = requests.post(f"{API}/projects", json={"name": "x", "voice": "bogus-voice"})
        assert r.status_code == 400

    def test_list_projects(self):
        r = requests.get(f"{API}/projects")
        assert r.status_code == 200
        ids = [p["id"] for p in r.json()["projects"]]
        assert TestProjectCRUD.created_id in ids

    def test_get_project(self):
        r = requests.get(f"{API}/projects/{TestProjectCRUD.created_id}")
        assert r.status_code == 200
        assert r.json()["id"] == TestProjectCRUD.created_id

    def test_get_missing(self):
        r = requests.get(f"{API}/projects/does-not-exist-xyz")
        assert r.status_code == 404

    def test_upload_non_mp4_rejected(self):
        files = {"files": ("bad.txt", b"not a video", "text/plain")}
        r = requests.post(f"{API}/projects/{TestProjectCRUD.created_id}/upload", files=files)
        assert r.status_code == 400

    def test_upload_mp4(self):
        assert os.path.exists(SOURCE_VIDEO), "source.mp4 missing"
        with open(SOURCE_VIDEO, "rb") as fh:
            files = {"files": ("source.mp4", fh, "video/mp4")}
            r = requests.post(
                f"{API}/projects/{TestProjectCRUD.created_id}/upload",
                files=files, timeout=180,
            )
        assert r.status_code == 200, r.text
        sf = r.json()["source_files"]
        assert len(sf) == 1
        assert sf[0]["duration"] > 80

    def test_delete_project(self):
        # delete a *different* project so E2E test still runs on created_id
        r0 = requests.post(f"{API}/projects", json={"name": "TEST_delete_me", "voice": "en-US-AriaNeural"})
        pid = r0.json()["id"]
        r = requests.delete(f"{API}/projects/{pid}")
        assert r.status_code == 200
        assert requests.get(f"{API}/projects/{pid}").status_code == 404


# ---------- end-to-end pipeline (slow) ----------
@pytest.mark.slow
class TestPipelineE2E:
    def test_full_pipeline(self):
        # fresh project for the run
        r = requests.post(f"{API}/projects", json={
            "name": "TEST_e2e_pipeline",
            "voice": "en-US-AndrewNeural",
            "language": "en",
            "user_prompt": "make it punchy",
            "audience": "35-50 adults",
            "target_duration_s": 85.0,
        })
        assert r.status_code == 200
        pid = r.json()["id"]

        with open(SOURCE_VIDEO, "rb") as fh:
            up = requests.post(
                f"{API}/projects/{pid}/upload",
                files={"files": ("source.mp4", fh, "video/mp4")},
                timeout=300,
            )
        assert up.status_code == 200

        pr = requests.post(f"{API}/projects/{pid}/process")
        assert pr.status_code == 200

        deadline = time.time() + 10 * 60  # 10 min budget
        statuses_seen = set()
        last = None
        done = False
        while time.time() < deadline:
            try:
                rr = requests.get(f"{API}/projects/{pid}", timeout=30)
                if rr.status_code != 200 or not rr.text.strip():
                    time.sleep(5); continue
                p = rr.json()
            except Exception as ex:
                print(f"poll transient: {ex}")
                time.sleep(5); continue
            last = p
            statuses_seen.add(p["status"])
            if p["status"] == "done":
                done = True; break
            if p["status"] == "failed":
                pytest.fail(f"Pipeline failed: {p.get('error')}")
            time.sleep(5)
        if not done:
            pytest.fail(f"Pipeline did not finish in time. Last status: {last and last.get('status')}, seen={statuses_seen}")

        # status transitions
        assert {"queued"}.issubset(statuses_seen) or "analyzing" in statuses_seen
        assert "done" == last["status"]

        # plan checks — non-linear + bounded
        tl = last["plan"]["timeline"]
        src_dur = last["source_files"][0]["duration"]
        assert len(tl) >= 2
        assert tl[0]["start"] > 0.05 or any(s["source_idx"] != 0 for s in tl) or tl[0]["end"] < src_dur, \
            "first segment looks like raw source start — not reordered"
        # reorder check: starts are not monotonically increasing
        starts = [s["start"] for s in tl]
        assert starts != sorted(starts), f"timeline appears linear (sorted) — {starts}"
        # bounds check
        for s in tl:
            assert 0 <= s["start"] < s["end"] <= src_dur + 0.1, f"segment out of bounds: {s}"

        # output duration
        out = last["output"]
        assert out["duration_s"] >= 80, f"final duration too short: {out['duration_s']}"
        assert out["size_mb"] > 0

        # download
        dl = requests.get(f"{API}/projects/{pid}/download", stream=True)
        assert dl.status_code == 200
        assert dl.headers.get("content-type", "").startswith("video/mp4")
        total = sum(len(c) for c in dl.iter_content(1024 * 256))
        assert total > 500_000

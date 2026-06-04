import os
import uuid
import asyncio
import shutil
import time
import subprocess
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from faster_whisper import WhisperModel
import edge_tts
from deep_translator import GoogleTranslator
import ffmpeg

# ── Config ──────────────────────────────────────────────
MAX_FILE_SIZE_MB  = 200          # ridotto per Render free
MAX_DURATION_SEC  = 15 * 60      # 15 minuti max su Render free
MAX_TEXT_CHARS    = 10_000
JOB_TTL_HOURS     = 2
WHISPER_MODEL     = "tiny"       # tiny = ~200MB RAM, sufficiente per Render free
# ────────────────────────────────────────────────────────

app = FastAPI(title="Doppiaggio IA API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

_whisper_model = None

def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = WhisperModel(
            WHISPER_MODEL,
            device="cpu",
            compute_type="int8",
            cpu_threads=1,        # limita thread per non saturare la CPU
            num_workers=1,
        )
    return _whisper_model

jobs: dict = {}
_processing_lock = asyncio.Lock()

VOICES = {
    "isabella": "it-IT-IsabellaNeural",
    "diego":    "it-IT-DiegoNeural",
    "elsa":     "it-IT-ElsaNeural",
}

@app.on_event("startup")
async def startup_event():
    # Carica il modello in background senza bloccare lo startup
    import threading
    threading.Thread(target=get_whisper_model, daemon=True).start()

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "whisper_model": WHISPER_MODEL,
        "max_file_mb": MAX_FILE_SIZE_MB,
        "max_duration_min": MAX_DURATION_SEC // 60,
        "jobs_count": len(jobs),
    }

@app.get("/voices")
async def get_voices():
    return [
        {"id": "isabella", "name": "Isabella (F) — naturale", "gender": "F"},
        {"id": "diego",    "name": "Diego (M) — naturale",    "gender": "M"},
        {"id": "elsa",     "name": "Elsa (F) — formale",      "gender": "F"},
    ]

@app.get("/jobs")
async def list_jobs():
    return list(jobs.values())

@app.post("/dub")
async def dub_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    voice: str = Form("isabella"),
    source_lang: str = Form("auto"),
):
    allowed_ext = (".mp4", ".mov", ".avi", ".mkv", ".webm")
    if not file.filename.lower().endswith(allowed_ext):
        raise HTTPException(400, f"Formato non supportato. Usa: MP4, MOV, AVI, MKV")

    job_id  = str(uuid.uuid4())
    job_dir = UPLOAD_DIR / job_id
    job_dir.mkdir(exist_ok=True)
    video_path = job_dir / f"input{Path(file.filename).suffix}"

    # Lettura a chunk — non carica tutto in RAM
    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    total = 0
    with open(video_path, "wb") as out:
        while chunk := await file.read(512 * 1024):  # 512KB per chunk
            total += len(chunk)
            if total > max_bytes:
                shutil.rmtree(job_dir, ignore_errors=True)
                raise HTTPException(413, f"File troppo grande. Limite: {MAX_FILE_SIZE_MB} MB")
            out.write(chunk)

    duration = get_video_duration(str(video_path))
    if duration > MAX_DURATION_SEC:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(400,
            f"Video troppo lungo ({int(duration//60)}m {int(duration%60)}s). "
            f"Limite su server gratuito: {MAX_DURATION_SEC//60} minuti.")

    active = sum(1 for j in jobs.values() if j["status"] in ("queued", "processing"))

    jobs[job_id] = {
        "id":           job_id,
        "filename":     file.filename,
        "voice":        voice,
        "status":       "queued",
        "step":         0,
        "step_name":    f"In coda (posizione {active + 1})..." if active > 0 else "In attesa...",
        "progress":     0,
        "error":        None,
        "output_file":  None,
        "transcript":   None,
        "translation":  None,
        "duration_sec": round(duration, 1),
        "created_at":   time.time(),
        "queue_pos":    active + 1,
    }

    background_tasks.add_task(process_video, job_id, video_path, voice, source_lang)
    background_tasks.add_task(cleanup_old_jobs)
    return {"job_id": job_id, "duration_sec": duration, "queue_pos": active + 1}

@app.get("/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Job non trovato")
    return jobs[job_id]

@app.get("/download/{job_id}")
async def download(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Job non trovato")
    job = jobs[job_id]
    if job["status"] != "done":
        raise HTTPException(400, "Il video non è ancora pronto")
    output_path = Path(job["output_file"])
    if not output_path.exists():
        raise HTTPException(404, "File output non trovato")
    return FileResponse(
        output_path,
        media_type="video/mp4",
        filename=f"doppiato_it_{job_id[:8]}.mp4"
    )

@app.delete("/job/{job_id}")
async def delete_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Job non trovato")
    shutil.rmtree(UPLOAD_DIR / job_id, ignore_errors=True)
    out_file = jobs[job_id].get("output_file")
    if out_file:
        Path(out_file).unlink(missing_ok=True)
    del jobs[job_id]
    return {"deleted": job_id}

async def process_video(job_id: str, video_path: Path, voice: str, source_lang: str):
    # Coda sequenziale: aspetta che finisca il job in corso
    while True:
        processing = [jid for jid, j in jobs.items()
                      if j["status"] == "processing" and jid != job_id]
        if not processing:
            break
        jobs[job_id]["step_name"] = f"In coda..."
        await asyncio.sleep(3)

    job       = jobs[job_id]
    job_dir   = video_path.parent
    voice_name = VOICES.get(voice, VOICES["isabella"])

    try:
        # Step 1 — Estrai audio
        update_job(job_id, step=1, step_name="Estrazione audio...", progress=8)
        audio_path = job_dir / "audio.wav"
        r = subprocess.run([
            "ffmpeg", "-y", "-i", str(video_path),
            "-ac", "1", "-ar", "16000", "-f", "wav", str(audio_path)
        ], capture_output=True, timeout=120)
        if r.returncode != 0:
            raise Exception(f"Estrazione audio fallita: {r.stderr.decode()[:300]}")

        # Step 2 — Trascrivi
        update_job(job_id, step=2, step_name="Trascrizione audio (Whisper)...", progress=25)
        model = get_whisper_model()
        detect_lang = None if source_lang == "auto" else source_lang
        segments, info = model.transcribe(
            str(audio_path),
            language=detect_lang,
            beam_size=5,
            best_of=3,
            temperature=0.0,
            vad_filter=True,
        )
        transcript    = " ".join(seg.text.strip() for seg in segments)
        detected_lang = info.language
        job["transcript"]    = transcript
        job["detected_lang"] = detected_lang

        if not transcript.strip():
            raise Exception("Nessun parlato rilevato nel video. Verifica che il video abbia audio.")

        # Step 3 — Traduci
        update_job(job_id, step=3, step_name="Traduzione in italiano...", progress=50)
        translation = translate_text(transcript, detected_lang)

        if len(translation) > MAX_TEXT_CHARS:
            translation = translation[:MAX_TEXT_CHARS]
            job["truncated"] = True
        job["translation"] = translation

        # Step 4 — Sintesi vocale
        update_job(job_id, step=4, step_name=f"Sintesi voce ({voice})...", progress=68)
        tts_path = job_dir / "tts_audio.mp3"
        communicate = edge_tts.Communicate(translation, voice_name)
        await communicate.save(str(tts_path))

        if not tts_path.exists() or tts_path.stat().st_size < 1000:
            raise Exception("Generazione voce fallita — file audio vuoto")

        # Step 5 — Fondi video + audio
        update_job(job_id, step=5, step_name="Composizione video finale...", progress=85)
        output_path = OUTPUT_DIR / f"{job_id}_dubbed.mp4"
        r = subprocess.run([
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(tts_path),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-vcodec", "copy",
            "-acodec", "aac",
            "-b:a", "128k",
            str(output_path)
        ], capture_output=True, timeout=300)
        if r.returncode != 0:
            raise Exception(f"Composizione video fallita: {r.stderr.decode()[:300]}")

        update_job(job_id, step=6, step_name="Completato!", progress=100, status="done")
        job["output_file"] = str(output_path)

        # Pulizia file temporanei
        for tmp in [audio_path, tts_path, video_path]:
            tmp.unlink(missing_ok=True)

    except Exception as e:
        jobs[job_id]["status"]    = "error"
        jobs[job_id]["error"]     = str(e)
        jobs[job_id]["step_name"] = f"Errore: {str(e)[:200]}"

def translate_text(text: str, detected_lang: str) -> str:
    if detected_lang == "it":
        return text
    chunks     = [text[i:i+4500] for i in range(0, len(text), 4500)]
    translated = []
    for chunk in chunks:
        try:
            t = GoogleTranslator(source="auto", target="it").translate(chunk)
            translated.append(t)
        except Exception as e:
            raise Exception(f"Traduzione fallita: {e}")
    return " ".join(translated)

def update_job(job_id, step=None, step_name=None, progress=None, status="processing"):
    job = jobs[job_id]
    job["status"] = status
    if step      is not None: job["step"]      = step
    if step_name is not None: job["step_name"] = step_name
    if progress  is not None: job["progress"]  = progress

def get_video_duration(video_path: str) -> float:
    try:
        probe = ffmpeg.probe(video_path)
        return float(probe["format"]["duration"])
    except Exception:
        return 0.0

def cleanup_old_jobs():
    cutoff = time.time() - JOB_TTL_HOURS * 3600
    to_delete = [jid for jid, j in list(jobs.items()) if j.get("created_at", 0) < cutoff]
    for jid in to_delete:
        shutil.rmtree(UPLOAD_DIR / jid, ignore_errors=True)
        out_file = jobs[jid].get("output_file")
        if out_file:
            Path(out_file).unlink(missing_ok=True)
        del jobs[jid]

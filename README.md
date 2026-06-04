# 🎬 DoppiaVideo — Doppiaggio automatico in italiano

App gratuita per doppiare qualsiasi video in italiano usando AI open source.

## Stack tecnologico (tutto gratuito)

| Componente | Tool | Scopo |
|---|---|---|
| Trascrizione | Whisper (OpenAI) | Audio → Testo |
| Traduzione | Google Translate (free) | Testo → Italiano |
| Sintesi vocale | EdgeTTS (Microsoft) | Italiano → Audio |
| Montaggio | FFmpeg | Audio → Video |
| Backend | FastAPI (Python) | API REST |
| Frontend | HTML/CSS/JS vanilla | Interfaccia utente |

---

## 🚀 Avvio rapido (locale)

### Prerequisiti
- Python 3.10+
- FFmpeg installato (`brew install ffmpeg` su Mac, `apt install ffmpeg` su Linux)
- Node.js (opzionale, solo per servire il frontend)

### 1. Backend

```bash
cd backend

# Crea ambiente virtuale
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Installa dipendenze
pip install -r requirements.txt

# Avvia server (porta 8000)
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Il primo avvio scaricherà il modello Whisper (~140MB). Ci vogliono 1-2 minuti.

### 2. Frontend

Apri semplicemente `frontend/index.html` nel browser, oppure servi con:

```bash
cd frontend
python -m http.server 3000
# Vai su http://localhost:3000
```

Nel campo "URL backend" lascia `http://localhost:8000` e premi Salva.

---

## 🐳 Deploy con Docker

### Backend su Docker

```bash
cd backend
docker build -t doppiavideo-backend .
docker run -p 8000:8000 -v $(pwd)/outputs:/app/outputs doppiavideo-backend
```

### Deploy gratuito su Render.com

1. Crea account su https://render.com (gratuito)
2. Crea un nuovo **Web Service**
3. Collega il repository GitHub
4. Imposta:
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: Free (512MB RAM) — ⚠️ Whisper base richiede ~1GB RAM, usa almeno il piano Starter ($7/mese) per video lunghi
5. Copia l'URL del servizio (es. `https://doppiavideo-xxx.onrender.com`)
6. Incollalo nel campo "URL backend" del frontend

### Frontend su Vercel/Netlify (gratuito)

1. Carica la cartella `frontend` su Vercel o Netlify
2. Deploy automatico

---

## ⚙️ Configurazione avanzata

### Modelli Whisper disponibili

Modifica `main.py` riga `model = whisper.load_model("base")`:

| Modello | Dimensione | Velocità | Qualità |
|---|---|---|---|
| `tiny` | 39MB | Molto veloce | Base |
| `base` | 74MB | Veloce | **Buona (consigliato)** |
| `small` | 244MB | Medio | Ottima |
| `medium` | 769MB | Lento | Eccellente |
| `large` | 1.5GB | Molto lento | Massima |

### Voci italiane EdgeTTS

Le voci disponibili sono:
- `it-IT-IsabellaNeural` — voce femminile naturale
- `it-IT-DiegoNeural` — voce maschile naturale  
- `it-IT-ElsaNeural` — voce femminile formale

---

## 📝 Limitazioni

- **Nessun lip sync**: l'audio viene sostituito ma le labbra del video non si sincronizzano (questa funzione richiede modelli costosi come Wav2Lip)
- **Timing audio**: per video con musica in sottofondo, l'audio originale viene completamente rimosso
- **Piano gratuito Render**: il server va in sleep dopo 15 minuti di inattività — il primo avvio può richiedere 30 secondi
- **Video lunghi**: Whisper impiega circa 1/10 del tempo del video (es. 10 min di video → ~1 min di trascrizione)

---

## 🔧 Struttura progetto

```
doppiavideo/
├── backend/
│   ├── main.py          # API FastAPI
│   ├── requirements.txt # Dipendenze Python
│   └── Dockerfile       # Per deploy containerizzato
└── frontend/
    └── index.html       # App web completa (single file)
```

---

## 🆓 Costi

**Tutto gratuito!** Nessuna API key necessaria.

- Whisper: open source, gira in locale
- EdgeTTS: API Microsoft pubblica, nessun account
- Google Translate (deep-translator): ~500k caratteri/giorno gratis
- FFmpeg: open source

L'unico costo potenziale è l'hosting del backend se superi i limiti del piano gratuito.

Passo 1 — Scarica il progetto
Scarica lo ZIP qui sopra (doppiavideo.zip) e estrailo sul desktop o in una cartella a tua scelta.

Passo 2 — Installa Python
Vai su https://www.python.org/downloads e scarica Python 3.11 o superiore. Durante l'installazione su Windows, spunta la casella "Add Python to PATH".
Per verificare che sia installato, apri il terminale e scrivi:
python --version

Passo 3 — Installa FFmpeg
FFmpeg è il programma che gestisce i video.
Su Mac:
brew install ffmpeg
(se non hai Homebrew: https://brew.sh)
Su Windows:

Vai su https://ffmpeg.org/download.html
Scarica la versione per Windows (build da "gyan.dev")
Estrai lo ZIP e copia la cartella in C:\ffmpeg
Aggiungi C:\ffmpeg\bin alle variabili d'ambiente PATH

Su Linux/Ubuntu:
sudo apt install ffmpeg

Passo 4 — Avvia il backend
Apri il terminale, entra nella cartella backend del progetto:
bashcd percorso/doppiavideo/backend
Crea l'ambiente virtuale e installa le dipendenze:
bashpython -m venv venv
Mac/Linux:
bashsource venv/bin/activate
pip install -r requirements.txt
Windows:
bashvenv\Scripts\activate
pip install -r requirements.txt
L'installazione scarica Whisper, EdgeTTS ecc. — ci vogliono 3-5 minuti.
Poi avvia il server:
bashuvicorn main:app --reload
La prima volta scarica il modello Whisper (~74MB) — aspetta finché vedi:
Application startup complete.
Lascia questo terminale aperto. Il backend gira su http://localhost:8000.

Passo 5 — Apri il frontend
Apri la cartella frontend del progetto ed esegui un doppio click su index.html. Si apre nel browser.
Nel campo in alto che dice "URL backend", lascia http://localhost:8000 e premi Salva.

Passo 6 — Doppia il primo video

Trascina un video MP4 nella zona di upload
Scegli la lingua originale e la voce italiana
Premi Avvia doppiaggio in italiano
Aspetta (vedrai i 5 step avanzare)
Scarica il video doppiato
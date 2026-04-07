"""
Real Estate AI Video Pipeline — Web Server
==========================================
Flask App: Upload Foto → Pipeline startet → Video Download

Deploy auf Railway.app:
  1. GitHub Repo erstellen, diese Dateien pushen
  2. railway.app → New Project → Deploy from GitHub
  3. Environment Variables setzen (HF_API_KEY, HF_SECRET, ANTHROPIC_KEY)
  4. URL teilen → vom Smartphone öffnen → fertig
"""

from flask import Flask, request, jsonify, send_file, render_template_string
import os, json, time, base64, requests, subprocess, threading, uuid
from pathlib import Path
from datetime import datetime
import anthropic
import higgsfield_client

app = Flask(__name__)

# ── Keys (Railway Environment Variables) ────────────────────
HF_API_KEY    = os.environ.get("HF_API_KEY",    "DEIN_KEY_HIER")
HF_SECRET     = os.environ.get("HF_SECRET",     "DEIN_SECRET_HIER")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_KEY", "DEIN_ANTHROPIC_KEY_HIER")

higgsfield_client.api_key    = HF_API_KEY
higgsfield_client.api_secret = HF_SECRET
claude = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

# ── Job-Status Store (in-memory, reicht für Single-User) ────
jobs = {}   # job_id → { status, progress, message, result_path }

WORKDIR = Path("/tmp/realestate_jobs")
WORKDIR.mkdir(exist_ok=True)


# ════════════════════════════════════════════════════════════
#  FRONTEND — Mobile-optimierte Web-App
# ════════════════════════════════════════════════════════════

HTML = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<title>Estate AI</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;600&family=DM+Mono:wght@300;400&display=swap" rel="stylesheet">
<style>
  :root {
    --gold: #C9A84C;
    --gold-dim: #8B6E2E;
    --bg: #0C0C0A;
    --surface: #141410;
    --border: rgba(201,168,76,0.15);
    --text: #E8E0CC;
    --muted: #6B6355;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
  
  html, body {
    background: var(--bg);
    color: var(--text);
    font-family: 'DM Mono', monospace;
    min-height: 100vh;
    overflow-x: hidden;
  }

  /* Grain overlay */
  body::before {
    content: '';
    position: fixed; inset: 0;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.04'/%3E%3C/svg%3E");
    opacity: 0.4;
    pointer-events: none;
    z-index: 0;
  }

  .container {
    position: relative; z-index: 1;
    max-width: 480px;
    margin: 0 auto;
    padding: 0 20px 60px;
  }

  /* Header */
  .header {
    padding: 48px 0 32px;
    text-align: center;
  }
  .logo {
    font-family: 'Cormorant Garamond', serif;
    font-size: 11px;
    font-weight: 400;
    letter-spacing: 0.4em;
    color: var(--gold);
    text-transform: uppercase;
    margin-bottom: 16px;
  }
  .headline {
    font-family: 'Cormorant Garamond', serif;
    font-size: 38px;
    font-weight: 300;
    line-height: 1.1;
    color: var(--text);
    letter-spacing: -0.01em;
  }
  .headline em {
    font-style: italic;
    color: var(--gold);
  }
  .subline {
    font-size: 10px;
    color: var(--muted);
    letter-spacing: 0.15em;
    margin-top: 14px;
    text-transform: uppercase;
  }

  /* Upload Zone */
  .upload-zone {
    border: 1px solid var(--border);
    border-radius: 2px;
    padding: 40px 20px;
    text-align: center;
    cursor: pointer;
    transition: border-color 0.3s, background 0.3s;
    margin-bottom: 16px;
    position: relative;
    overflow: hidden;
  }
  .upload-zone::before {
    content: '';
    position: absolute; inset: 0;
    background: linear-gradient(135deg, rgba(201,168,76,0.03) 0%, transparent 60%);
    pointer-events: none;
  }
  .upload-zone:active, .upload-zone.drag { 
    border-color: var(--gold);
    background: rgba(201,168,76,0.04);
  }
  .upload-zone.has-file { border-color: rgba(201,168,76,0.4); }
  
  .upload-icon {
    font-size: 32px;
    margin-bottom: 12px;
    display: block;
  }
  .upload-text {
    font-size: 11px;
    color: var(--muted);
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }
  .upload-file-name {
    font-size: 12px;
    color: var(--gold);
    margin-top: 8px;
    font-family: 'DM Mono', monospace;
  }
  input[type=file] { display: none; }

  /* Form Fields */
  .field { margin-bottom: 12px; }
  .field label {
    display: block;
    font-size: 9px;
    letter-spacing: 0.2em;
    color: var(--muted);
    text-transform: uppercase;
    margin-bottom: 6px;
  }
  .field input {
    width: 100%;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 1px;
    padding: 14px 16px;
    color: var(--text);
    font-family: 'DM Mono', monospace;
    font-size: 13px;
    outline: none;
    transition: border-color 0.2s;
    -webkit-appearance: none;
  }
  .field input:focus { border-color: rgba(201,168,76,0.4); }
  .field input::placeholder { color: var(--muted); }

  /* Button */
  .btn {
    width: 100%;
    padding: 18px;
    background: var(--gold);
    color: #0C0C0A;
    border: none;
    border-radius: 1px;
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    font-weight: 400;
    letter-spacing: 0.25em;
    text-transform: uppercase;
    cursor: pointer;
    transition: opacity 0.2s, transform 0.1s;
    margin-top: 8px;
  }
  .btn:active { transform: scale(0.99); opacity: 0.85; }
  .btn:disabled { opacity: 0.3; cursor: not-allowed; }

  /* Progress */
  .progress-section {
    display: none;
    margin-top: 32px;
  }
  .progress-section.visible { display: block; }

  .progress-label {
    font-size: 9px;
    letter-spacing: 0.2em;
    color: var(--muted);
    text-transform: uppercase;
    margin-bottom: 10px;
    display: flex;
    justify-content: space-between;
  }
  .progress-bar {
    height: 1px;
    background: rgba(201,168,76,0.1);
    border-radius: 0;
    overflow: hidden;
    margin-bottom: 20px;
  }
  .progress-fill {
    height: 100%;
    background: var(--gold);
    width: 0%;
    transition: width 0.8s cubic-bezier(0.4,0,0.2,1);
  }

  .log-container {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 1px;
    padding: 16px;
    max-height: 200px;
    overflow-y: auto;
    font-size: 11px;
    line-height: 1.8;
    color: var(--muted);
  }
  .log-entry { display: flex; gap: 10px; }
  .log-entry .log-icon { color: var(--gold); flex-shrink: 0; }
  .log-entry.active .log-msg { color: var(--text); }

  /* Steps visual */
  .steps {
    display: flex;
    justify-content: space-between;
    margin-bottom: 20px;
    padding: 0 4px;
  }
  .step {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    flex: 1;
  }
  .step-dot {
    width: 6px; height: 6px;
    border-radius: 50%;
    background: rgba(201,168,76,0.15);
    border: 1px solid var(--border);
    transition: all 0.4s;
  }
  .step.done .step-dot { background: var(--gold); border-color: var(--gold); }
  .step.active .step-dot { 
    background: transparent; 
    border-color: var(--gold); 
    box-shadow: 0 0 8px rgba(201,168,76,0.4);
    animation: pulse 1.5s ease-in-out infinite;
  }
  .step-name {
    font-size: 8px;
    letter-spacing: 0.1em;
    color: var(--muted);
    text-transform: uppercase;
    text-align: center;
  }
  .step.done .step-name, .step.active .step-name { color: var(--gold); }

  @keyframes pulse {
    0%, 100% { box-shadow: 0 0 4px rgba(201,168,76,0.3); }
    50% { box-shadow: 0 0 12px rgba(201,168,76,0.7); }
  }

  /* Result */
  .result-section {
    display: none;
    margin-top: 32px;
    text-align: center;
  }
  .result-section.visible { display: block; }
  
  .result-title {
    font-family: 'Cormorant Garamond', serif;
    font-size: 28px;
    font-weight: 300;
    color: var(--gold);
    margin-bottom: 6px;
  }
  .result-sub {
    font-size: 10px;
    color: var(--muted);
    letter-spacing: 0.15em;
    text-transform: uppercase;
    margin-bottom: 24px;
  }
  .download-btn {
    display: block;
    width: 100%;
    padding: 18px;
    background: transparent;
    border: 1px solid var(--gold);
    color: var(--gold);
    border-radius: 1px;
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.25em;
    text-transform: uppercase;
    text-decoration: none;
    cursor: pointer;
    margin-bottom: 10px;
    transition: background 0.2s, color 0.2s;
  }
  .download-btn:active { background: var(--gold); color: #0C0C0A; }

  .new-btn {
    background: none;
    border: 1px solid var(--border);
    color: var(--muted);
    padding: 14px;
    width: 100%;
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    cursor: pointer;
    border-radius: 1px;
    transition: border-color 0.2s, color 0.2s;
  }
  .new-btn:active { border-color: var(--gold); color: var(--text); }

  /* Divider */
  .divider {
    display: flex;
    align-items: center;
    gap: 12px;
    margin: 24px 0;
  }
  .divider-line { flex: 1; height: 1px; background: var(--border); }
  .divider-text { font-size: 9px; color: var(--muted); letter-spacing: 0.2em; text-transform: uppercase; }

  /* Preview thumbnails */
  .phases-preview {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 3px;
    margin-top: 20px;
  }
  .phase-thumb {
    aspect-ratio: 1;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 1px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 7px;
    color: var(--muted);
    letter-spacing: 0.05em;
    transition: border-color 0.3s, background 0.3s;
    overflow: hidden;
  }
  .phase-thumb.done {
    border-color: rgba(201,168,76,0.3);
    background: rgba(201,168,76,0.05);
    color: var(--gold);
  }
  .phase-thumb img { width: 100%; height: 100%; object-fit: cover; }
</style>
</head>
<body>
<div class="container">

  <!-- Header -->
  <div class="header">
    <div class="logo">Estate · AI · Studio</div>
    <h1 class="headline">Vom ersten<br>Stein zum <em>fertigen</em><br>Zuhause.</h1>
    <p class="subline">1 Foto → 87 Sekunden Cinematic Video</p>
  </div>

  <!-- Upload Form -->
  <div id="form-section">
    <div class="upload-zone" id="upload-zone" onclick="document.getElementById('file-input').click()">
      <span class="upload-icon">📷</span>
      <div class="upload-text">Immobilienfoto hochladen</div>
      <div class="upload-text" style="margin-top:4px;font-size:9px;">JPG oder PNG · min. 1MP</div>
      <div class="upload-file-name" id="file-name"></div>
    </div>
    <input type="file" id="file-input" accept="image/jpeg,image/png" onchange="handleFile(this)">

    <div class="field">
      <label>Name der Immobilie</label>
      <input type="text" id="prop-name" placeholder="z.B. Villa Marbella" value="">
    </div>
    <div class="field">
      <label>Typ</label>
      <input type="text" id="prop-type" placeholder="z.B. Luxusvilla, Wohnanlage, Penthouse" value="">
    </div>

    <button class="btn" id="start-btn" onclick="startPipeline()" disabled>
      Pipeline starten →
    </button>
  </div>

  <!-- Progress -->
  <div class="progress-section" id="progress-section">
    
    <!-- Steps -->
    <div class="steps">
      <div class="step" id="step-prompts">
        <div class="step-dot"></div>
        <div class="step-name">Prompts</div>
      </div>
      <div class="step" id="step-images">
        <div class="step-dot"></div>
        <div class="step-name">Bilder</div>
      </div>
      <div class="step" id="step-videos">
        <div class="step-dot"></div>
        <div class="step-name">Videos</div>
      </div>
      <div class="step" id="step-dolly">
        <div class="step-dot"></div>
        <div class="step-name">Dolly</div>
      </div>
      <div class="step" id="step-cut">
        <div class="step-dot"></div>
        <div class="step-name">Schnitt</div>
      </div>
    </div>

    <div class="progress-label">
      <span id="progress-msg">Starte...</span>
      <span id="progress-pct">0%</span>
    </div>
    <div class="progress-bar">
      <div class="progress-fill" id="progress-fill"></div>
    </div>

    <!-- Phase Thumbnails -->
    <div class="phases-preview" id="phases-preview">
      <div class="phase-thumb" id="thumb-7">P7</div>
      <div class="phase-thumb" id="thumb-6">P6</div>
      <div class="phase-thumb" id="thumb-5">P5</div>
      <div class="phase-thumb" id="thumb-4">P4</div>
      <div class="phase-thumb" id="thumb-3">P3</div>
      <div class="phase-thumb" id="thumb-2">P2</div>
      <div class="phase-thumb" id="thumb-1">P1</div>
    </div>

    <!-- Log -->
    <div class="divider">
      <div class="divider-line"></div>
      <div class="divider-text">Live Log</div>
      <div class="divider-line"></div>
    </div>
    <div class="log-container" id="log-container"></div>
  </div>

  <!-- Result -->
  <div class="result-section" id="result-section">
    <div class="result-title">Fertig.</div>
    <div class="result-sub" id="result-punchline"></div>
    <a class="download-btn" id="download-link" href="#" download>
      ↓ Video herunterladen
    </a>
    <button class="new-btn" onclick="resetApp()">
      Neues Video erstellen
    </button>
  </div>

</div>

<script>
let currentJobId = null;
let pollInterval = null;
let selectedFile = null;

function handleFile(input) {
  const file = input.files[0];
  if (!file) return;
  selectedFile = file;
  document.getElementById('file-name').textContent = file.name;
  document.getElementById('upload-zone').classList.add('has-file');
  document.getElementById('upload-zone').querySelector('.upload-icon').textContent = '✅';
  checkReady();
}

// Drag & Drop
const zone = document.getElementById('upload-zone');
zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag'); });
zone.addEventListener('dragleave', () => zone.classList.remove('drag'));
zone.addEventListener('drop', e => {
  e.preventDefault(); zone.classList.remove('drag');
  const file = e.dataTransfer.files[0];
  if (file && file.type.startsWith('image/')) {
    selectedFile = file;
    document.getElementById('file-name').textContent = file.name;
    zone.classList.add('has-file');
    checkReady();
  }
});

function checkReady() {
  const name = document.getElementById('prop-name').value.trim();
  const type = document.getElementById('prop-type').value.trim();
  document.getElementById('start-btn').disabled = !(selectedFile && name && type);
}
document.getElementById('prop-name').addEventListener('input', checkReady);
document.getElementById('prop-type').addEventListener('input', checkReady);

async function startPipeline() {
  if (!selectedFile) return;

  const name = document.getElementById('prop-name').value.trim();
  const type = document.getElementById('prop-type').value.trim();

  // UI State
  document.getElementById('form-section').style.opacity = '0.3';
  document.getElementById('form-section').style.pointerEvents = 'none';
  document.getElementById('progress-section').classList.add('visible');
  document.getElementById('start-btn').disabled = true;

  setStep('prompts', 'active');

  // Formdata
  const fd = new FormData();
  fd.append('image', selectedFile);
  fd.append('name', name);
  fd.append('type', type);

  try {
    const res = await fetch('/start', { method: 'POST', body: fd });
    const data = await res.json();
    if (!data.job_id) throw new Error(data.error || 'Server-Fehler');
    currentJobId = data.job_id;
    pollInterval = setInterval(pollStatus, 3000);
  } catch (e) {
    addLog('❌', e.message);
  }
}

async function pollStatus() {
  if (!currentJobId) return;
  try {
    const res = await fetch('/status/' + currentJobId);
    const data = await res.json();
    updateUI(data);
    if (data.status === 'done' || data.status === 'error') {
      clearInterval(pollInterval);
    }
  } catch (e) { /* ignore */ }
}

function updateUI(data) {
  // Progress bar
  const pct = data.progress || 0;
  document.getElementById('progress-fill').style.width = pct + '%';
  document.getElementById('progress-pct').textContent = pct + '%';
  document.getElementById('progress-msg').textContent = data.message || '';

  // Log
  if (data.log_entry) addLog(data.log_icon || '·', data.log_entry);

  // Steps
  if (pct >= 10) setStep('prompts', 'done');
  if (pct >= 15) setStep('images', 'active');
  if (pct >= 45) { setStep('images', 'done'); setStep('videos', 'active'); }
  if (pct >= 70) { setStep('dolly', 'active'); }
  if (pct >= 80) { setStep('videos', 'done'); setStep('dolly', 'done'); setStep('cut', 'active'); }
  if (pct >= 95) setStep('cut', 'done');

  // Thumbnails
  if (data.thumb) {
    const el = document.getElementById('thumb-' + data.thumb_idx);
    if (el) {
      el.innerHTML = `<img src="${data.thumb}" alt="">`;
      el.classList.add('done');
    }
  }

  // Done
  if (data.status === 'done') {
    document.getElementById('progress-section').style.display = 'none';
    document.getElementById('result-section').classList.add('visible');
    document.getElementById('result-punchline').textContent = data.punchline || '';
    document.getElementById('download-link').href = '/download/' + currentJobId;
  }

  // Error
  if (data.status === 'error') {
    addLog('❌', data.message);
  }
}

function setStep(name, state) {
  const el = document.getElementById('step-' + name);
  if (!el) return;
  el.className = 'step ' + state;
}

function addLog(icon, msg) {
  const container = document.getElementById('log-container');
  const entry = document.createElement('div');
  entry.className = 'log-entry active';
  entry.innerHTML = `<span class="log-icon">${icon}</span><span class="log-msg">${msg}</span>`;
  container.appendChild(entry);
  container.scrollTop = container.scrollHeight;
  // Alte Einträge dimmen
  const all = container.querySelectorAll('.log-entry');
  all.forEach((e, i) => { if (i < all.length - 1) e.classList.remove('active'); });
}

function resetApp() {
  location.reload();
}
</script>
</body>
</html>"""


# ════════════════════════════════════════════════════════════
#  API ROUTES
# ════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/start", methods=["POST"])
def start_job():
    """Startet einen neuen Pipeline-Job im Hintergrund."""
    image_file = request.files.get("image")
    prop_name  = request.form.get("name", "Wohnanlage")
    prop_type  = request.form.get("type", "Immobilie")

    if not image_file:
        return jsonify({"error": "Kein Bild hochgeladen"}), 400

    job_id  = str(uuid.uuid4())[:8]
    job_dir = WORKDIR / job_id
    job_dir.mkdir()

    # Bild speichern
    img_path = job_dir / ("input" + Path(image_file.filename).suffix)
    image_file.save(str(img_path))

    # Job initialisieren
    jobs[job_id] = {
        "status":   "running",
        "progress": 0,
        "message":  "Gestartet",
        "punchline": "",
        "log_entry": "",
        "log_icon":  "·",
        "thumb":     None,
        "thumb_idx": None,
    }

    # Pipeline im Hintergrund starten
    thread = threading.Thread(
        target=run_pipeline_job,
        args=(job_id, str(img_path), prop_name, prop_type, job_dir),
        daemon=True
    )
    thread.start()

    return jsonify({"job_id": job_id})


@app.route("/status/<job_id>")
def job_status(job_id):
    job = jobs.get(job_id, {"status": "not_found"})
    return jsonify(job)


@app.route("/download/<job_id>")
def download_video(job_id):
    job = jobs.get(job_id, {})
    result_path = job.get("result_path")
    if not result_path or not Path(result_path).exists():
        return "Video nicht gefunden", 404
    return send_file(result_path, as_attachment=True, download_name="immobilien_video.mp4")


# ════════════════════════════════════════════════════════════
#  PIPELINE LOGIC (läuft im Background-Thread)
# ════════════════════════════════════════════════════════════

def update_job(job_id, **kwargs):
    jobs[job_id].update(kwargs)


def run_pipeline_job(job_id, img_path, prop_name, prop_type, job_dir):
    """Führt die komplette Pipeline aus — läuft im Hintergrund-Thread."""
    img_dir = job_dir / "images"
    vid_dir = job_dir / "videos"
    img_dir.mkdir(); vid_dir.mkdir()

    try:
        # ── 1. Prompts ──────────────────────────────────────
        update_job(job_id, progress=5, message="Claude generiert Prompts...", log_icon="🧠", log_entry="Claude analysiert Foto und erstellt alle Prompts")
        prompts = generate_prompts(img_path, prop_name, prop_type)
        (job_dir / "prompts.json").write_text(json.dumps(prompts, indent=2, ensure_ascii=False))
        update_job(job_id, progress=12, message="Prompts fertig", log_icon="✅", log_entry=f"Punchline: {prompts['punchlines'][0]}", punchline=prompts["punchlines"][0])

        # ── 2. Bilder ────────────────────────────────────────
        images = {}
        image_jobs = [
            ("img1", "phase_01_fertig.jpg", 7, 1),
            ("img2", "phase_02_fast_fertig.jpg", 6, 2),
            ("img3", "phase_03_rohbau.jpg", 5, 3),
            ("img4", "phase_04_fundament.jpg", 4, 4),
            ("img5", "phase_05_aushub.jpg", 3, 5),
            ("img6", "phase_06_planierung.jpg", 2, 6),
            ("img7", "phase_07_wald.jpg", 1, 7),
            ("img_craftsman", "insert_handwerker.jpg", None, None),
        ]

        for key, filename, thumb_idx, phase_num in image_jobs:
            pct = 15 + len(images) * 4
            update_job(job_id, progress=pct, message=f"Generiere Bild {len(images)+1}/8...",
                      log_icon="🖼️", log_entry=f"Phase {phase_num or 'Handwerker'} → {filename}")

            path = gen_image(prompts["images"][key], img_dir / filename)
            images[key] = str(path)

            if thumb_idx:
                # Thumbnail als base64 für Frontend
                thumb_b64 = "data:image/jpeg;base64," + base64.b64encode(Path(path).read_bytes()).decode()
                update_job(job_id, thumb=thumb_b64, thumb_idx=thumb_idx)

            time.sleep(1)

        update_job(job_id, progress=47, message="Alle Bilder fertig", log_icon="✅", log_entry="8 Phasenbilder generiert")

        # ── 3. Videos ────────────────────────────────────────
        videos = {}
        p = prompts["videos"]
        i = images

        video_jobs = [
            ("v1", i["img7"], i["img6"], "vid_01.mp4", 10),
            ("v2", i["img6"], i["img5"], "vid_02.mp4", 10),
            ("v3", i["img5"], i["img4"], "vid_03.mp4", 10),
            ("v4", i["img4"], i["img3"], "vid_04.mp4", 10),
        ]

        for vkey, start, end, fname, dur in video_jobs:
            idx = len(videos) + 1
            update_job(job_id, progress=50 + idx*3, message=f"Video {idx}/10...",
                      log_icon="🎬", log_entry=f"Übergang {fname}")
            path = gen_video_transition(start, end, p[vkey], vid_dir / fname, dur)
            videos[vkey] = str(path)
            time.sleep(2)

        # Dolly Insert
        update_job(job_id, progress=65, message="Dolly-Insert generieren...", log_icon="🎥", log_entry="Dolly In → Handwerker")
        videos["dolly_in"] = str(gen_video_transition(i["img3"], i["img_craftsman"], p["dolly_in"], vid_dir / "vid_05a_dolly_in.mp4", 5))
        time.sleep(2)

        update_job(job_id, progress=68, message="Handwerker aktiv...", log_icon="👷", log_entry="Handwerker — Blick in die Kamera")
        videos["dolly_active"] = str(gen_video_i2v(i["img_craftsman"], p["dolly_active"], vid_dir / "vid_05b_handwerker.mp4", 7))
        time.sleep(2)

        update_job(job_id, progress=71, message="Dolly Out...", log_icon="🎥", log_entry="Dolly Out → zurück zur Totale")
        videos["dolly_out"] = str(gen_video_transition(i["img_craftsman"], i["img2"], p["dolly_out"], vid_dir / "vid_05c_dolly_out.mp4", 5))
        time.sleep(2)

        # Rest der Videos
        rest_jobs = [
            ("v5", i["img3"], i["img2"], "vid_07.mp4", 10),
            ("v6", i["img2"], i["img1"], "vid_08.mp4", 10),
        ]
        for vkey, start, end, fname, dur in rest_jobs:
            update_job(job_id, progress=75 + len(videos)*1, message=f"Video {fname}...", log_icon="🎬", log_entry=fname)
            videos[vkey] = str(gen_video_transition(start, end, p[vkey], vid_dir / fname, dur))
            time.sleep(2)

        # Finale
        update_job(job_id, progress=80, message="Finale generieren...", log_icon="🎬", log_entry="Crane Down — emotionaler Abschluss")
        videos["v7"] = str(gen_video_i2v(i["img1"], p["v7"], vid_dir / "vid_09_finale.mp4", 10))

        update_job(job_id, progress=85, message="Alle Clips fertig", log_icon="✅", log_entry="10 Video-Clips generiert")

        # ── 4. Finaler Schnitt ───────────────────────────────
        update_job(job_id, progress=90, message="ffmpeg schneidet zusammen...", log_icon="✂️", log_entry="Montage aller Clips")
        final_path = assemble(videos, prompts["punchlines"][0], job_dir)

        update_job(job_id,
            status="done",
            progress=100,
            message="Fertig!",
            log_icon="🏁",
            log_entry="Video fertig — Download bereit",
            result_path=str(final_path)
        )

    except Exception as e:
        update_job(job_id, status="error", message=str(e), log_icon="❌", log_entry=f"Fehler: {e}")


# ════════════════════════════════════════════════════════════
#  HIGGSFIELD HELPER FUNCTIONS
# ════════════════════════════════════════════════════════════

def generate_prompts(img_path, prop_name, prop_type):
    with open(img_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()
    ext = Path(img_path).suffix.lower().replace(".", "")
    mime = {"jpg":"image/jpeg","jpeg":"image/jpeg","png":"image/png"}.get(ext,"image/jpeg")

    res = claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[{"role":"user","content":[
            {"type":"image","source":{"type":"base64","media_type":mime,"data":img_b64}},
            {"type":"text","text":f"""Analysiere diese Immobilie ({prop_type}: {prop_name}) und erstelle ein JSON Prompt-System für eine KI-Video-Produktion die den Bau rückwärts als TimeLapse zeigt.

Antworte NUR mit validem JSON:
{{
  "images": {{
    "img1": "Aerial Golden Hour fertig — 80+ Wörter, same high-angle perspective, ultra-realistic",
    "img2": "Fast fertig Morgenlicht — 60+ Wörter, same perspective",
    "img3": "Rohbau Betonrahmen bedeckt — 60+ Wörter, same perspective",
    "img4": "Fundament Sonnenuntergang — 60+ Wörter, same perspective",
    "img5": "Aushubphase Nachmittag — 60+ Wörter, same perspective",
    "img6": "Planiertes Grundstück sonnig — 50+ Wörter, same perspective",
    "img7": "Unberührter Wald natürlich — 40+ Wörter",
    "img_craftsman": "Maurer Nahaufnahme Rohbau cinematic 16:9 — 50+ Wörter"
  }},
  "videos": {{
    "v1": "Wald→Planierung timelapse statische Kamera",
    "v2": "Planierung→Aushub timelapse statische Kamera",
    "v3": "Aushub→Fundament timelapse statische Kamera",
    "v4": "Fundament→Rohbau timelapse Kräne statische Kamera",
    "v5": "Rohbau→Ausbau timelapse statische Kamera",
    "v6": "Ausbau→Fertig timelapse statische Kamera",
    "v7": "Kamera fährt smooth runter und rein crane down dolly forward golden hour",
    "dolly_in": "Smooth cinematic dolly von Aerial-Totale ran an Maurer, keine Cuts",
    "dolly_active": "Maurer arbeitet rhythmisch, blickt kurz in Kamera, dokumentarisch warm",
    "dolly_out": "Kamera zieht smooth zurück und hoch, Maurer wird klein, volle Baustelle sichtbar"
  }},
  "punchlines": [
    "Emotionaler Spruch 1 max 8 Wörter Deutsch",
    "Emotionaler Spruch 2 max 8 Wörter Deutsch",
    "Emotionaler Spruch 3 max 8 Wörter Deutsch"
  ]
}}"""}
        ]}]
    )
    raw = res.content[0].text.strip()
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"): raw = raw[4:]
    return json.loads(raw.strip())


def img_to_data_url(path):
    ext = Path(path).suffix.lower().replace(".","")
    mime = {"jpg":"image/jpeg","jpeg":"image/jpeg","png":"image/png"}.get(ext,"image/jpeg")
    data = Path(path).read_bytes()
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def gen_image(prompt, out_path):
    result = higgsfield_client.subscribe(
        "bytedance/seedream/v4/text-to-image",
        arguments={"prompt": prompt, "resolution": "2K", "aspect_ratio": "16:9", "camera_fixed": True}
    )
    url = result["images"][0]["url"]
    r = requests.get(url, timeout=60)
    Path(out_path).write_bytes(r.content)
    return out_path


def gen_video_transition(start_img, end_img, prompt, out_path, duration=10):
    result = higgsfield_client.subscribe(
        "kling/v1/image-to-video",
        arguments={
            "start_image_url": img_to_data_url(start_img),
            "end_image_url":   img_to_data_url(end_img),
            "prompt": prompt,
            "duration": duration,
            "mode": "std",
            "cfg_scale": 0.5,
        }
    )
    url = result["videos"][0]["url"]
    r = requests.get(url, timeout=120)
    Path(out_path).write_bytes(r.content)
    return out_path


def gen_video_i2v(image, prompt, out_path, duration=10):
    result = higgsfield_client.subscribe(
        "kling/v1/image-to-video",
        arguments={
            "image_url": img_to_data_url(image),
            "prompt": prompt,
            "duration": duration,
            "cfg_scale": 0.5,
        }
    )
    url = result["videos"][0]["url"]
    r = requests.get(url, timeout=120)
    Path(out_path).write_bytes(r.content)
    return out_path


def assemble(videos, punchline, job_dir):
    vid_dir = job_dir / "videos"
    order = ["v1","v2","v3","v4","dolly_in","dolly_active","dolly_out","v5","v6","v7"]

    # Punchline auf Finale
    finale = Path(videos.get("v7",""))
    if finale.exists():
        finale_txt = vid_dir / "vid_09_finale_text.mp4"
        safe = punchline.replace("'", "\\'")
        subprocess.run([
            "ffmpeg","-y","-i",str(finale),
            "-vf", f"drawtext=text='{safe}':fontsize=48:fontcolor=white:font='Arial Bold':x=(w-text_w)/2:y=(h*0.78):enable='gte(t,6)':alpha='min((t-6)/1.5,1)'",
            "-codec:a","copy", str(finale_txt)
        ], capture_output=True, check=True)
        videos["v7"] = str(finale_txt)

    clips = [videos[k] for k in order if k in videos and Path(videos[k]).exists()]
    concat = job_dir / "concat.txt"
    concat.write_text("\n".join(f"file '{Path(c).resolve()}'" for c in clips))

    final = job_dir / "FINAL_video.mp4"
    subprocess.run([
        "ffmpeg","-y","-f","concat","-safe","0","-i",str(concat),
        "-c:v","libx264","-crf","18","-preset","fast",
        "-pix_fmt","yuv420p","-movflags","+faststart",str(final)
    ], capture_output=True, check=True)
    return final


# ════════════════════════════════════════════════════════════
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

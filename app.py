"""
Immo-Wizard Video Studio — Web App
====================================
Corporate Design: Dunkelblau #0A1628 · Cyan #00C8FF · Gold #FFB347
PWA-ready: manifest.json, Service Worker, Icons
"""

from flask import Flask, request, jsonify, send_file, render_template_string
import os, json, time, base64, requests, subprocess, threading, uuid
from pathlib import Path
import anthropic
import higgsfield_client

app = Flask(__name__, static_folder='.', static_url_path='')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB Upload-Limit

# ── Keys (Railway Environment Variables) ─────────────────────
HF_API_KEY    = os.environ.get("HF_API_KEY",    "DEIN_KEY_HIER")
HF_SECRET     = os.environ.get("HF_SECRET",     "DEIN_SECRET_HIER")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_KEY", "DEIN_KEY_HIER")

higgsfield_client.api_key    = HF_API_KEY
higgsfield_client.api_secret = HF_SECRET
claude = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

jobs = {}
WORKDIR = Path("/tmp/immowizard_jobs")
WORKDIR.mkdir(exist_ok=True)


# ════════════════════════════════════════════════════════════
#  HTML — Immo-Wizard Corporate Design + PWA
# ════════════════════════════════════════════════════════════

HTML = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta name="theme-color" content="#0A1628">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Immo-Wizard">
<link rel="manifest" href="/manifest.json">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="icon" href="/favicon.ico">
<title>Immo-Wizard Video Studio</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;500;600;700&family=Inter:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg:        #0A1628;
    --surface:   #0F1E35;
    --surface2:  #152440;
    --cyan:      #00C8FF;
    --cyan-dim:  #0086AA;
    --gold:      #FFB347;
    --gold-dim:  #AA6E1A;
    --white:     #F0F4FF;
    --muted:     #4A6080;
    --border:    rgba(0,200,255,0.12);
    --border2:   rgba(255,179,71,0.12);
  }

  * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }

  html { scroll-behavior: smooth; }

  body {
    background: var(--bg);
    color: var(--white);
    font-family: 'Inter', sans-serif;
    min-height: 100vh;
    min-height: -webkit-fill-available;
    overflow-x: hidden;
  }

  /* Animated star background */
  body::before {
    content: '';
    position: fixed; inset: 0;
    background:
      radial-gradient(ellipse at 20% 20%, rgba(0,200,255,0.06) 0%, transparent 50%),
      radial-gradient(ellipse at 80% 80%, rgba(255,179,71,0.05) 0%, transparent 50%);
    pointer-events: none;
    z-index: 0;
  }

  .container {
    position: relative; z-index: 1;
    max-width: 440px;
    margin: 0 auto;
    padding: 0 18px 80px;
  }

  /* ── Header ── */
  .header {
    padding: 36px 0 28px;
    text-align: center;
  }

  .logo-wrap {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    margin-bottom: 20px;
  }

  .logo-img {
    width: 52px;
    height: 52px;
    border-radius: 12px;
    border: 1px solid var(--border);
  }

  .logo-text {
    text-align: left;
  }

  .logo-name {
    font-family: 'Rajdhani', sans-serif;
    font-size: 26px;
    font-weight: 700;
    letter-spacing: 0.05em;
    line-height: 1;
  }
  .logo-name .immo { color: var(--white); }
  .logo-name .dash { color: var(--muted); }
  .logo-name .wizard { color: var(--cyan); }

  .logo-tagline {
    font-size: 10px;
    color: var(--muted);
    letter-spacing: 0.15em;
    text-transform: uppercase;
    margin-top: 2px;
  }

  .headline {
    font-family: 'Rajdhani', sans-serif;
    font-size: 30px;
    font-weight: 600;
    line-height: 1.15;
    color: var(--white);
    margin-bottom: 8px;
  }
  .headline .hl-cyan { color: var(--cyan); }
  .headline .hl-gold { color: var(--gold); }

  .subline {
    font-size: 12px;
    color: var(--muted);
    letter-spacing: 0.08em;
  }

  /* ── Cards ── */
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 20px;
    margin-bottom: 14px;
  }

  .card-label {
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--cyan);
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .card-label::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--border);
  }

  /* ── Upload Zone ── */
  .upload-zone {
    border: 1.5px dashed var(--border);
    border-radius: 12px;
    padding: 32px 16px;
    text-align: center;
    cursor: pointer;
    transition: all 0.25s;
    position: relative;
    overflow: hidden;
  }
  .upload-zone::before {
    content: '';
    position: absolute; inset: 0;
    background: radial-gradient(ellipse at center, rgba(0,200,255,0.04), transparent 70%);
    pointer-events: none;
  }
  .upload-zone:active, .upload-zone.drag {
    border-color: var(--cyan);
    background: rgba(0,200,255,0.04);
  }
  .upload-zone.has-file {
    border-color: var(--gold);
    border-style: solid;
    background: rgba(255,179,71,0.03);
  }

  .upload-icon-wrap {
    width: 56px; height: 56px;
    border-radius: 14px;
    background: var(--surface2);
    border: 1px solid var(--border);
    display: flex; align-items: center; justify-content: center;
    margin: 0 auto 12px;
    font-size: 24px;
    transition: all 0.2s;
  }
  .upload-zone.has-file .upload-icon-wrap {
    border-color: var(--gold);
    background: rgba(255,179,71,0.08);
  }

  .upload-title {
    font-family: 'Rajdhani', sans-serif;
    font-size: 16px;
    font-weight: 600;
    color: var(--white);
    margin-bottom: 4px;
  }
  .upload-hint { font-size: 11px; color: var(--muted); }
  .upload-filename {
    font-size: 12px;
    color: var(--gold);
    margin-top: 8px;
    font-family: monospace;
  }
  input[type=file] { display: none; }

  /* ── Fields ── */
  .field { margin-bottom: 12px; }
  .field label {
    display: block;
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 6px;
  }
  .field input {
    width: 100%;
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 13px 15px;
    color: var(--white);
    font-family: 'Inter', sans-serif;
    font-size: 14px;
    outline: none;
    transition: border-color 0.2s;
    -webkit-appearance: none;
  }
  .field input:focus { border-color: rgba(0,200,255,0.4); }
  .field input::placeholder { color: var(--muted); }

  /* ── Button ── */
  .btn-primary {
    width: 100%;
    padding: 17px;
    background: linear-gradient(135deg, var(--cyan) 0%, #0086CC 100%);
    color: var(--bg);
    border: none;
    border-radius: 12px;
    font-family: 'Rajdhani', sans-serif;
    font-size: 16px;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    cursor: pointer;
    transition: opacity 0.2s, transform 0.1s;
    margin-top: 4px;
    position: relative;
    overflow: hidden;
  }
  .btn-primary::before {
    content: '';
    position: absolute; inset: 0;
    background: linear-gradient(135deg, rgba(255,255,255,0.15), transparent);
  }
  .btn-primary:active { transform: scale(0.98); opacity: 0.85; }
  .btn-primary:disabled { opacity: 0.25; cursor: not-allowed; }

  /* ── Progress ── */
  .progress-section { display: none; margin-top: 4px; }
  .progress-section.visible { display: block; }

  /* Steps */
  .steps {
    display: flex;
    justify-content: space-between;
    margin-bottom: 18px;
    padding: 16px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 14px;
  }
  .step { display: flex; flex-direction: column; align-items: center; gap: 6px; flex: 1; }
  .step-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: var(--surface2);
    border: 1.5px solid var(--muted);
    transition: all 0.4s;
  }
  .step.active .step-dot {
    background: transparent;
    border-color: var(--cyan);
    box-shadow: 0 0 10px rgba(0,200,255,0.6);
    animation: pulse-cyan 1.4s ease-in-out infinite;
  }
  .step.done .step-dot {
    background: var(--cyan);
    border-color: var(--cyan);
    box-shadow: 0 0 6px rgba(0,200,255,0.4);
  }
  .step-name {
    font-size: 8px;
    font-weight: 600;
    letter-spacing: 0.08em;
    color: var(--muted);
    text-transform: uppercase;
    text-align: center;
  }
  .step.active .step-name { color: var(--cyan); }
  .step.done .step-name { color: var(--cyan-dim); }

  @keyframes pulse-cyan {
    0%,100% { box-shadow: 0 0 4px rgba(0,200,255,0.4); }
    50% { box-shadow: 0 0 14px rgba(0,200,255,0.8); }
  }

  /* Progress bar */
  .prog-header {
    display: flex;
    justify-content: space-between;
    font-size: 11px;
    margin-bottom: 8px;
  }
  .prog-msg { color: var(--white); }
  .prog-pct { color: var(--cyan); font-weight: 600; font-family: monospace; }

  .prog-bar {
    height: 3px;
    background: var(--surface2);
    border-radius: 2px;
    overflow: hidden;
    margin-bottom: 16px;
  }
  .prog-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--cyan-dim), var(--cyan));
    border-radius: 2px;
    width: 0%;
    transition: width 1s cubic-bezier(0.4,0,0.2,1);
    position: relative;
  }
  .prog-fill::after {
    content: '';
    position: absolute; right: 0; top: -2px;
    width: 6px; height: 7px;
    background: var(--cyan);
    border-radius: 50%;
    box-shadow: 0 0 8px var(--cyan);
  }

  /* Phase thumbnails */
  .thumbs {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 4px;
    margin-bottom: 14px;
  }
  .thumb {
    aspect-ratio: 1;
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 7px;
    font-weight: 600;
    color: var(--muted);
    overflow: hidden;
    transition: border-color 0.3s;
  }
  .thumb.done {
    border-color: rgba(0,200,255,0.3);
  }
  .thumb img { width: 100%; height: 100%; object-fit: cover; border-radius: 5px; }

  /* Log */
  .log-box {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 12px 14px;
    max-height: 160px;
    overflow-y: auto;
    font-size: 11px;
    font-family: monospace;
    line-height: 1.9;
    color: var(--muted);
  }
  .log-row { display: flex; gap: 8px; }
  .log-row .li { color: var(--cyan); flex-shrink: 0; }
  .log-row.current .lm { color: var(--white); }

  /* ── Result ── */
  .result-section { display: none; margin-top: 4px; }
  .result-section.visible { display: block; }

  .result-card {
    background: var(--surface);
    border: 1px solid rgba(255,179,71,0.2);
    border-radius: 16px;
    padding: 28px 20px;
    text-align: center;
    margin-bottom: 12px;
  }

  .result-icon { font-size: 48px; margin-bottom: 12px; }

  .result-title {
    font-family: 'Rajdhani', sans-serif;
    font-size: 28px;
    font-weight: 700;
    color: var(--gold);
    margin-bottom: 4px;
  }

  .result-punchline {
    font-size: 14px;
    color: var(--muted);
    font-style: italic;
    margin-bottom: 24px;
    line-height: 1.5;
  }

  .btn-download {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    width: 100%;
    padding: 17px;
    background: linear-gradient(135deg, var(--gold) 0%, #CC8820 100%);
    color: var(--bg);
    border: none;
    border-radius: 12px;
    font-family: 'Rajdhani', sans-serif;
    font-size: 16px;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    text-decoration: none;
    cursor: pointer;
    margin-bottom: 10px;
    transition: opacity 0.2s;
  }
  .btn-download:active { opacity: 0.8; }

  .btn-new {
    width: 100%;
    padding: 14px;
    background: transparent;
    border: 1px solid var(--border);
    border-radius: 12px;
    color: var(--muted);
    font-family: 'Inter', sans-serif;
    font-size: 13px;
    cursor: pointer;
    transition: border-color 0.2s, color 0.2s;
  }
  .btn-new:active { border-color: var(--cyan); color: var(--white); }

  /* PWA Install Banner */
  .pwa-banner {
    display: none;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 14px 16px;
    margin-bottom: 14px;
    flex-direction: row;
    align-items: center;
    gap: 12px;
  }
  .pwa-banner.show { display: flex; }
  .pwa-banner-text { flex: 1; font-size: 12px; color: var(--muted); line-height: 1.4; }
  .pwa-banner-text strong { color: var(--white); display: block; margin-bottom: 2px; }
  .pwa-btn {
    padding: 8px 14px;
    background: var(--cyan);
    color: var(--bg);
    border: none;
    border-radius: 8px;
    font-family: 'Rajdhani', sans-serif;
    font-weight: 700;
    font-size: 13px;
    cursor: pointer;
    white-space: nowrap;
  }

  /* Divider */
  .divider {
    display: flex; align-items: center; gap: 10px; margin: 14px 0;
  }
  .div-line { flex: 1; height: 1px; background: var(--border); }
  .div-txt { font-size: 9px; color: var(--muted); letter-spacing: 0.15em; text-transform: uppercase; }
</style>
</head>
<body>
<div class="container">

  <!-- PWA Install Banner -->
  <div class="pwa-banner" id="pwa-banner">
    <img src="/icon-192.png" style="width:40px;height:40px;border-radius:10px;" alt="">
    <div class="pwa-banner-text">
      <strong>Als App installieren</strong>
      Kein Chrome-Logo, echte App-Erfahrung
    </div>
    <button class="pwa-btn" id="pwa-install-btn">Installieren</button>
  </div>

  <!-- Header -->
  <div class="header">
    <div class="logo-wrap">
      <img src="/icon-192.png" class="logo-img" alt="Immo-Wizard">
      <div class="logo-text">
        <div class="logo-name">
          <span class="immo">IMMO</span><span class="dash">-</span><span class="wizard">WIZARD</span>
        </div>
        <div class="logo-tagline">We turn imagination into reality.</div>
      </div>
    </div>
    <h1 class="headline">
      Vom <span class="hl-cyan">ersten Stein</span><br>
      zum <span class="hl-gold">fertigen Video.</span>
    </h1>
    <p class="subline">1 Foto · KI Pipeline · ~87 Sek. Cinematic</p>
  </div>

  <!-- Form -->
  <div id="form-section">

    <div class="card">
      <div class="card-label">Immobilienfoto</div>
      <div class="upload-zone" id="upload-zone" onclick="document.getElementById('file-in').click()">
        <div class="upload-icon-wrap" id="up-icon">📷</div>
        <div class="upload-title">Foto hochladen</div>
        <div class="upload-hint">JPG oder PNG · Außenansicht · min. 1MP</div>
        <div class="upload-filename" id="file-name"></div>
      </div>
      <input type="file" id="file-in" accept="image/jpeg,image/png" onchange="handleFile(this)">
    </div>

    <div class="card">
      <div class="card-label">Projektdaten</div>
      <div class="field">
        <label>Name der Immobilie</label>
        <input type="text" id="prop-name" placeholder="z.B. Villa Marbella" oninput="checkReady()">
      </div>
      <div class="field">
        <label>Typ</label>
        <input type="text" id="prop-type" placeholder="z.B. Luxusvilla, Wohnanlage" oninput="checkReady()">
      </div>
    </div>

    <button class="btn-primary" id="start-btn" onclick="startPipeline()" disabled>
      ⚡ Pipeline starten
    </button>

  </div>

  <!-- Progress -->
  <div class="progress-section" id="prog-section">

    <div class="steps">
      <div class="step" id="s-prompts"><div class="step-dot"></div><div class="step-name">Prompts</div></div>
      <div class="step" id="s-images"><div class="step-dot"></div><div class="step-name">Bilder</div></div>
      <div class="step" id="s-videos"><div class="step-dot"></div><div class="step-name">Videos</div></div>
      <div class="step" id="s-dolly"><div class="step-dot"></div><div class="step-name">Dolly</div></div>
      <div class="step" id="s-cut"><div class="step-dot"></div><div class="step-name">Schnitt</div></div>
    </div>

    <div class="card" style="padding:16px;">
      <div class="prog-header">
        <span class="prog-msg" id="prog-msg">Starte...</span>
        <span class="prog-pct" id="prog-pct">0%</span>
      </div>
      <div class="prog-bar"><div class="prog-fill" id="prog-fill"></div></div>

      <div class="thumbs" id="thumbs">
        <div class="thumb" id="th-7">P7</div>
        <div class="thumb" id="th-6">P6</div>
        <div class="thumb" id="th-5">P5</div>
        <div class="thumb" id="th-4">P4</div>
        <div class="thumb" id="th-3">P3</div>
        <div class="thumb" id="th-2">P2</div>
        <div class="thumb" id="th-1">P1</div>
      </div>

      <div class="divider"><div class="div-line"></div><div class="div-txt">Live Log</div><div class="div-line"></div></div>
      <div class="log-box" id="log-box"></div>
    </div>

  </div>

  <!-- Result -->
  <div class="result-section" id="result-section">
    <div class="result-card">
      <div class="result-icon">🏆</div>
      <div class="result-title">Video fertig!</div>
      <div class="result-punchline" id="result-punchline"></div>
      <a class="btn-download" id="dl-link" href="#" download>
        ⬇ Video herunterladen
      </a>
    </div>
    <button class="btn-new" onclick="location.reload()">+ Neues Video erstellen</button>
  </div>

</div>

<script>
// ── PWA Install ──────────────────────────────────────────────
let deferredPrompt = null;
window.addEventListener('beforeinstallprompt', e => {
  e.preventDefault();
  deferredPrompt = e;
  document.getElementById('pwa-banner').classList.add('show');
});
document.getElementById('pwa-install-btn')?.addEventListener('click', async () => {
  if (!deferredPrompt) return;
  deferredPrompt.prompt();
  const { outcome } = await deferredPrompt.userChoice;
  deferredPrompt = null;
  document.getElementById('pwa-banner').classList.remove('show');
});

// ── Service Worker ────────────────────────────────────────────
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch(() => {});
}

// ── App Logic ────────────────────────────────────────────────
let jobId = null, poll = null, file = null;

function handleFile(inp) {
  file = inp.files[0];
  if (!file) return;
  document.getElementById('file-name').textContent = file.name;
  document.getElementById('upload-zone').classList.add('has-file');
  document.getElementById('up-icon').textContent = '✅';
  checkReady();
}

// Drag & Drop
const zone = document.getElementById('upload-zone');
zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag'); });
zone.addEventListener('dragleave', () => zone.classList.remove('drag'));
zone.addEventListener('drop', e => {
  e.preventDefault(); zone.classList.remove('drag');
  const f = e.dataTransfer.files[0];
  if (f?.type.startsWith('image/')) {
    file = f;
    document.getElementById('file-name').textContent = f.name;
    zone.classList.add('has-file');
    document.getElementById('up-icon').textContent = '✅';
    checkReady();
  }
});

function checkReady() {
  const ok = file && document.getElementById('prop-name').value.trim() && document.getElementById('prop-type').value.trim();
  document.getElementById('start-btn').disabled = !ok;
}

async function startPipeline() {
  const name = document.getElementById('prop-name').value.trim();
  const type = document.getElementById('prop-type').value.trim();

  document.getElementById('form-section').style.opacity = '0.3';
  document.getElementById('form-section').style.pointerEvents = 'none';
  document.getElementById('prog-section').classList.add('visible');
  setStep('prompts', 'active');

  const fd = new FormData();
  fd.append('image', file);
  fd.append('name', name);
  fd.append('type', type);

  try {
    const res = await fetch('/start', { method: 'POST', body: fd });
    const data = await res.json();
    if (!data.job_id) throw new Error(data.error || 'Server-Fehler');
    jobId = data.job_id;
    poll = setInterval(pollStatus, 3500);
  } catch(e) { addLog('❌', e.message); }
}

async function pollStatus() {
  if (!jobId) return;
  try {
    const res = await fetch('/status/' + jobId);
    const d = await res.json();
    updateUI(d);
    if (d.status === 'done' || d.status === 'error') clearInterval(poll);
  } catch(e) {}
}

function updateUI(d) {
  const pct = d.progress || 0;
  document.getElementById('prog-fill').style.width = pct + '%';
  document.getElementById('prog-pct').textContent = pct + '%';
  document.getElementById('prog-msg').textContent = d.message || '';

  if (d.log_entry) addLog(d.log_icon || '·', d.log_entry);

  if (pct >= 10) setStep('prompts','done');
  if (pct >= 15) setStep('images','active');
  if (pct >= 47) { setStep('images','done'); setStep('videos','active'); }
  if (pct >= 65) setStep('dolly','active');
  if (pct >= 82) { setStep('videos','done'); setStep('dolly','done'); setStep('cut','active'); }
  if (pct >= 98) setStep('cut','done');

  if (d.thumb && d.thumb_idx) {
    const el = document.getElementById('th-' + d.thumb_idx);
    if (el) { el.innerHTML = `<img src="${d.thumb}" alt="">`; el.classList.add('done'); }
  }

  if (d.status === 'done') {
    document.getElementById('prog-section').style.display = 'none';
    document.getElementById('result-section').classList.add('visible');
    document.getElementById('result-punchline').textContent = d.punchline || '';
    document.getElementById('dl-link').href = '/download/' + jobId;
  }
  if (d.status === 'error') addLog('❌', d.message);
}

function setStep(name, state) {
  const el = document.getElementById('s-' + name);
  if (el) el.className = 'step ' + state;
}

function addLog(icon, msg) {
  const box = document.getElementById('log-box');
  const row = document.createElement('div');
  row.className = 'log-row current';
  row.innerHTML = `<span class="li">${icon}</span><span class="lm">${msg}</span>`;
  box.appendChild(row);
  box.scrollTop = box.scrollHeight;
  box.querySelectorAll('.log-row').forEach((r,i,a) => { if(i < a.length-1) r.classList.remove('current'); });
}
</script>
</body>
</html>"""


# ── Service Worker (minimal, für PWA) ────────────────────────
SW_JS = """
self.addEventListener('fetch', e => {
  e.respondWith(fetch(e.request).catch(() => new Response('Offline', {status: 503})));
});
"""


# ════════════════════════════════════════════════════════════
#  ROUTES
# ════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/favicon.ico")
def favicon():
    return send_file("favicon.ico", mimetype="image/x-icon")

@app.route("/icon-192.png")
def icon192():
    return send_file("icon-192.png", mimetype="image/png")

@app.route("/icon-512.png")
def icon512():
    return send_file("icon-512.png", mimetype="image/png")

@app.route("/apple-touch-icon.png")
def apple_icon():
    return send_file("apple-touch-icon.png", mimetype="image/png")

@app.route("/manifest.json")
def manifest():
    return send_file("manifest.json", mimetype="application/manifest+json")

@app.route("/sw.js")
def service_worker():
    from flask import Response
    return Response(SW_JS, mimetype="application/javascript",
                   headers={"Service-Worker-Allowed": "/"})

@app.route("/start", methods=["POST"])
def start_job():
    image_file = request.files.get("image")
    prop_name  = request.form.get("name", "Wohnanlage")
    prop_type  = request.form.get("type", "Immobilie")
    if not image_file:
        return jsonify({"error": "Kein Bild"}), 400

    job_id  = str(uuid.uuid4())[:8]
    job_dir = WORKDIR / job_id
    job_dir.mkdir()

    img_path = job_dir / ("input" + Path(image_file.filename).suffix)
    image_file.save(str(img_path))

    jobs[job_id] = {"status":"running","progress":0,"message":"Gestartet",
                    "punchline":"","log_entry":"","log_icon":"·","thumb":None,"thumb_idx":None}

    threading.Thread(target=run_pipeline,
                    args=(job_id, str(img_path), prop_name, prop_type, job_dir),
                    daemon=True).start()
    return jsonify({"job_id": job_id})

@app.route("/status/<job_id>")
def job_status(job_id):
    return jsonify(jobs.get(job_id, {"status":"not_found"}))

@app.route("/download/<job_id>")
def download_video(job_id):
    path = jobs.get(job_id, {}).get("result_path")
    if not path or not Path(path).exists():
        return "Nicht gefunden", 404
    return send_file(path, as_attachment=True, download_name="immowizard_video.mp4")


# ════════════════════════════════════════════════════════════
#  PIPELINE
# ════════════════════════════════════════════════════════════

def upd(job_id, **kw):
    jobs[job_id].update(kw)

def run_pipeline(job_id, img_path, prop_name, prop_type, job_dir):
    img_dir = job_dir/"images"; vid_dir = job_dir/"videos"
    img_dir.mkdir(); vid_dir.mkdir()
    try:
        upd(job_id, progress=5, message="Claude generiert Prompts...", log_icon="🧠", log_entry="Analysiere Immobilienfoto...")
        prompts = gen_prompts(img_path, prop_name, prop_type)
        (job_dir/"prompts.json").write_text(json.dumps(prompts, indent=2, ensure_ascii=False))
        upd(job_id, progress=12, message="Prompts fertig", log_icon="✅",
            log_entry=f"Punchline: {prompts['punchlines'][0]}", punchline=prompts["punchlines"][0])

        images = {}
        img_jobs = [
            ("img1","phase_01.jpg",1,1), ("img2","phase_02.jpg",2,2),
            ("img3","phase_03.jpg",3,3), ("img4","phase_04.jpg",4,4),
            ("img5","phase_05.jpg",5,5), ("img6","phase_06.jpg",6,6),
            ("img7","phase_07.jpg",7,7), ("img_craftsman","handwerker.jpg",None,None),
        ]
        # Originalfoto als Haupt-Referenz — Haustyp, Stil, Perspektive
        original_ref_url = img_to_data_url(img_path, max_size=1024, quality=90)

        # Kette: jede Phase bekommt Original + vorheriges Phasenbild
        # → verhindert Drift zwischen Phasen
        last_phase_url = None  # wird nach jeder Phase aktualisiert

        for key, fname, tidx, pnum in img_jobs:
            pct = 15 + len(images)*4
            upd(job_id, progress=pct, message=f"Bild {len(images)+1}/8...",
                log_icon="🖼️", log_entry=f"Phase {pnum or 'Handwerker'}")

            if key == "img_craftsman":
                # Handwerker: kein Referenzbild — andere Szene
                ref = None
            elif last_phase_url:
                # Ab Phase 2: Original + vorheriges Phasenbild kombinieren
                # Nano Banana 2 bekommt beide als Referenz
                # → Haus identisch, nur Bauzustand ändert sich
                ref = last_phase_url  # vorheriges Bild dominiert Konsistenz
            else:
                # Phase 1 (img7, Wald): nur Original als Stilreferenz
                ref = original_ref_url

            path = gen_image(
                prompts["images"][key],
                img_dir/fname,
                reference_image_url=ref,
                original_ref_url=original_ref_url  # immer dabei für Stil-Ankerpunkt
            )
            images[key] = str(path)
            # Für nächste Phase: dieses Bild als Referenz merken
            if key != "img_craftsman":
                last_phase_url = img_to_data_url(str(path), max_size=1024, quality=90)
            if tidx:
                b64 = "data:image/jpeg;base64," + base64.b64encode(Path(path).read_bytes()).decode()
                upd(job_id, thumb=b64, thumb_idx=tidx)
            time.sleep(1)

        upd(job_id, progress=47, message="Bilder fertig", log_icon="✅", log_entry="8 Phasenbilder generiert")

        videos = {}
        p = prompts["videos"]; i = images
        for vk, s, e, fn, dur in [
            ("v1",i["img7"],i["img6"],"v01.mp4",10),
            ("v2",i["img6"],i["img5"],"v02.mp4",10),
            ("v3",i["img5"],i["img4"],"v03.mp4",10),
            ("v4",i["img4"],i["img3"],"v04.mp4",10),
        ]:
            upd(job_id, progress=50+len(videos)*3, message=f"Video {fn}...", log_icon="🎬", log_entry=fn)
            videos[vk] = str(gen_vid_transition(s, e, p[vk], vid_dir/fn, dur))
            time.sleep(2)

        # Dolly-Insert vorerst deaktiviert — wird nach Basis-Stabilität eingebaut
        upd(job_id, progress=70, message="Dolly-Insert übersprungen...", log_icon="⏭️", log_entry="Dolly-Insert deaktiviert")

        for vk, s, e, fn, dur in [
            ("v5",i["img3"],i["img2"],"v07.mp4",10),
            ("v6",i["img2"],i["img1"],"v08.mp4",10),
        ]:
            upd(job_id, progress=73+len(videos), message=f"Video {fn}...", log_icon="🎬", log_entry=fn)
            videos[vk] = str(gen_vid_transition(s,e,p[vk],vid_dir/fn,dur))
            time.sleep(2)

        upd(job_id, progress=80, message="Finale...", log_icon="🎬", log_entry="Crane Down — emotionaler Abschluss")
        videos["v7"] = str(gen_vid_i2v(i["img1"],p["v7"],vid_dir/"finale.mp4",10))

        upd(job_id, progress=85, message="ffmpeg Schnitt...", log_icon="✂️", log_entry="Alle Clips zusammenfügen")
        final = assemble(videos, prompts["punchlines"][0], job_dir)
        upd(job_id, status="done", progress=100, message="Fertig!", log_icon="🏆",
            log_entry="Video bereit zum Download", result_path=str(final))

    except Exception as e:
        upd(job_id, status="error", message=str(e), log_icon="❌", log_entry=f"Fehler: {e}")


def img_to_data_url(path, max_size=4096, quality=95):
    """
    Konvertiert Bild zu Data-URL für Higgsfield API.
    - max_size: max Kantenlänge in px (Standard 4096 = 4K)
    - quality: JPEG Qualität 0-100 (Standard 95 = sehr hoch)
    Originalbild wird NICHT verändert.
    """
    from PIL import Image as PILImage
    import io
    img = PILImage.open(path).convert("RGB")
    # Nur verkleinern wenn nötig (größer als 4K)
    if max(img.size) > max_size:
        img.thumbnail((max_size, max_size), PILImage.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/jpeg;base64,{b64}"

def gen_prompts(img_path, prop_name, prop_type):
    from PIL import Image as PILImage
    import io
    img = PILImage.open(img_path).convert("RGB")
    img.thumbnail((1500, 1500), PILImage.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    b64 = base64.b64encode(buf.getvalue()).decode()
    mime = "image/jpeg"

    # ── Bewährte Basis-Prompts (getestet, funktionieren mit Nano Banana 2) ──
    # Kurze Prompts + Referenzbild = beste Konsistenz
    BASE_IMAGES = {
        "img1": (
            f"High-angle aerial view from a drone or crane, camera positioned almost directly overhead. "
            f"A brand-new premium {prop_type} called {prop_name} with modern realistic design and clean geometry. "
            f"Golden hour lighting with warm sunlight, long soft shadows, dramatic colorful clouds — "
            f"shades of orange, pink, and soft purple. Palm trees integrated into the master plan. "
            f"Ocean visible on the distant horizon. Ultra-realistic, high detail, premium real estate aesthetic."
        ),
        "img2": "Create an image of this residential complex. Completed, clean, landscaping done. Same perspective.",
        "img3": (
            "Create an image of this residential complex during construction with concrete frames only. "
            "Concrete mixers around the perimeter, workers installing frames. "
            "Overcast afternoon sky. Same perspective."
        ),
        "img4": (
            "All complex while digging a pit with work equipment. "
            "No buildings, just earth and foundation slabs. Sunset with clouds. Same perspective."
        ),
        "img5": (
            "Empty lots with excavation pits before construction. "
            "Equipment on the sides of the pit closer to us. Sunny daytime. Same perspective."
        ),
        "img6": (
            "Leveled land without excavations. "
            "Equipment leveling the ground in frame. Sunny daytime. Same perspective."
        ),
        "img7": (
            "Dense natural forest on flat terrain, subtropical trees and palms, "
            "warm golden afternoon sunlight. No signs of human activity."
        ),
        "img_craftsman": (
            "Construction worker in orange safety vest and white helmet, "
            "actively laying concrete blocks on a rising wall. Close-up at eye level. "
            "Construction site in blurred background. Warm afternoon light. "
            "Photorealistic, cinematic depth of field, 16:9."
        ),
    }

    BASE_VIDEOS = {
        "v1": "Timelapse of forest clearing and land leveling using specialized machinery. Static camera.",
        "v2": "Timelapse of excavation work. Equipment arrives and leaves. Static camera.",
        "v3": "Timelapse of concrete foundation construction. Equipment arrives and leaves. Static camera.",
        "v4": "Timelapse of reinforced concrete frame construction. Cranes and machinery active. Equipment arrives and leaves. Static camera.",
        "v5": "Timelapse of building construction. Cranes and machinery active. Equipment arrives and leaves. Static camera.",
        "v6": "Timelapse of construction completion. Cranes and machinery active. Equipment arrives and leaves. Static camera.",
        "v7": "The camera moves down and forward smoothly and steadily. Golden hour light.",
    }

    # Claude passt nur an was wirklich zum konkreten Objekt passt
    res = claude.messages.create(
        model="claude-sonnet-4-6", max_tokens=1500,
        messages=[{"role":"user","content":[
            {"type":"image","source":{"type":"base64","media_type":mime,"data":b64}},
            {"type":"text","text":f"""Analysiere diese Immobilie ({prop_type}: {prop_name}).

Passe img1 minimal an: ersetze nur Haustyp-spezifische Details (Materialien, Besonderheiten).
Erstelle 3 emotionale Werbesprüche auf Deutsch, max 8 Wörter.

Antworte NUR mit JSON:
{{
  "img1_adjusted": "angepasster Prompt oder null",
  "punchlines": ["Spruch1", "Spruch2", "Spruch3"]
}}"""}
        ]}]
    )

    raw = res.content[0].text.strip()
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"): raw = raw[4:]

    try:
        data = json.loads(raw.strip())
        img1_adj = data.get("img1_adjusted")
        punchlines = data.get("punchlines", [
            f"Ihr Traum. Unser Werk.",
            "Vom ersten Stein bis zum Schlüssel.",
            "Wo Vision zur Wirklichkeit wird."
        ])
        if img1_adj and img1_adj != "null":
            BASE_IMAGES["img1"] = img1_adj
    except Exception:
        punchlines = [
            f"Ihr Traum. Unser Werk.",
            "Vom ersten Stein bis zum Schlüssel.",
            "Wo Vision zur Wirklichkeit wird."
        ]

    return {"images": BASE_IMAGES, "videos": BASE_VIDEOS, "punchlines": punchlines}


def gen_image(prompt, out_path, reference_image_url=None, original_ref_url=None):
    """
    Generiert ein Bild mit Nano Banana 2.

    Konsistenz-Strategie:
    - reference_image_url: vorheriges Phasenbild → räumliche + bauliche Kontinuität
    - original_ref_url: Originalfoto → Haustyp, Architekturstil, Perspektive als Anker

    Nur die explizit im Prompt beschriebenen Änderungen (Bauzustand) sind erlaubt.
    Alles andere — Haus, Kamera, Umgebung — bleibt identisch.
    """
    args = {
        "prompt": prompt,
        "resolution": "2K",
        "aspect_ratio": "16:9",
        "camera_fixed": True,
    }

    # Referenzbild-Strategie:
    # Phase 1: nur Original (Stilanker)
    # Phase 2+: vorheriges Phasenbild (Kontinuität) — Original ist implizit durch Kette verankert
    if reference_image_url:
        args["reference_image"] = reference_image_url
        args["reference_strength"] = 0.90  # Hoch — nur minimale Änderungen erlaubt
    elif original_ref_url:
        args["reference_image"] = original_ref_url
        args["reference_strength"] = 0.80

    r = higgsfield_client.subscribe("bytedance/seedream/v4/text-to-image", arguments=args)
    data = requests.get(r["images"][0]["url"], timeout=60).content
    Path(out_path).write_bytes(data)
    return out_path

def gen_vid_transition(s, e, prompt, out, dur=10):
    """
    Kling Start/End Frame via Higgsfield SDK.
    Probiert mehrere Model-Strings bis einer funktioniert.
    Basiert auf ComfyUI Doku: mode/duration/model_name Format.
    """
    # Kandidaten in Prioritätsreihenfolge — erster der funktioniert wird verwendet
    candidates = [
        # Kling O1 Start/End Frame (neuestes Modell)
        ("kling/v1/start-end-frame", {
            "start_image": img_to_data_url(s),
            "end_image": img_to_data_url(e),
            "prompt": prompt, "duration": dur, "cfg_scale": 0.5
        }),
        # Kling 2.5 Turbo Start/End Frame
        ("kling/v2.5/turbo/start-end-frame", {
            "start_image": img_to_data_url(s),
            "end_image": img_to_data_url(e),
            "prompt": prompt, "duration": dur, "cfg_scale": 0.5
        }),
        # Alternative Parameter-Namen (start_image_url)
        ("kling/v1/start-end-frame", {
            "start_image_url": img_to_data_url(s),
            "end_image_url": img_to_data_url(e),
            "prompt": prompt, "duration": dur, "cfg_scale": 0.5
        }),
        # image_tail Format (laut ComfyUI Doku)
        ("kling/v1.6/standard/image-to-video", {
            "image": img_to_data_url(s),
            "image_tail": img_to_data_url(e),
            "prompt": prompt, "duration": dur, "cfg_scale": 0.5
        }),
        # Kling O1 mit image_tail
        ("kling/o1/image-to-video", {
            "image": img_to_data_url(s),
            "image_tail": img_to_data_url(e),
            "prompt": prompt, "duration": dur, "cfg_scale": 0.5
        }),
    ]

    last_error = None
    for model_str, args in candidates:
        try:
            print(f"Versuche: {model_str}")
            r = higgsfield_client.subscribe(model_str, arguments=args)
            vid_url = r.get("videos", [{}])[0].get("url") or r.get("video", {}).get("url")
            if vid_url:
                Path(out).write_bytes(requests.get(vid_url, timeout=120).content)
                print(f"✅ Funktioniert: {model_str}")
                return out
        except Exception as e:
            last_error = f"{model_str}: {e}"
            print(f"❌ {last_error}")
            continue

    raise Exception(f"Kein Kling Start/End Frame Endpoint gefunden. Letzter Fehler: {last_error}")

def gen_vid_i2v(img, prompt, out, dur=10):
    r = higgsfield_client.subscribe("kling/v1.6/standard/image-to-video",
        arguments={"image_url":img_to_data_url(img),"prompt":prompt,"duration":dur,"cfg_scale":0.5})
    Path(out).write_bytes(requests.get(r["videos"][0]["url"],timeout=120).content)
    return out

def assemble(videos, punchline, job_dir):
    vd = job_dir/"videos"
    order = ["v1","v2","v3","v4","v5","v6","v7"]  # Dolly vorerst deaktiviert
    finale = Path(videos.get("v7",""))
    if finale.exists():
        ft = vd/"finale_text.mp4"
        safe = punchline.replace("'","\\'")
        subprocess.run(["ffmpeg","-y","-i",str(finale),"-vf",
            f"drawtext=text='{safe}':fontsize=48:fontcolor=white:font='Arial Bold':x=(w-text_w)/2:y=(h*0.78):enable='gte(t,6)':alpha='min((t-6)/1.5,1)'",
            "-codec:a","copy",str(ft)],capture_output=True,check=True)
        videos["v7"] = str(ft)
    clips = [videos[k] for k in order if k in videos and Path(videos[k]).exists()]
    cf = job_dir/"concat.txt"
    cf.write_text("\n".join(f"file '{Path(c).resolve()}'" for c in clips))
    final = job_dir/"IMMOWIZARD_video.mp4"
    subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(cf),
        "-c:v","libx264","-crf","18","-preset","fast",
        "-pix_fmt","yuv420p","-movflags","+faststart",str(final)],
        capture_output=True,check=True)
    return final


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

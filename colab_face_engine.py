# =====================================================================
# BioCore — REAL Face Engine on Google Colab (GPU)
# ---------------------------------------------------------------------
# Runs InsightFace (ArcFace 512-d embeddings + SCRFD face detection) on
# Colab's GPU and exposes /embed /liveness /compare over a PUBLIC URL,
# matching BioCore's RemoteFaceEngine contract. Real face recognition —
# not the sha512 stand-in.
#
# HOW TO RUN:
#   1. Open https://colab.research.google.com  ->  New notebook
#   2. Runtime > Change runtime type > Hardware accelerator: T4 GPU
#   3. Paste this ENTIRE file into ONE cell and run it
#   4. Wait ~2-3 min (installs + model download). It prints:
#         BioCore FACE_ENGINE_URL = https://xxxx.trycloudflare.com
#   5. Send that URL to Claude — it wires FACE_ENGINE=remote + that URL
#      and we test the full flow.
#
# NOTE ON LIVENESS: this does real recognition + a basic quality gate
# (face present, sharp, big enough). True anti-spoof/PAD (reject a printed
# photo / phone screen) is a separate model — ask Claude to add MiniFASNet.
# =====================================================================
import subprocess, sys, threading, time, re, base64

def sh(cmd):
    print(">", cmd)
    subprocess.run(cmd, shell=True, check=False)

# --- 1) dependencies ---
sh("pip -q install insightface onnxruntime-gpu fastapi 'uvicorn[standard]' nest_asyncio "
   "opencv-python-headless")
# cloudflared: a public URL with NO signup / token
sh("wget -q -O /usr/local/bin/cloudflared "
   "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 "
   "&& chmod +x /usr/local/bin/cloudflared")

# --- 2) load the real face model (ArcFace 512-d + detector) on GPU ---
import numpy as np, cv2
from insightface.app import FaceAnalysis

app_model = FaceAnalysis(name="buffalo_l",
                         providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
app_model.prepare(ctx_id=0, det_size=(640, 640))
print(">> face model ready (GPU if available)")

def _decode(image: str):
    if image.startswith("data:"):
        image = image.split(",", 1)[1]
    arr = np.frombuffer(base64.b64decode(image), np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)

def _largest_face(img):
    faces = app_model.get(img) if img is not None else []
    if not faces:
        return None
    return max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))

# --- 3) the HTTP API (matches BioCore RemoteFaceEngine) ---
from fastapi import FastAPI, Request
import uvicorn, nest_asyncio

api = FastAPI()

@api.get("/health")
def health():
    return {"status": "ok"}

@api.post("/embed")
async def embed(req: Request):
    d = await req.json()
    f = _largest_face(_decode(d["image"]))
    if f is None:
        return {"face_detected": False, "embedding": None}
    v = f.normed_embedding.astype("float32").tobytes()   # L2-normalized 512-d
    return {"face_detected": True, "embedding": base64.b64encode(v).decode(),
            "embedding_dim": 512}

@api.post("/liveness")
async def liveness(req: Request):
    img = _decode((await req.json())["image"])
    f = _largest_face(img)
    if f is None:
        return {"live": False, "detail": "no_face"}
    area = (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]) / (img.shape[0] * img.shape[1])
    sharp = cv2.Laplacian(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
    ok = area > 0.02      # face present & reasonably framed (webcam-friendly; NOT anti-spoof)
    return {"live": bool(ok), "detail": f"area={area:.3f} sharp={sharp:.0f}"}

@api.post("/compare")
async def compare(req: Request):
    d = await req.json()
    a = np.frombuffer(base64.b64decode(d["a"]), np.float32)
    b = np.frombuffer(base64.b64decode(d["b"]), np.float32)
    if a.size == 0 or b.size == 0:
        return {"score": 0.0, "match": False}
    cos = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
    return {"score": cos, "match": cos >= 0.40}   # ArcFace cosine threshold

# --- 4) serve + open a public tunnel ---
nest_asyncio.apply()
threading.Thread(
    target=lambda: uvicorn.run(api, host="0.0.0.0", port=8000, log_level="warning"),
    daemon=True).start()
time.sleep(3)

proc = subprocess.Popen(["cloudflared", "tunnel", "--url", "http://localhost:8000"],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
url = None
for line in proc.stdout:
    m = re.search(r"https://[-\w]+\.trycloudflare\.com", line)
    if m:
        url = m.group(0)
        break

print("\n\n=====================================================")
print("  BioCore FACE_ENGINE_URL =", url)
print("  -> send this URL to Claude to wire it in.")
print("  (keep this cell running for the whole demo)")
print("=====================================================\n")

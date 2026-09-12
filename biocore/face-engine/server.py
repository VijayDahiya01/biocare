"""BioCore real face engine — local, CPU (§15.1 RemoteFaceEngine contract).

The same engine as `prod/colab_face_engine.py` (InsightFace buffalo_l: SCRFD detection +
ArcFace 512-d embeddings), but run on THIS machine instead of a Colab GPU behind a
cloudflared tunnel. Tunnels are ephemeral — the committed FACE_ENGINE_URL had already gone
dead, which silently failed every identity verification — so this exists to be permanent.

Serves exactly what `app/adapters/face_engine/remote.py` expects:

    POST /embed     {image}          -> {embedding: <base64 float32>, face_detected}
    POST /liveness  {image}          -> {live: bool, detail: str}
    POST /compare   {a, b}           -> {score: float, match: bool}
    GET  /health                     -> {status, model}

RUN:
    C:/Users/DELL/bcface/Scripts/python.exe biocore/face-engine/server.py
    # first start downloads buffalo_l (~300MB) into ~/.insightface

WIRE IT (backend .env):
    FACE_ENGINE=remote
    FACE_ENGINE_URL=http://127.0.0.1:8099
    FACE_MODEL_VERSION=insightface-buffalo_l-arcface-512

LIVENESS IS NOT ANTI-SPOOF. /liveness checks a real face is present, big enough and sharp —
it will happily accept a printed photo or a phone screen. Real presentation-attack detection
is a separate model (MiniFASNet or equivalent) and is NOT wired here. Do not describe this as
spoof-proof to a customer.
"""
import base64

import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI, Request
from insightface.app import FaceAnalysis

PORT = 8099
MODEL = "buffalo_l"
MATCH_THRESHOLD = 0.40          # ArcFace cosine; keep in step with FACE_MATCH_THRESHOLD
MIN_FACE_AREA = 0.02            # fraction of frame the face must fill
MIN_SHARPNESS = 12.0            # Laplacian variance; rejects a badly out-of-focus capture

print(f"loading {MODEL} on CPU (first run downloads ~300MB)...")
engine = FaceAnalysis(name=MODEL, providers=["CPUExecutionProvider"])
engine.prepare(ctx_id=-1, det_size=(640, 640))          # ctx_id=-1 -> CPU
print(f">> {MODEL} ready")

api = FastAPI(title="BioCore face engine (local)")


def _decode(image: str):
    if not image:
        return None
    if image.startswith("data:"):
        image = image.split(",", 1)[1]
    try:
        raw = base64.b64decode(image)
    except Exception:
        return None
    arr = np.frombuffer(raw, np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def _largest_face(img):
    """The biggest face in frame — at a gate that is the person standing at it."""
    faces = engine.get(img) if img is not None else []
    if not faces:
        return None
    return max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))


@api.get("/health")
def health():
    return {"status": "ok", "model": MODEL, "provider": "CPUExecutionProvider"}


@api.post("/embed")
async def embed(req: Request):
    body = await req.json()
    face = _largest_face(_decode(body.get("image", "")))
    if face is None:
        return {"face_detected": False, "embedding": None}
    vector = face.normed_embedding.astype("float32").tobytes()   # L2-normalized 512-d
    return {"face_detected": True, "embedding": base64.b64encode(vector).decode(),
            "embedding_dim": 512}


@api.post("/liveness")
async def liveness(req: Request):
    img = _decode((await req.json()).get("image", ""))
    if img is None:
        return {"live": False, "detail": "undecodable_image"}
    face = _largest_face(img)
    if face is None:
        return {"live": False, "detail": "no_face"}
    area = ((face.bbox[2] - face.bbox[0]) * (face.bbox[3] - face.bbox[1])
            / (img.shape[0] * img.shape[1]))
    sharp = cv2.Laplacian(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
    ok = bool(area > MIN_FACE_AREA and sharp > MIN_SHARPNESS)
    # Quality gate only — a printed photo passes. See the module docstring.
    return {"live": ok, "detail": f"area={area:.3f} sharp={sharp:.0f}"}


@api.post("/compare")
async def compare(req: Request):
    body = await req.json()
    a = np.frombuffer(base64.b64decode(body.get("a") or ""), np.float32)
    b = np.frombuffer(base64.b64decode(body.get("b") or ""), np.float32)
    if a.size == 0 or b.size == 0 or a.size != b.size:
        return {"score": 0.0, "match": False}
    cos = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
    return {"score": cos, "match": bool(cos >= MATCH_THRESHOLD)}


if __name__ == "__main__":
    uvicorn.run(api, host="127.0.0.1", port=PORT, log_level="warning")

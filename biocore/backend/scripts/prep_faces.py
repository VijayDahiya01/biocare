"""Prepare real face images and prove the local engine does real recognition.

Two DIFFERENT people are cropped (with margin, so the detector has something to find) out of
the group photo InsightFace bundles for testing.

person A  - the largest face
person A2 - the SAME person, a different "capture": rescaled, brightened, slightly re-cropped.
            Byte-wise completely different, so matching A to A2 can only come from real face
            recognition, never from comparing bytes.
person B  - a different person from the same photo.
"""
import base64
import os

import cv2
import httpx
import insightface

ENGINE = "http://127.0.0.1:8099"
OUT = os.path.dirname(os.path.abspath(__file__)) + "/testfaces"
os.makedirs(OUT, exist_ok=True)
SRC = os.path.join(os.path.dirname(insightface.__file__), "data", "images")

group = cv2.imread(os.path.join(SRC, "t1.jpg"))
det = insightface.app.FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
det.prepare(ctx_id=-1, det_size=(640, 640))
faces = sorted(det.get(group), key=lambda f: -((f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1])))
print(f"faces found in the group photo: {len(faces)}")


def crop(face, margin=0.7, size=512):
    x1, y1, x2, y2 = [int(v) for v in face.bbox]
    mx, my = int((x2 - x1) * margin), int((y2 - y1) * margin)
    c = group[max(0, y1 - my):min(group.shape[0], y2 + my),
              max(0, x1 - mx):min(group.shape[1], x2 + mx)]
    return cv2.resize(c, (size, size))


a, b = crop(faces[0]), crop(faces[1])
h, w = a.shape[:2]
a2 = a[int(h * 0.05):int(h * 0.95), int(w * 0.05):int(w * 0.95)]
a2 = cv2.convertScaleAbs(cv2.resize(a2, (420, 420)), alpha=1.12, beta=18)

for name, img in (("personA", a), ("personA2", a2), ("personB", b)):
    path = f"{OUT}/{name}.jpg"
    cv2.imwrite(path, img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    raw = open(path, "rb").read()
    open(f"{OUT}/{name}.b64", "w").write("data:image/jpeg;base64," + base64.b64encode(raw).decode())
    print(f"  {name}: {img.shape} -> {len(raw)} bytes")

c = httpx.Client(timeout=120.0)


def b64(name):
    return open(f"{OUT}/{name}.b64").read()


print("\n--- engine: liveness / quality gate ---")
for name in ("personA", "personA2", "personB"):
    r = c.post(f"{ENGINE}/liveness", json={"image": b64(name)}).json()
    print(f"  {name}: live={r['live']}  {r['detail']}")
r = c.post(f"{ENGINE}/liveness", json={"image": base64.b64encode(b"not an image").decode()}).json()
print(f"  garbage:  live={r['live']}  {r['detail']}")

print("\n--- engine: embeddings ---")
emb = {}
for name in ("personA", "personA2", "personB"):
    r = c.post(f"{ENGINE}/embed", json={"image": b64(name)}).json()
    emb[name] = r.get("embedding")
    print(f"  {name}: face_detected={r['face_detected']} dim={r.get('embedding_dim')}")

print("\n--- engine: 1:1 comparison (the real test) ---")
same = c.post(f"{ENGINE}/compare", json={"a": emb["personA"], "b": emb["personA2"]}).json()
diff = c.post(f"{ENGINE}/compare", json={"a": emb["personA"], "b": emb["personB"]}).json()
print(f"  A vs A2 (same person, different capture): score={same['score']:.3f} match={same['match']}")
print(f"  A vs B  (different people):               score={diff['score']:.3f} match={diff['match']}")

ok = bool(same["match"]) and not bool(diff["match"])
print(f"\n=== REAL RECOGNITION: {'WORKING' if ok else 'BROKEN'} ===")
raise SystemExit(0 if ok else 1)

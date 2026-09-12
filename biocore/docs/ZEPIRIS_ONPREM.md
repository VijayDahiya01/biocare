# ZepIris — On-Premise Setup Runbook

How to run the real ZepIris face engine locally and on-prem, with **no data leaving your
infrastructure** and **no GPU**.

Verified against `github.com/zepto-labs/zepiris` @ `main` / release `release-v1.0.0`
on 2026-08-17 by reading the upstream source. Where this contradicts
`_extracted/7_ZepIris_VERIFIED.txt`, **this file is correct** — see
[§8 Corrections](#8-corrections-to-existing-repo-docs).

---

## 1. The two answers up front

### No GPU. Zero VRAM.

Not "optional" — the shipped code physically cannot use one:

| Evidence | Where |
|---|---|
| `providers=["CPUExecutionProvider"]` hard-coded for detection + embedding | `zepiris/ml_inference/face_embedding.py` → `load_model()` |
| Docstring: *"device: Inference device (for now only `cpu` is supported)"* | same file, `__init__` |
| torch/torchvision pinned to the **CPU-only** wheel index | `pyproject.toml` → `[[tool.poetry.source]] url = ".../whl/cpu"` |

Setting `ML_SERVICE_ML_DEVICE=cuda:0` on the shipped build raises
*"Torch not compiled with CUDA enabled."*

Rebuilding with CUDA wheels would accelerate only the three small IQA classifiers
(~250 MB VRAM). The embedding model — the actual cost — stays on CPU regardless.
**Not worth doing.** Spend on CPU cores instead.

### No data goes to Zepto. Ever.

ZepIris is a self-hosted microservice. It writes vectors to **your** Milvus and images to
**your** MinIO. No telemetry, no vendor API, no callback.

There is exactly **one** outbound call in the entire pipeline:

```python
# zepiris/ml_inference/face_embedding.py
def _download_auraface(self):
    snapshot_download("fal/AuraFace-v1", local_dir="models/auraface")
```

It hits **huggingface.co** (not Zepto), fires once at first model load, and *downloads*
weights — it uploads nothing. The three IQA models load from local `.pth` files with no
network at all. [§4](#4-air-gap-close-the-last-outbound-call) closes even this.

---

## 2. Licensing — pick the right face model

`ML_SERVICE_FACE_MODEL` accepts two values, and **the choice is a commercial-licensing
decision**, not a quality tradeoff. From upstream `.env.example`:

| Value | Weights | License | Use for BioCore? |
|---|---|---|---|
| `auraface` *(default)* | `fal/AuraFace-v1` | **Apache-2.0** — verified via HF API | ✅ **Yes** |
| `buffalo_l` | InsightFace buffalo_l | **Non-commercial research only.** Commercial use needs a separate license from `recognition-oss-pack@insightface.ai` | ❌ **No** |

> **Keep `ML_SERVICE_FACE_MODEL=auraface`.** Do not switch to `buffalo_l` in any
> environment that touches a paying customer. The default is already correct — just
> don't override it.

Both produce 512-d embeddings, so the Milvus schema is identical either way. AuraFace
resolves to `glintr100.onnx` (ArcFace R100) for recognition + `scrfd_10g_bnkps.onnx` for
detection.

---

## 3. Hardware

CPU is the only throughput lever.

| | Recommended (on-prem server) | Minimum |
|---|---|---|
| CPU | 16 cores, AVX-512 (Xeon Silver / EPYC) | 8 cores with AVX2 |
| RAM | 32 GB | 16 GB |
| Disk | 250 GB NVMe | 100 GB SSD |
| GPU | **none** | — |

Throughput: AuraFace uses **R100** (not R50), so budget ~400–800 ms per request
single-threaded for detect + embed. Expect roughly:

| Faces/sec | Cores |
|---|---|
| ~2–5 | 8 |
| ~5–10 | 16 |
| more | scale `zepiris-ml` replicas horizontally |

Milvus storage is cheap: FLAT/COSINE at 512-d float32 = **2 KB per face**
(100k faces ≈ 200 MB). MinIO holding source images is what actually grows, ~100 KB/face.

> **⚠️ This dev laptop (i5-1145G7, 15.4 GB RAM, 6.1 GB free disk) cannot host the full
> stack.** 13 containers plus volumes needs ~60 GB. Disk is the wall, not the GPU.
> Use [§5 Path A](#5-path-a-run-the-ml-service-natively-dev-laptop) here, and
> [§6 Path B](#6-path-b-full-stack-on-the-on-prem-server) on the real server.

---

## 4. Air-gap: close the last outbound call

Do this **once, while you have internet**, then forbid the network forever.

```bash
# from the zepiris repo root
poetry run python -c "from huggingface_hub import snapshot_download; \
snapshot_download('fal/AuraFace-v1', local_dir='models/auraface')"
```

Downloads ~600 MB. Then set:

```
HF_HUB_OFFLINE=1
```

InsightFace is constructed with `name="auraface", root="."`, so it resolves to
`./models/auraface/` — exactly where that command writes. After this, **zero egress**.

For Docker, do the same as a build-time `RUN` step in `ml_inference.Dockerfile` (build has
network, runtime does not) and add `ENV HF_HUB_OFFLINE=1`.

The three IQA classifiers need nothing — `.env.example` ships them as
`ML_SERVICE_*_MODEL_SOURCE=local` pointing at committed `.pth` files.

---

## 5. Path A — run the ML service natively (dev laptop)

The ML service needs **no Milvus, no MinIO, no etcd**. This is the fastest way to prove
the models work, and it fits in your remaining disk (~2.5 GB vs ~5–6 GB peak for a
Docker build).

### 5.1 Clone

The published images are **not pullable** — `ghcr.io/zepto-labs/zepiris:1.0.0` and
`:zepiris-ml:1.0.0` both return **HTTP 403** anonymously. The repo is public, so build
from source:

```bash
cd C:/Users/DELL/Desktop/wxwqxqwxw
git clone https://github.com/zepto-labs/zepiris.git
cd zepiris
```

Weights are **committed in the repo** at `models/` — no release download needed:

| File | Size |
|---|---|
| `models/blur_model.pth` | 44.8 MB |
| `models/spoof_model.pth` | 50.8 MB |
| `models/nsfw_model.pth` | 9.1 MB |

### 5.2 Config

```bash
cp .env.example .env
```

Then edit `.env` — the shipped paths are **container-absolute** and must be made relative
for a native run:

```diff
-ML_SERVICE_NSFW_LOCAL_MODEL_PATH=/app/models/nsfw_model.pth
+ML_SERVICE_NSFW_LOCAL_MODEL_PATH=models/nsfw_model.pth
-ML_SERVICE_SPOOF_LOCAL_MODEL_PATH=/app/models/spoof_model.pth
+ML_SERVICE_SPOOF_LOCAL_MODEL_PATH=models/spoof_model.pth
-ML_SERVICE_BLUR_LOCAL_MODEL_PATH=/app/models/blur_model.pth
+ML_SERVICE_BLUR_LOCAL_MODEL_PATH=models/blur_model.pth
```

Leave `ML_SERVICE_FACE_MODEL=auraface` and `ML_SERVICE_ML_DEVICE=cpu` alone.

### 5.3 Install and run

Requires Python 3.10–3.14 (`requires-python = ">=3.10,<3.15"`).

```bash
pip install poetry
poetry install --extras ml     # pulls the CPU torch wheel, ~2 GB
poetry run zepiris-ml-inference-api
```

Run from the repo root — AuraFace resolves `models/auraface` relative to CWD.

First start takes **30–90 s** while the models load. Then:

- Live route list: **http://localhost:8001/docs**
- Health: `curl http://localhost:8001/healthz` → `{"status":"ok"}`

### 5.4 Smoke test

All ML endpoints take **JSON** `{"image_b64": "..."}` — *not* multipart, and the field is
`image_b64`, not `image`.

```bash
poetry run python - <<'PY'
import base64, json, httpx
b64 = base64.b64encode(open("face.jpg","rb").read()).decode()
for path in ["/v1/iqa/assess", "/v1/face/embed"]:
    r = httpx.post(f"http://localhost:8001{path}", json={"image_b64": b64}, timeout=60)
    body = r.json()
    if path.endswith("embed"):
        body["embedding"] = f"<{len(body.get('embedding', []))} floats>"
    print(path, r.status_code, json.dumps(body, indent=2)[:400])
PY
```

Expect `face_detected: true` and `embedding_dim: 512` from `/v1/face/embed`.

PowerShell equivalent for a single call:

```powershell
$b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes("face.jpg"))
Invoke-RestMethod -Method Post -Uri "http://localhost:8001/v1/iqa/assess" `
  -ContentType "application/json" -Body (@{ image_b64 = $b64 } | ConvertTo-Json)
```

---

## 6. Path B — full stack on the on-prem server

Only once Path A works.

### 6.1 Build both images locally

`.env` **must exist before you build** — `ml_inference.Dockerfile` does
`COPY pyproject.toml poetry.lock poetry.toml README.md .env ./` and the build fails
without it.

```bash
cd zepiris
cp .env.example .env
docker build -f Dockerfile              -t zepiris-main:1.0.0 .
docker build -f ml_inference.Dockerfile -t zepiris-ml:1.0.0   .
```

### 6.2 Patch `biocore/docker-compose.yml`

```yaml
  zepiris-main:
    image: zepiris-main:1.0.0        # was ghcr.io/zepto-labs/zepiris:1.0.0  (403)
    environment:
      - ZEPIRIS_API_PORT=8000
      - ZEPIRIS_MINIO_ENDPOINT=minio:9000
      - ZEPIRIS_MINIO_ACCESS_KEY=${MINIO_KEY}
      - ZEPIRIS_MINIO_SECRET_KEY=${MINIO_SECRET}
      - ZEPIRIS_MINIO_BUCKET=zepiris
      - ZEPIRIS_MINIO_SECURE=false
      - ZEPIRIS_MILVUS_HOST=milvus
      - ZEPIRIS_MILVUS_PORT=19530
      - ZEPIRIS_MILVUS_COLLECTION=zepiris_faces
      - ZEPIRIS_MILVUS_EMBEDDING_DIM=512
      - ZEPIRIS_MILVUS_SEARCH_THRESHOLD=0.5
      - ZEPIRIS_ML_INFERENCE_SERVICE_URL=http://zepiris-ml:8001

  zepiris-ml:
    image: zepiris-ml:1.0.0          # was ghcr.io/zepto-labs/zepiris-ml:1.0.0  (403)
    environment:
      - ML_SERVICE_PORT=8001
      - ML_SERVICE_ML_DEVICE=cpu
      - ML_SERVICE_FACE_MODEL=auraface
      - HF_HUB_OFFLINE=1
    # ⚠️ DO NOT mount ./infra/models here — see §8.3
```

`ZEPIRIS_MINIO_ACCESS_KEY` / `_SECRET_KEY` are **missing from the current compose file**
and are required for ZepIris to reach MinIO — the existing block only sets the endpoint.

### 6.3 Point BioCore at it

In `biocore/backend/.env`:

```
FAKE_ZEPIRIS=false
ZEPIRIS_URL=http://zepiris-main:8000
```

The adapter at `biocore/backend/app/adapters/zepiris/client.py` is already written against
the real wire format (multipart + `tenant` form field). Verify with the existing script:

```bash
python scripts/verify_zepiris.py    # insert → search → get → delete
```

Note the separate legacy path: `FACE_ENGINE=remote` + `FACE_ENGINE_URL` in `.env` currently
points at a **dead** cloudflared tunnel (`electron-firewire-action-hampshire.trycloudflare.com`
— confirmed unreachable). That adapter (`face_engine/remote.py`) expects a *different*
contract (`/embed`, `/liveness`, `/compare`) and will not talk to ZepIris directly. Either
retire it or put a shim in front.

---

## 7. Verified API reference

### 7.1 ML inference service — port 8001

Read from `zepiris/ml_inference/routes.py`. Request body for **all** POSTs:
`{"image_b64": "<base64>"}`.

| Method | Path | Returns |
|---|---|---|
| GET | `/healthz` | `{"status":"ok"}` |
| POST | `/v1/face/embed` | `FaceEmbeddingResult` — `face_detected`, `embedding` (512 floats, L2-normalized), `embedding_dim` |
| POST | `/v1/iqa/assess` | Combined NSFW + spoof + blur, run in parallel |
| POST | `/v1/iqa/nsfw_check` | `NSFWDetectionResult` |
| POST | `/v1/iqa/spoof_check` | `SpoofDetectionResult` |
| POST | `/v1/iqa/blur_check` | `BlurDetectionResult` |

Error codes on bad input: `400` with detail `invalid_base64`, `empty_image_data`,
`invalid_image_format`, or `failed_to_decode_image`.

### 7.2 Main API — port 8000

Per `_extracted/7_ZepIris_VERIFIED.txt` and the BioCore adapter. **Multipart/form-data**
with a real file upload plus a `tenant` form field:

| Method | Path | Notes |
|---|---|---|
| POST | `/v1/faces/insert` | `422` on IQA failure / no face, `409` on duplicate id |
| POST | `/v1/faces/upsert` | re-enrollment |
| POST | `/v1/faces/search` | `?top_k=5&threshold=…` · returns **200 with empty `matches[]`** on a bad image — does not raise |
| DELETE | `/v1/faces/delete` | `?id=…` |
| GET | `/v1/faces/get/{id}` | metadata |
| GET | `/healthz`, `/readyz` | liveness / readiness |

Note the plural: ML service is `/v1/face/…`, main API is `/v1/faces/…`.

### 7.3 Milvus schema

One collection, `zepiris_faces`, with `tenant` as a **column** (not per-tenant
collections). Index FLAT, metric COSINE.

```
face_id     VARCHAR(128)      primary key
tenant      VARCHAR(256)
object_key  VARCHAR(512)      MinIO path
embedding   FLOAT_VECTOR(512)
```

---

## 8. Corrections to existing repo docs

Four things in this repo are wrong and will cost you time.

### 8.1 `_extracted/7_ZepIris_VERIFIED.txt` has the wrong ML route paths

It lists `/v1/spoof` and `/v1/blur`. The real paths are namespaced:
`/v1/iqa/spoof_check`, `/v1/iqa/blur_check`, `/v1/iqa/nsfw_check`, `/v1/iqa/assess`,
`/v1/face/embed`. Use [§7.1](#71-ml-inference-service--port-8001).

### 8.2 `biocore/infra/models/README.md` is wrong twice

- It says to obtain weights "from the ZepIris release." They are **committed in the repo**
  at `models/`.
- It names `nudity_model.pth`. The real filename is **`nsfw_model.pth`**.

### 8.3 The models volume mount is a live bug

`biocore/docker-compose.yml:87` mounts `./infra/models:/app/models:ro`, but
`ml_inference.Dockerfile` already does `COPY models/ /app/models/`. Since
`biocore/infra/models/` contains **only a README**, that read-only mount would **mask the
baked-in weights** → all ML endpoints return `503` and `/readyz` never passes.
**Delete the mount** when building from source.

### 8.4 MinIO credentials are missing from the ZepIris service block

See [§6.2](#62-patch-biocoredocker-composeyml).

---

## 9. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `503` from an ML endpoint | weight file not found at the configured path | check `ML_SERVICE_*_LOCAL_MODEL_PATH`; native runs need relative paths ([§5.2](#52-config)) |
| `/readyz` never passes | usually 8.3 — empty volume masking the weights | remove the `./infra/models` mount |
| `Torch not compiled with CUDA enabled` | you set `ML_SERVICE_ML_DEVICE=cuda:0` | set it back to `cpu`; see [§1](#no-gpu-zero-vram) |
| `denied` / `403` on `docker compose pull` | ghcr packages are private | build from source ([§6.1](#61-build-both-images-locally)) |
| Docker build fails on `COPY … .env` | no `.env` in the repo root | `cp .env.example .env` before building |
| Hangs ~60 s on first request, then works | lazy model load — this is normal | raise healthcheck `start_period` (compose already uses 90 s) |
| Network call attempted in the air-gapped site | AuraFace snapshot not pre-baked | [§4](#4-air-gap-close-the-last-outbound-call) |
| `search` returns `200` with no matches instead of an error | documented upstream behaviour, not a bug | handle empty `matches[]` in the caller |

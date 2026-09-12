"""Reference PPE model server — implements the contract the BioCore PPE adapter
expects (`POST /detect` -> {"detections": {gear: present?}}).

This is NOT a trained model; it returns a configurable response so the PPE
enforcement path can be exercised end-to-end without the real model. A real
deployment replaces this with an inference service that returns the same shape.

A dev-only `POST /_simulate` flips what `/detect` returns (helmet/vest present).
Run:  uvicorn app:app --port 8002   (or `python app.py`)
"""
import os

from fastapi import FastAPI

app = FastAPI(title="BioCore PPE (reference)")

# default: all gear present
_STATE: dict[str, bool] = {"helmet": True, "vest": True}
if os.getenv("PPE_DEFAULT_MISSING"):
    for item in os.getenv("PPE_DEFAULT_MISSING").split(","):
        _STATE[item.strip()] = False


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/detect")
def detect(body: dict | None = None):
    # a real model would read body["image_b64"]; the reference returns _STATE.
    return {"detections": dict(_STATE)}


@app.post("/_simulate")
def simulate(detections: dict):
    """Dev-only: set what /detect returns, e.g. {"helmet": true, "vest": false}."""
    _STATE.clear()
    _STATE.update({k: bool(v) for k, v in detections.items()})
    return {"detections": dict(_STATE)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PPE_PORT", "8002")))

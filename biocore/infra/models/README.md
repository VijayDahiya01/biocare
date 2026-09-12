# ZepIris ML model weights

**Nothing needs to go in this directory.** It is intentionally empty except for this file.

The weights ship **committed inside the ZepIris repo** at `models/`, and
`ml_inference.Dockerfile` bakes them into the image with `COPY models/ /app/models/`:

| File (upstream `models/`) | Size |
|---|---|
| `blur_model.pth` | 44.8 MB |
| `spoof_model.pth` | 50.8 MB |
| `nsfw_model.pth` | 9.1 MB |

There is no separate release download to fetch, and the third file is `nsfw_model.pth` —
**not** `nudity_model.pth`.

## Do not mount this directory into the container

`docker-compose.yml` used to bind-mount `./infra/models:/app/models:ro`. Because this
directory holds only a README, that read-only mount **masked the baked-in weights** — every
ML endpoint returned `503` and `/readyz` never passed. The mount has been removed; don't
add it back.

If you ever need to override a weight file, mount the single file, not the directory:

```yaml
volumes:
  - ./infra/models/spoof_model.pth:/app/models/spoof_model.pth:ro
```

## AuraFace

The face detection + embedding weights (`fal/AuraFace-v1`, Apache-2.0) are **not** in this
repo. They are pulled from HuggingFace on first model load, and should be pre-baked at
build time for air-gapped sites so `HF_HUB_OFFLINE=1` can be set at runtime.

Full setup, air-gap procedure, and licensing constraints: **`docs/ZEPIRIS_ONPREM.md`**.

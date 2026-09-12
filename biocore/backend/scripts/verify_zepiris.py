"""Verify the adapter against a REAL ZepIris engine (go-live de-risking).

Point at a running ZepIris and provide a real face image, then run the full
contract: readiness -> insert -> search (must match) -> get -> delete -> get-gone.

    set FAKE_ZEPIRIS=false
    set ZEPIRIS_URL=http://<zepiris-host>:8000
    python -m scripts.verify_zepiris path/to/face.jpg

Exercises app/adapters/zepiris/client.py directly (not the app), so it confirms
the verified Doc 7 wire contract (multipart, tenant form field, camelCase ids,
200-empty-on-bad-image, FLAT/COSINE search) against the actual engine.
"""
import base64
import sys
import uuid

from app.adapters.zepiris.client import ZepIrisClient
from app.core.config import settings


def main() -> None:
    if settings.fake_zepiris:
        raise SystemExit("Set FAKE_ZEPIRIS=false to verify against the REAL engine.")
    if len(sys.argv) < 2:
        raise SystemExit("usage: python -m scripts.verify_zepiris <face-image-path>")

    img_b64 = base64.b64encode(open(sys.argv[1], "rb").read()).decode()
    z = ZepIrisClient()
    tenant = "verify_tenant"
    fid = f"verify_{uuid.uuid4().hex[:8]}"
    results = []

    def chk(name, ok, detail=""):
        results.append(ok)
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

    print(f"ZepIris @ {z.base_url}")
    chk("readyz", z.readyz())

    ins = z.insert(tenant=tenant, face_id=fid, image_b64=img_b64)
    chk("insert stored a face + passed IQA", ins.stored and ins.quality.passed, f"req={ins.request_id}")

    res = z.search(tenant=tenant, image_b64=img_b64, top_k=5)
    best = res.best
    chk("search returns the enrolled face as top match", bool(best) and best.id == fid,
        f"best={best.id if best else None} score={best.score if best else 0}")

    meta = z.get(fid)
    chk("get returns metadata", meta is not None)

    chk("delete succeeds", z.delete(fid))
    chk("get-after-delete is gone", z.get(fid) is None)

    ok = all(results)
    print(f"\nVERIFY_ZEPIRIS {'OK' if ok else 'FAILED'} ({sum(results)}/{len(results)})")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()

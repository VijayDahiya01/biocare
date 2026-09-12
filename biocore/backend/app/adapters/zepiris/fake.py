"""In-process fake ZepIris for local testing (FAKE_ZEPIRIS=true).

Lets the entire face pipeline (enroll, kiosk search, blacklist, erasure) run with
NO Milvus, MinIO, ML service, or model weights — so the app can be clicked through
end-to-end with only Postgres.

Dev behaviour (documented limitation): a search returns the MOST RECENTLY enrolled
face for that tenant with a high score. So to test a check-in as a given person,
enroll/that person last. Quality always passes; spoof is always false.
"""
from __future__ import annotations

import uuid

from app.adapters.zepiris.client import (
    EnrollResult,
    ImageQuality,
    Match,
    SearchResult,
)

# tenant -> ordered list of live face ids (most recent last)
_STORE: dict[str, list[str]] = {}


def _pass() -> ImageQuality:
    return ImageQuality(passed=True, blur_ok=True, spoof=False, safe=True,
                        raw={"passed": True, "fake": True})


class FakeZepIris:
    def insert(self, tenant: str, face_id: str, image_b64: str) -> EnrollResult:
        ids = _STORE.setdefault(tenant, [])
        if face_id in ids:
            ids.remove(face_id)
        ids.append(face_id)
        return EnrollResult(request_id=str(uuid.uuid4()), face_id=face_id,
                            stored=True, quality=_pass())

    def upsert(self, tenant: str, face_id: str, image_b64: str) -> EnrollResult:
        return self.insert(tenant, face_id, image_b64)

    def search(self, tenant: str, image_b64: str, top_k: int = 5,
               threshold: float | None = None) -> SearchResult:
        ids = _STORE.get(tenant, [])
        matches = [Match(id=ids[-1], score=0.99)] if ids else []
        return SearchResult(request_id=str(uuid.uuid4()), quality=_pass(), matches=matches)

    def delete(self, face_id: str) -> bool:
        for ids in _STORE.values():
            if face_id in ids:
                ids.remove(face_id)
                return True
        return False

    def get(self, face_id: str) -> dict | None:
        for tenant, ids in _STORE.items():
            if face_id in ids:
                return {"face_id": face_id, "tenant": tenant, "object_key": f"fake/{face_id}"}
        return None

    def healthz(self) -> bool:
        return True

    def readyz(self) -> bool:
        return True

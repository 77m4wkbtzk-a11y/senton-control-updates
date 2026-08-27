from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


RESTRICTED_SIGN_TERMS = {
    "toilet",
    "toilets",
    "restroom",
    "restrooms",
    "bathroom",
    "bathrooms",
    "changing room",
    "change room",
    "changeroom",
    "shower",
    "showers",
}


@dataclass(frozen=True)
class PrivacyEvent:
    reason: str
    detected_text: str
    camera_name: str
    timestamp_utc: str
    evidence_path: Optional[str]


class PrivacyGuard:
    """Privacy lock state machine for Senton Control v1.2.9.

    This module does not perform computer vision by itself. A camera/OCR layer can
    feed sign text or a confirmed restricted-area event into it. The guard then
    enforces a recoverable camera lock and records only non-sensitive metadata.
    """

    def __init__(self, camera_name: str = "Main Camera"):
        self.camera_name = camera_name
        self.locked = False
        self.last_event: Optional[PrivacyEvent] = None

    def sign_is_restricted(self, detected_text: str) -> bool:
        text = " ".join((detected_text or "").lower().split())
        return any(term in text for term in RESTRICTED_SIGN_TERMS)

    def trigger_from_sign(self, detected_text: str, exterior_evidence_path: Optional[str] = None) -> PrivacyEvent:
        if not self.sign_is_restricted(detected_text):
            raise ValueError("Detected sign text is not a configured restricted privacy-zone indicator")
        return self._lock("Restricted privacy-zone sign detected", detected_text, exterior_evidence_path)

    def trigger_private_area_view(self, exterior_evidence_path: Optional[str] = None) -> PrivacyEvent:
        return self._lock("Restricted privacy area entered/viewed", "", exterior_evidence_path)

    def _lock(self, reason: str, detected_text: str, exterior_evidence_path: Optional[str]) -> PrivacyEvent:
        evidence = None
        if exterior_evidence_path:
            p = Path(exterior_evidence_path)
            # Evidence must have been captured before entry. This layer only records
            # the supplied exterior path; capture/blur validation belongs upstream.
            evidence = str(p)
        self.locked = True
        self.last_event = PrivacyEvent(
            reason=reason,
            detected_text=detected_text,
            camera_name=self.camera_name,
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            evidence_path=evidence,
        )
        return self.last_event

    def authorise_phone_unlock(self, approved: bool) -> bool:
        """Accept only an approval result from Senton Link; never a PIN value."""
        if not approved:
            return False
        self.locked = False
        return True

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Optional


@dataclass
class VehicleOfInterest:
    rego: str
    make_model: str = ""
    colour: str = ""
    year: str = ""


@dataclass
class MissingPersonCase:
    case_id: str
    name: str
    age: Optional[int]
    last_seen: str
    last_known_area: str
    clothing: str = ""
    notes: str = ""
    bulletin_source: str = ""
    expires_at: str = ""
    status: str = "ACTIVE"
    vehicle: Optional[VehicleOfInterest] = None


class MissingPersonDatabase:
    """Small local bulletin database for authorised missing-person assistance.

    This module deliberately does not implement biometric/facial identification.
    Person sightings require human review. Vehicle plate candidates may only be
    compared against vehicles explicitly attached to an active authorised case.
    """

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({"cases": [], "sightings": []})

    def _read(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, data: dict) -> None:
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def upsert_case(self, case: MissingPersonCase) -> None:
        data = self._read()
        payload = asdict(case)
        cases = [c for c in data["cases"] if c.get("case_id") != case.case_id]
        cases.append(payload)
        data["cases"] = cases
        self._write(data)

    def get_case(self, case_id: str) -> Optional[dict]:
        for case in self._read()["cases"]:
            if case.get("case_id") == case_id:
                return case
        return None

    def active_cases(self) -> list[dict]:
        return [c for c in self._read()["cases"] if c.get("status") == "ACTIVE"]

    @staticmethod
    def normalise_rego(rego: str) -> str:
        return "".join(ch for ch in rego.upper() if ch.isalnum())

    def match_case_vehicle_rego(self, observed_rego: str) -> list[dict]:
        """Return case-scoped plate candidates only; never a general plate history."""
        observed = self.normalise_rego(observed_rego)
        matches = []
        for case in self.active_cases():
            vehicle = case.get("vehicle") or {}
            expected = self.normalise_rego(vehicle.get("rego", ""))
            if expected and observed == expected:
                matches.append({
                    "case_id": case["case_id"],
                    "observed_rego": observed,
                    "status": "PENDING_HUMAN_REVIEW",
                })
        return matches

    def add_possible_sighting(
        self,
        case_id: str,
        location: str,
        notes: str = "",
        evidence_path: str = "",
        sighting_type: str = "PERSON",
        observed_rego: str = "",
    ) -> dict:
        if self.get_case(case_id) is None:
            raise ValueError("Unknown missing-person case")

        record = {
            "case_id": case_id,
            "type": sighting_type,
            "location": location,
            "notes": notes,
            "evidence_path": evidence_path,
            "observed_rego": self.normalise_rego(observed_rego),
            "status": "PENDING_HUMAN_REVIEW",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        data = self._read()
        data["sightings"].append(record)
        self._write(data)
        return record

    def sightings_for_case(self, case_id: str) -> list[dict]:
        return [s for s in self._read()["sightings"] if s.get("case_id") == case_id]

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from missing_person import MissingPersonDatabase


@dataclass
class CameraObservation:
    observation_type: str
    location: str
    evidence_path: str = ""
    observed_rego: str = ""
    vehicle_make_model: str = ""
    vehicle_colour: str = ""
    notes: str = ""


class MissingPersonCameraAssist:
    """Human-reviewed camera assistance for authorised missing-person cases.

    This module deliberately does not perform facial recognition or biometric
    identity matching. Person observations are only recorded as possible
    sightings for human review. Vehicle registration candidates may be matched
    only against vehicles explicitly attached to active missing-person cases.
    """

    def __init__(self, database: MissingPersonDatabase):
        self.database = database

    def record_person_observation(
        self,
        case_id: str,
        location: str,
        evidence_path: str = "",
        notes: str = "",
    ) -> dict:
        """Record a possible person sighting for an already-selected case."""
        return self.database.add_possible_sighting(
            case_id=case_id,
            location=location,
            notes=notes or "Camera detected a person; human identity review required.",
            evidence_path=evidence_path,
            sighting_type="PERSON",
        )

    def process_vehicle_observation(
        self,
        observed_rego: str,
        location: str,
        evidence_path: str = "",
        make_model: str = "",
        colour: str = "",
    ) -> list[dict]:
        """Match a plate candidate only to vehicles linked to active cases."""
        matches = self.database.match_case_vehicle_rego(observed_rego)
        records: list[dict] = []
        for match in matches:
            notes = "Case-linked vehicle registration candidate. Human review required."
            if make_model:
                notes += f" Observed vehicle: {make_model}."
            if colour:
                notes += f" Colour: {colour}."
            records.append(
                self.database.add_possible_sighting(
                    case_id=match["case_id"],
                    location=location,
                    notes=notes,
                    evidence_path=evidence_path,
                    sighting_type="VEHICLE",
                    observed_rego=observed_rego,
                )
            )
        return records

    @staticmethod
    def sapol_review_packet(case: dict, sighting: dict) -> dict:
        """Create a minimal review packet for an authorised human reviewer."""
        vehicle = case.get("vehicle") or {}
        return {
            "case_id": case.get("case_id", ""),
            "missing_person_name": case.get("name", ""),
            "sighting_type": sighting.get("type", ""),
            "location": sighting.get("location", ""),
            "created_at": sighting.get("created_at", ""),
            "observed_rego": sighting.get("observed_rego", ""),
            "case_vehicle_rego": vehicle.get("rego", ""),
            "evidence_path": sighting.get("evidence_path", ""),
            "notes": sighting.get("notes", ""),
            "status": "PENDING_HUMAN_REVIEW",
            "identity_decision": "NOT_AUTOMATED",
            "review_required": True,
        }

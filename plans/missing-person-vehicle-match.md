# Missing Person Assistance — Vehicle / Rego Matching

Status: DESIGN FOR v1.2.9+

Senton may support authorised missing-person bulletins that include a specific vehicle registration (rego), vehicle make/model, colour and other identifying details.

## Rego matching scope

- Match only against a specific authorised bulletin/case supplied by police or an approved operator.
- Do not create a general-purpose database of every registration plate seen.
- Camera OCR may read visible registration plates and compare them against the active case plate(s).
- A plate match is a POSSIBLE VEHICLE SIGHTING, not proof that the missing person is present.
- Record time, GPS/location (when available), camera name and the matched plate text.
- Allow one relevant vehicle/plate evidence frame for human review when lawful and appropriate.
- Notify the authorised case contact/operator when a possible match occurs.
- Human review is required before a sighting is treated as confirmed.

## Safety and privacy

- Privacy Guard always overrides this feature in toilets, changerooms and other restricted privacy zones.
- Do not use face recognition to identify the missing person.
- Case/watch data must expire when the bulletin closes or reaches its expiry date.
- Limit access to authorised users and maintain an audit log of case uploads, matches and exports.
- Do not expose plate-watch data publicly.

Example event:

Possible vehicle sighting
Case: MP-2026-00587
Rego expected: S123ABC
Rego read: S123ABC
Vehicle: White Toyota Corolla
Time: 14:32:08
Location: Adelaide SA
Status: PENDING HUMAN REVIEW

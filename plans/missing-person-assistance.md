# Senton Missing Person Assistance

Status: v1.2.9+ development

## Purpose

Provide an authorised, privacy-preserving workflow for missing-person bulletins, possible sightings, case-scoped vehicle registration matching, evidence packaging and owner/police review.

## Core ideas included

- Authorised police/owner bulletin upload with case ID, name, age where appropriate, last-seen details, last-known area, clothing, notes, expiry and optional vehicle of interest.
- Local missing-person bulletin database with active/expired/closed states.
- Possible sighting records with time, location, notes and optional evidence attachment.
- Human review required before any sighting is treated as confirmed.
- Case-specific vehicle registration matching: OCR candidates may be compared only against regos explicitly attached to an active authorised bulletin.
- No general vehicle tracking history and no open-ended plate database.
- No facial-recognition identification or automatic declaration that a person has been found.
- Senton Link Emergency Assistance screen can display current GPS/location and offer a user-initiated CALL 000 action; no automatic emergency call is placed solely from an automated match.
- Police Evidence Mode remains read-only and approval/audit controlled.
- Privacy Guard always overrides missing-person assistance in toilets, bathrooms, showers, changing rooms and other restricted privacy zones.

## Privacy Guard interaction

If a restricted privacy zone is detected, camera capture stops immediately. Missing Person Assistance cannot override that lock. Only permitted exterior/sign evidence may be retained under the Privacy Guard policy.

## Alerts

Possible sightings may generate owner/test notifications and, when properly integrated with an authorised backend, a police review notification. Alerts must say POSSIBLE / PENDING HUMAN REVIEW unless a human reviewer confirms relevance.

## Release gate

Do not publish these features as operational police tooling until authentication, audit logging, data retention, case expiry, evidence integrity and access-control tests have passed.

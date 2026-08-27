# Senton Control — Police Evidence Mode

Status: DESIGN ADDED FOR v1.2.9+ — DO NOT ENABLE AS A BACKDOOR

Purpose: allow police to receive a controlled, auditable evidence package from Senton without giving police unrestricted remote access to the camera, owner PIN, vehicle controls, or Privacy Guard bypasses.

## Core design

- Owner-initiated or owner-approved only.
- Read-only evidence access.
- No live camera viewing by default.
- No remote control of the vehicle or Senton Control.
- No ability to disable or bypass Privacy Guard.
- No access to the owner's Senton Link PIN or authentication secrets.
- No hidden recording or covert camera activation.

## Evidence package

A Police Evidence Export may contain only material that was lawfully retained by Senton, such as:

- incident date/time
- device/app version
- camera identifier (single Main Camera)
- event type
- non-sensitive system log entries
- SHA-256 hashes for each exported file
- exterior sign-only Privacy Guard evidence images when permitted
- other ordinary retained camera evidence outside restricted privacy zones

Never include imagery from inside toilets, changerooms, bathrooms, showers or other restricted privacy zones.

## Access flow

1. Police officer requests evidence from the owner.
2. Owner opens Senton Link / Senton Control and chooses Police Evidence Export.
3. Owner selects the incident/time range and explicitly approves the export.
4. Senton creates a read-only evidence bundle plus a manifest and SHA-256 hashes.
5. The export records who authorised it, when it was created and exactly which files were included.
6. Police receive the exported package through a user-selected transfer method.

## Audit requirements

- Log export creation and completion.
- Log the selected incident/time range.
- Log file hashes, not sensitive credentials.
- Never log the owner's unlock PIN.
- Make exports tamper-evident through a signed or hashed manifest.

## Future optional feature

A time-limited Police Review Code may be added later, but only if it grants read-only access to a specific owner-approved evidence package and expires automatically. It must not unlock the main app, camera, Privacy Guard, or vehicle controls.

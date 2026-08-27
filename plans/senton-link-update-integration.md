# Senton Link Update Integration — v1.2.12+

Starting with the v1.2.12 development line, Senton Control's Updates area should also surface Senton Link Android update status.

## Intended behaviour

- Keep Senton Control and Senton Link as separate applications with separate version numbers and packages.
- The Senton Control Updates screen may show two products:
  - Senton Control (Windows)
  - Senton Link (Android)
- Each product must use its own signed/verified update manifest and package hash/signature.
- Senton Control must never install an Android APK onto Windows.
- Senton Link updates are delivered to the authorised phone over its own Android update path.
- Senton Control may display whether a Senton Link update is available and whether the paired phone has reported that update as installed.
- Keep a manual Check for Updates control.
- Do not restore the removed filename-based IMPORTANT UPDATE idea.

## Safety / integrity

- Never trust an update based on filename alone.
- Reject unverified or incorrectly signed packages.
- Never place the owner's Senton Link unlock PIN in Windows update metadata, logs or manifests.
- Privacy Guard and existing failsafes remain active during update operations.

## Future UI

Updates
- Senton Control — current / latest / status
- Senton Link — paired phone version / latest / status
- Check for Updates

This file is a development specification. Actual Android OTA delivery requires the Senton Link updater and paired-phone communication to be implemented and tested before being described as operational.

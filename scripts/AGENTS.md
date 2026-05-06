## Script Directory Overview

This folder contains start and stop scripts for macOS, Linux, and Windows.

### Files

- `start-mac.sh`
- `stop-mac.sh`
- `start-linux.sh`
- `stop-linux.sh`
- `start-windows.ps1`
- `stop-windows.ps1`

### Behavior

- Start scripts build Docker image `pm-mvp` and run container `pm-mvp` on port `8000` by default.
- If `.env` exists in repo root, start scripts pass it to Docker via `--env-file`.
- Stop scripts stop and remove the `pm-mvp` container.
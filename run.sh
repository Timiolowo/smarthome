#!/usr/bin/env bash
# ==============================================================================
# 1-Click Launcher for Timilehin Home AI Assistant
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
    echo "Virtual environment not found. Running installer first..."
    ./install.sh
fi

# Check and request macOS microphone permission automatically on launch
if [[ "$(uname)" == "Darwin" ]] && command -v swift >/dev/null 2>&1; then
    swift -e '
import AVFoundation

let status = AVCaptureDevice.authorizationStatus(for: .audio)
if status == .notDetermined {
    let sema = DispatchSemaphore(value: 0)
    AVCaptureDevice.requestAccess(for: .audio) { _ in sema.signal() }
    _ = sema.wait(timeout: .now() + 10.0)
}
' 2>/dev/null || true
fi

# shellcheck disable=SC1091
source .venv/bin/activate
python -m src.main "$@"

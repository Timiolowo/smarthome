#!/usr/bin/env bash
# ==============================================================================
# macOS Terminal Microphone Permission Requester
# Triggers native macOS system authorization prompt and opens Privacy settings.
# ==============================================================================

echo "🎙️  Checking macOS Terminal Microphone Permission..."

if [[ "$(uname)" != "Darwin" ]]; then
    echo "ℹ️  Non-macOS system detected. Skipping macOS permission prompt."
    exit 0
fi

SWIFT_CODE='
import AVFoundation

let status = AVCaptureDevice.authorizationStatus(for: .audio)
if status == .notDetermined {
    print("PROMPTING: Requesting microphone permission from macOS...")
    let sema = DispatchSemaphore(value: 0)
    AVCaptureDevice.requestAccess(for: .audio) { granted in
        if granted {
            print("STATUS: GRANTED")
        } else {
            print("STATUS: DENIED")
        }
        sema.signal()
    }
    _ = sema.wait(timeout: .now() + 15.0)
} else if status == .authorized {
    print("STATUS: GRANTED")
} else if status == .denied || status == .restricted {
    print("STATUS: DENIED")
}
'

OUTPUT=$(swift -e "$SWIFT_CODE" 2>&1)

if echo "$OUTPUT" | grep -q "STATUS: GRANTED"; then
    echo "✅ Microphone access is GRANTED for this Terminal!"
    echo "You can now run ./run.sh with full voice control."
    exit 0
else
    echo "⚠️  Microphone access is currently DENIED or BLOCKED by macOS for this Terminal."
    echo "Opening macOS System Settings → Privacy & Security → Microphone now..."
    open "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone" 2>/dev/null || open "/System/Applications/System Settings.app"
    echo ""
    echo "👉 Toggle the switch ON for your terminal app (Terminal / iTerm / VS Code / Cursor)."
    echo "👉 Then restart this terminal window and run ./run.sh."
fi

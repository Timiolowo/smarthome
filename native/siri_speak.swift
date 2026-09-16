#!/usr/bin/env swift
//
// siri_speak.swift — Premium Siri Neural Voice TTS for SmartHome Assistant
//
// Uses AVSpeechSynthesizer to access high-quality Apple neural voices
// that the legacy `say` command cannot reach.
//
// Usage:
//   ./siri_speak "Hello, welcome home!"              # Speak with best auto-detected voice
//   ./siri_speak -v Nora "Hello!"                     # Speak with a specific voice
//   ./siri_speak -o output.wav "Hello!"               # Render to WAV file
//   ./siri_speak --list                               # List all available premium voices
//

import AVFoundation
import Foundation

// MARK: - Voice Discovery

func listVoices(premiumOnly: Bool) {
    let voices = AVSpeechSynthesisVoice.speechVoices()
    let english = voices.filter { $0.language.hasPrefix("en") }
        .sorted { v1, v2 in
            if v1.quality.rawValue != v2.quality.rawValue {
                return v1.quality.rawValue > v2.quality.rawValue
            }
            return v1.name < v2.name
        }

    let filtered = premiumOnly
        ? english.filter { $0.quality.rawValue >= AVSpeechSynthesisVoiceQuality.enhanced.rawValue }
        : english

    if filtered.isEmpty {
        print("No \(premiumOnly ? "premium/enhanced " : "")English voices found.")
        print("Go to: System Settings → Accessibility → Spoken Content → Manage Voices")
        print("Download enhanced or premium voices for the best quality.")
        return
    }

    print("─────────────────────────────────────────────────────")
    print("  Available \(premiumOnly ? "Premium " : "")Voices (English)")
    print("─────────────────────────────────────────────────────")
    for v in filtered {
        let qualityLabel: String
        switch v.quality {
        case .premium:
            qualityLabel = "⭐ Premium"
        case .enhanced:
            qualityLabel = "✨ Enhanced"
        default:
            qualityLabel = "   Standard"
        }
        let siri = v.identifier.contains("siri") ? " 🔊 SIRI" : ""
        print("  \(qualityLabel)  \(v.name) [\(v.language)]\(siri)")
    }
    print("─────────────────────────────────────────────────────")
}

// MARK: - Best Voice Selection

func findBestVoice(preferred: String?) -> AVSpeechSynthesisVoice? {
    let voices = AVSpeechSynthesisVoice.speechVoices()
    let english = voices.filter { $0.language.hasPrefix("en") }
        .sorted { v1, v2 in
            if v1.quality.rawValue != v2.quality.rawValue {
                return v1.quality.rawValue > v2.quality.rawValue
            }
            return v1.name < v2.name
        }

    // If user specified a voice name, find it
    if let name = preferred, !name.isEmpty, name.lowercased() != "default" {
        let needle = name.lowercased()
        if let exact = english.first(where: { $0.name.lowercased() == needle }) {
            return exact
        }
        let matches = english.filter { $0.name.lowercased().contains(needle) || $0.identifier.lowercased().contains(needle) }
            .sorted { $0.quality.rawValue > $1.quality.rawValue }
        if let best = matches.first { return best }
    }

    // Auto-detect: prioritize Siri neural > premium > enhanced > standard
    // 1. Siri voices (enhanced/premium)
    if let siri = english.first(where: { $0.identifier.lowercased().contains("siri") && $0.quality.rawValue >= AVSpeechSynthesisVoiceQuality.enhanced.rawValue }) {
        return siri
    }

    // 2. Any premium quality voice
    if let premium = english.first(where: { $0.quality == .premium }) {
        return premium
    }

    // 3. Any enhanced quality voice (e.g. Voice 4)
    if let enhanced = english.first(where: { $0.quality == .enhanced }) {
        return enhanced
    }

    // 4. Any Siri voice regardless of quality
    if let siriAny = english.first(where: { $0.identifier.lowercased().contains("siri") }) {
        return siriAny
    }

    // 5. Fallback to US English default
    return english.first(where: { $0.language == "en-US" }) ?? english.first
}

// MARK: - Speech Synthesis

class SpeechDelegate: NSObject, AVSpeechSynthesizerDelegate {
    var isDone = false

    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
        isDone = true
    }

    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didCancel utterance: AVSpeechUtterance) {
        isDone = true
    }
}

func speakText(_ text: String, voiceName: String?, outputPath: String?) {
    guard let voice = findBestVoice(preferred: voiceName) else {
        fputs("Error: No suitable voice found.\n", stderr)
        exit(1)
    }

    let utterance = AVSpeechUtterance(string: text)
    utterance.voice = voice
    utterance.rate = AVSpeechUtteranceDefaultSpeechRate
    utterance.pitchMultiplier = 1.0
    utterance.volume = 1.0

    let qualityStr: String
    switch voice.quality {
    case .premium: qualityStr = "Premium"
    case .enhanced: qualityStr = "Enhanced"
    default: qualityStr = "Standard"
    }
    fputs("[SiriSpeak] Voice: \(voice.name) [\(voice.language)] (\(qualityStr))\n", stderr)

    let synthesizer = AVSpeechSynthesizer()
    let delegate = SpeechDelegate()
    synthesizer.delegate = delegate

    if let path = outputPath {
        // Write to WAV file
        var fileOutput: AVAudioFile?
        synthesizer.write(utterance) { buffer in
            guard let pcmBuffer = buffer as? AVAudioPCMBuffer else {
                return
            }
            if pcmBuffer.frameLength == 0 && fileOutput != nil {
                delegate.isDone = true
                return
            }
            if fileOutput == nil {
                let url = URL(fileURLWithPath: path)
                do {
                    fileOutput = try AVAudioFile(
                        forWriting: url,
                        settings: pcmBuffer.format.settings,
                        commonFormat: .pcmFormatFloat32,
                        interleaved: false
                    )
                } catch {
                    fputs("Error creating output file: \(error)\n", stderr)
                    delegate.isDone = true
                    return
                }
            }
            if pcmBuffer.frameLength > 0 {
                do {
                    try fileOutput?.write(from: pcmBuffer)
                } catch {
                    fputs("Error writing audio: \(error)\n", stderr)
                }
            }
        }
        while !delegate.isDone {
            RunLoop.current.run(mode: .default, before: Date(timeIntervalSinceNow: 0.005))
        }
        fileOutput = nil // Flush and close file so headers are properly written
        fputs("[SiriSpeak] Saved: \(path)\n", stderr)
    } else {
        // Speak aloud
        synthesizer.speak(utterance)
        while !delegate.isDone {
            RunLoop.current.run(mode: .default, before: Date(timeIntervalSinceNow: 0.05))
        }
    }
}

// MARK: - CLI

var args = Array(CommandLine.arguments.dropFirst())

if args.isEmpty {
    print("Usage: siri_speak [OPTIONS] \"text to speak\"")
    print("  -v VOICE       Voice name (auto-detects Siri neural by default)")
    print("  -o FILE        Write audio to WAV file instead of speaking")
    print("  --list         List all available English voices")
    print("  --list-premium List only premium/enhanced voices")
    exit(0)
}

if args.contains("--list") {
    listVoices(premiumOnly: false)
    exit(0)
}

if args.contains("--list-premium") {
    listVoices(premiumOnly: true)
    exit(0)
}

var voiceName: String? = nil
var outputPath: String? = nil
var textParts: [String] = []

var i = 0
while i < args.count {
    switch args[i] {
    case "-v":
        i += 1
        if i < args.count { voiceName = args[i] }
    case "-o":
        i += 1
        if i < args.count { outputPath = args[i] }
    default:
        textParts.append(args[i])
    }
    i += 1
}

let text = textParts.joined(separator: " ")
if text.isEmpty {
    fputs("Error: No text provided.\n", stderr)
    exit(1)
}

speakText(text, voiceName: voiceName, outputPath: outputPath)

// Full-duplex microphone and playback share Apple's acoustic echo canceller.
import AVFoundation
import Foundation

let outputQueue = DispatchQueue(label: "voice.events")
func emit(_ event: [String: Any]) {
    outputQueue.async {
        if let data = try? JSONSerialization.data(withJSONObject: event) {
            FileHandle.standardOutput.write(data)
            FileHandle.standardOutput.write(Data([10]))
        }
    }
}
let engine = AVAudioEngine()
let player = AVAudioPlayerNode()
let audioQueue = DispatchQueue(label: "voice.audio")
let wireFormat = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: 16000,
                               channels: 1, interleaved: false)!
var playbackID = ""

do {
    let input = engine.inputNode
    try input.setVoiceProcessingEnabled(true)
    input.isVoiceProcessingAGCEnabled = true
    let inputFormat = input.outputFormat(forBus: 0)
    guard inputFormat.sampleRate > 0, inputFormat.channelCount > 0,
          let converter = AVAudioConverter(from: inputFormat, to: wireFormat) else {
        throw NSError(domain: "VoiceAudio", code: 1,
                      userInfo: [NSLocalizedDescriptionKey: "No usable default microphone"])
    }
    engine.attach(player)
    engine.connect(player, to: engine.mainMixerNode, format: wireFormat)
    input.installTap(onBus: 0, bufferSize: 1024, format: inputFormat) { buffer, _ in
        // Copy before leaving the tap; the hardware reuses its buffer.
        guard let copy = AVAudioPCMBuffer(pcmFormat: inputFormat, frameCapacity: buffer.frameLength),
              let source = buffer.floatChannelData, let destination = copy.floatChannelData else { return }
        copy.frameLength = buffer.frameLength
        for channel in 0..<Int(inputFormat.channelCount) {
            destination[channel].update(from: source[channel], count: Int(buffer.frameLength))
        }
        audioQueue.async {
            let capacity = AVAudioFrameCount(Double(copy.frameLength) * 16000 / inputFormat.sampleRate + 32)
            guard let converted = AVAudioPCMBuffer(pcmFormat: wireFormat, frameCapacity: capacity) else { return }
            var supplied = false
            var error: NSError?
            converter.convert(to: converted, error: &error) { _, status in
                if supplied { status.pointee = .noDataNow; return nil }
                supplied = true
                status.pointee = .haveData
                return copy
            }
            if let error = error { emit(["event": "error", "message": error.localizedDescription]); return }
            if let samples = converted.floatChannelData, converted.frameLength > 0 {
                let data = Data(bytes: samples[0], count: Int(converted.frameLength) * 4)
                emit(["event": "audio", "pcm": data.base64EncodedString()])
            }
        }
    }
    try engine.start()
    emit(["event": "ready", "echo_cancelled": input.isVoiceProcessingEnabled])
} catch {
    emit(["event": "error", "message": error.localizedDescription])
    outputQueue.sync {}
    exit(1)
}

// Keep AVAudioEngine's main run loop alive; serialize playback commands on main.
DispatchQueue.global().async {
    while let line = readLine() {
        guard let data = line.data(using: .utf8),
              let command = try? JSONSerialization.jsonObject(with: data) as? [String: String] else { continue }
        DispatchQueue.main.async {
            let id = command["id"] ?? ""
            switch command["command"] {
            case "play":
                do {
                    player.stop()
                    playbackID = id
                    let file = try AVAudioFile(forReading: URL(fileURLWithPath: command["path"] ?? ""))
                    guard file.processingFormat.sampleRate == 16000, file.processingFormat.channelCount == 1 else {
                        throw NSError(domain: "VoiceAudio", code: 2,
                                      userInfo: [NSLocalizedDescriptionKey: "Playback requires mono 16 kHz audio"])
                    }
                    player.scheduleFile(file, at: nil, completionCallbackType: .dataPlayedBack) { _ in
                        emit(["event": "played", "id": id])
                    }
                    player.play()
                    emit(["event": "playing", "id": id])
                } catch { emit(["event": "play_error", "id": id, "message": error.localizedDescription]) }
            case "stop":
                player.stop()
                emit(["event": "played", "id": playbackID])
            case "quit":
                engine.stop()
                exit(0)
            default: break
            }
        }
    }
    DispatchQueue.main.async { engine.stop(); exit(0) }
}
RunLoop.main.run()

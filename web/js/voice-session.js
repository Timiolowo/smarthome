/* Browser-owned duplex voice: local capture -> local Faster-Whisper -> browser system voice. */
(function () {
  class BrowserVoiceSession {
    constructor() {
      this.stream = null;
      this.context = null;
      this.processor = null;
      this.source = null;
      this.silentGain = null;
      this.startPromise = null;
      this.mode = 'wake';
      this.sampleRate = 48000;
      this.noiseFloor = 0.004;
      this.calibration = [];
      this.preRoll = [];
      this.preRollSamples = 0;
      this.capture = [];
      this.captureSamples = 0;
      this.capturing = false;
      this.voicedBuffers = 0;
      this.silentBuffers = 0;
      this.processing = false;
      this.queuedFrames = null;
      this.interrupting = false;
      this.inactivityTimer = null;
    }

    _clearInactivityTimer() {
      if (this.inactivityTimer) {
        clearTimeout(this.inactivityTimer);
        this.inactivityTimer = null;
      }
    }

    _getAssistantName() {
      return (window.cachedStatus?.assistant?.name || window.cachedStatus?.config?.assistant_name || 'Nova').toUpperCase();
    }

    _startInactivityTimer() {
      this._clearInactivityTimer();
      if (this.mode !== 'live') return;
      this.inactivityTimer = setTimeout(() => {
        if (this.mode === 'live' && !this.capturing && !this.processing && !window.__isAssistantSpeaking) {
          this.mode = 'wake';
          this._setStatus(`WAITING FOR “${this._getAssistantName()}”`);
          if (window.tarsController) {
            window.tarsController.setState('standby');
          }
          if (typeof window.triggerStandbyMode === 'function') {
            window.triggerStandbyMode();
          }
        }
      }, 20000);
    }

    async ensureStarted() {
      if (this.mode === 'off' || this.stream) return;
      if (this.startPromise) return this.startPromise;
      this.startPromise = this._start().finally(() => { this.startPromise = null; });
      return this.startPromise;
    }

    async _start() {
      if (!navigator.mediaDevices?.getUserMedia) {
        this._unavailable('This browser does not provide microphone capture.');
        return;
      }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            channelCount: 1,
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
          video: false,
        });
        if (this.mode === 'off') {
          stream.getTracks().forEach(track => track.stop());
          return;
        }
        this.stream = stream;
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        this.context = new AudioContextClass();
        await this.context.resume();
        this.sampleRate = this.context.sampleRate;
        this.source = this.context.createMediaStreamSource(stream);
        this.processor = this.context.createScriptProcessor(2048, 1, 1);
        this.silentGain = this.context.createGain();
        this.silentGain.gain.value = 0;
        this.source.connect(this.processor);
        this.processor.connect(this.silentGain);
        this.silentGain.connect(this.context.destination);
        this.processor.onaudioprocess = event => this._onAudio(event.inputBuffer.getChannelData(0));

        const track = stream.getAudioTracks()[0];
        const settings = track?.getSettings?.() || {};
        await fetch('/api/voice/browser-ready', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            device: track?.label || 'Browser microphone',
            echo_cancellation: settings.echoCancellation === true,
            noise_suppression: settings.noiseSuppression === true,
            auto_gain_control: settings.autoGainControl === true,
          }),
        });
        this._setStatus(this.mode === 'live' ? 'LIVE LISTENING' : `WAITING FOR “${this._getAssistantName()}”`);
      } catch (error) {
        this.stopCapture();
        this._unavailable(error.name === 'NotAllowedError'
          ? `Allow microphone access in the browser to use ${this._getAssistantName()} voice.`
          : `Browser microphone failed: ${error.message}`);
      }
    }

    async setMode(mode) {
      this.mode = mode || 'wake';
      if (this.mode === 'off') {
        this.stopCapture();
        return;
      }
      await this.ensureStarted();
    }

    stopCapture() {
      if (this.processor) this.processor.onaudioprocess = null;
      for (const node of [this.source, this.processor, this.silentGain]) {
        try { node?.disconnect(); } catch (_) {}
      }
      this.stream?.getTracks().forEach(track => track.stop());
      if (this.context && this.context.state !== 'closed') this.context.close().catch(() => {});
      this.stream = null;
      this.context = null;
      this.processor = null;
      this.source = null;
      this.silentGain = null;
      this.capturing = false;
      this.preRoll = [];
      this.capture = [];
    }

    _onAudio(input) {
      if (this.mode === 'off') return;
      const frame = new Float32Array(input);
      const rms = Math.sqrt(frame.reduce((sum, value) => sum + value * value, 0) / frame.length);
      if (this.calibration.length < 18 && !window.__isAssistantSpeaking) {
        this.calibration.push(rms);
        const sorted = [...this.calibration].sort((a, b) => a - b);
        this.noiseFloor = sorted[Math.floor(sorted.length / 2)] || this.noiseFloor;
      }
      // When assistant is speaking, use a much higher threshold and buffer requirement to prevent speaker acoustic feedback
      const isSpeaking = Boolean(window.__isAssistantSpeaking);
      const threshold = isSpeaking
        ? Math.max(0.065, this.noiseFloor * 5.5)
        : Math.max(0.012, this.noiseFloor * 2.5);
      const voiced = rms >= threshold;

      this.preRoll.push(frame);
      this.preRollSamples += frame.length;
      const maxPreRoll = Math.round(this.sampleRate * 0.65);
      while (this.preRollSamples > maxPreRoll && this.preRoll.length > 1) {
        this.preRollSamples -= this.preRoll.shift().length;
      }

      if (!this.capturing) {
        this.voicedBuffers = voiced ? this.voicedBuffers + 1 : 0;
        const speechAge = performance.now() - (window.__browserSpeechStartedAt || 0);
        const canBargeIn = isSpeaking && speechAge > 800;
        const requiredBuffers = isSpeaking ? 6 : 2;

        if (this.voicedBuffers >= requiredBuffers && (!isSpeaking || canBargeIn)) {
          this._beginUtterance(Boolean(isSpeaking));
        }
        return;
      }

      this.capture.push(frame);
      this.captureSamples += frame.length;
      this.silentBuffers = voiced ? 0 : this.silentBuffers + 1;
      const silenceSeconds = this.silentBuffers * frame.length / this.sampleRate;
      const totalSeconds = this.captureSamples / this.sampleRate;
      if ((silenceSeconds >= 0.8 && totalSeconds >= 0.4) || totalSeconds >= 30) {
        this._finishUtterance();
      }
    }

    _beginUtterance(isInterruption) {
      this._clearInactivityTimer();
      if (typeof window.hideIosStandby === 'function') {
        window.hideIosStandby();
      }
      this.capturing = true;
      this.capture = this.preRoll.map(frame => new Float32Array(frame));
      this.captureSamples = this.capture.reduce((total, frame) => total + frame.length, 0);
      this.silentBuffers = 0;
      this.voicedBuffers = 0;

      // INSTANT CUT: Immediately stop assistant speech the millisecond user starts speaking
      if (isInterruption || window.__isAssistantSpeaking) {
        if (typeof window.stopAllAssistantSpeech === 'function') {
          window.stopAllAssistantSpeech();
        }
      }

      this._setStatus(isInterruption ? 'INTERRUPTED — LISTENING' : 'HEARING YOU');
      if (window.tarsController) {
        window.tarsController.setState('listening');
      }
      if (isInterruption && !this.interrupting) {
        this.interrupting = true;
        Promise.resolve(window.interruptAssistant?.()).finally(() => { this.interrupting = false; });
      }
    }

    async _finishUtterance() {
      if (!this.capturing) return;
      this.capturing = false;
      const frames = this.capture;
      this.capture = [];
      this.captureSamples = 0;
      if (this.processing) {
        this.queuedFrames = frames;
        this._setStatus('INTERRUPTED — UNDERSTANDING');
        if (window.tarsController) {
          window.tarsController.setState('thinking');
        }
        return;
      }
      await this._submitFrames(frames);
    }

    async _submitFrames(frames) {
      this._clearInactivityTimer();
      this.processing = true;
      this._setStatus('TRANSCRIBING & THINKING...');
      if (window.tarsController) {
        window.tarsController.setState('thinking');
      }
      try {
        const wav = this._encodeWav(frames, this.sampleRate);
        const response = await fetch('/api/voice/browser-turn', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({audio: this._toBase64(wav)}),
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'Voice request failed');
        const heard = document.getElementById('live-heard-text');
        if (heard && result.heard) heard.textContent = `"${result.heard}"`;
        if (result.interrupted || result.ignored || !result.reply) {
          if (typeof window.stopAllAssistantSpeech === 'function') {
            window.stopAllAssistantSpeech();
          }
          this._setStatus(this.mode === 'live' ? 'LIVE LISTENING' : `WAITING FOR “${this._getAssistantName()}”`);
          if (window.tarsController) {
            window.tarsController.setState(this.mode === 'live' ? 'listening' : 'standby');
          }
          if (this.mode === 'live') {
            this._startInactivityTimer();
          }
          return;
        }
        const reply = document.getElementById('live-reply-text');
        if (reply) reply.textContent = `"${result.reply}"`;
        if (result.end_conversation || result.standby) {
          this.mode = 'wake';
        } else if (result.wake) {
          this.mode = 'live';
          if (typeof window.hideIosStandby === 'function') {
            window.hideIosStandby();
          }
        }
        window.speakWithBrowserVoice(result.reply, () => {
          this._setStatus(this.mode === 'live' ? 'LIVE LISTENING' : `WAITING FOR “${this._getAssistantName()}”`);
          if (window.tarsController) {
            window.tarsController.setState(this.mode === 'live' ? 'listening' : 'standby');
          }
          if (this.mode === 'live') {
            this._startInactivityTimer();
          } else if (result.standby || result.end_conversation) {
            if (typeof window.showIosStandby === 'function') {
              window.showIosStandby();
            } else if (typeof window.triggerStandbyMode === 'function') {
              window.triggerStandbyMode();
            }
          }
        });
      } catch (error) {
        this._unavailable(error.message);
      } finally {
        this.processing = false;
        if (this.queuedFrames) {
          const queued = this.queuedFrames;
          this.queuedFrames = null;
          setTimeout(() => this._submitFrames(queued), 0);
        }
      }
    }

    _encodeWav(frames, sourceRate) {
      const sourceLength = frames.reduce((total, frame) => total + frame.length, 0);
      const source = new Float32Array(sourceLength);
      let offset = 0;
      for (const frame of frames) { source.set(frame, offset); offset += frame.length; }
      const targetRate = 16000;
      const targetLength = Math.max(1, Math.round(source.length * targetRate / sourceRate));
      const output = new Int16Array(targetLength);
      for (let index = 0; index < targetLength; index++) {
        const position = index * sourceRate / targetRate;
        const left = Math.floor(position);
        const right = Math.min(left + 1, source.length - 1);
        const mix = position - left;
        const sample = source[left] * (1 - mix) + source[right] * mix;
        output[index] = Math.max(-1, Math.min(1, sample)) * 32767;
      }
      const buffer = new ArrayBuffer(44 + output.byteLength);
      const view = new DataView(buffer);
      const write = (at, text) => [...text].forEach((char, i) => view.setUint8(at + i, char.charCodeAt(0)));
      write(0, 'RIFF'); view.setUint32(4, 36 + output.byteLength, true); write(8, 'WAVE');
      write(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
      view.setUint16(22, 1, true); view.setUint32(24, targetRate, true);
      view.setUint32(28, targetRate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
      write(36, 'data'); view.setUint32(40, output.byteLength, true);
      new Int16Array(buffer, 44).set(output);
      return buffer;
    }

    _toBase64(buffer) {
      const bytes = new Uint8Array(buffer);
      let binary = '';
      for (let offset = 0; offset < bytes.length; offset += 0x8000) {
        binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
      }
      return btoa(binary);
    }

    _setStatus(message) {
      const label = document.getElementById('live-orb-state-text');
      if (label) label.textContent = message;
      const termLabel = document.getElementById('terminal-voice-mode');
      if (termLabel) {
        termLabel.classList.remove('error');
        termLabel.textContent = message;
      }
    }

    _unavailable(message) {
      this._setStatus('BROWSER MICROPHONE UNAVAILABLE');
      if (window.tarsController) {
        window.tarsController.setState('error');
      }
      if (typeof window.showSonner === 'function') window.showSonner('Browser Voice Unavailable', message);
    }
  }

  const session = new BrowserVoiceSession();
  window.browserVoiceSession = session;
  document.addEventListener('DOMContentLoaded', () => session.ensureStarted());
  window.addEventListener('beforeunload', () => session.stopCapture());
})();

/**
 * Audio capture for the FFT controller.
 *
 * Two ways to get the system's audio output into the browser:
 *
 *  1. `startDevice(deviceId)` — capture an *input* device that mirrors the
 *     output, e.g. Windows "Stereo Mix" (or a loopback device). Select it in
 *     the device dropdown.
 *  2. `startSystem()` — `getDisplayMedia({ video: false, audio: true })`.
 *     Chrome/Edge show the screen picker; choose "Entire screen" to capture
 *     all system audio (or a specific window to capture only that window's
 *     audio). Works on systems without Stereo Mix.
 *
 * The captured stream is fed into an `AnalyserNode` (FFT size 8192) and the
 * raw byte frequency data is exposed for the engine loop.
 */

export type CaptureSource = 'device' | 'system';

export class AudioCapture {
  /** FFT size for the analyser (must be a power of two, 32..32768). */
  static readonly FFT_SIZE = 8192;

  /** Called when the captured stream ends on its own (e.g. user stops sharing). */
  onEnded: (() => void) | null = null;

  private ctx: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private stream: MediaStream | null = null;
  private freqData: Uint8Array<ArrayBuffer> | null = null;

  get isRunning(): boolean {
    return this.analyser !== null;
  }

  get sampleRate(): number {
    return this.ctx?.sampleRate ?? 48000;
  }

  get fftSize(): number {
    return AudioCapture.FFT_SIZE;
  }

  /** Capture a specific audio input device (e.g. "Stereo Mix"). */
  async startDevice(deviceId: string): Promise<void> {
    this.stop();
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        deviceId: deviceId ? { exact: deviceId } : undefined,
        // We want the raw mix, not a "cleaned up" mic signal.
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false
      }
    });
    this.attach(stream);
  }

  /** Capture system audio via the screen-picker (audio only). */
  async startSystem(): Promise<void> {
    this.stop();
    const stream = await navigator.mediaDevices.getDisplayMedia({
      video: false,
      audio: {
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false
      }
    });
    const track = stream.getAudioTracks()[0];
    if (track) {
      track.addEventListener('ended', this.handleTrackEnded);
    }
    this.attach(stream);
  }

  stop(): void {
    const track = this.stream?.getAudioTracks()[0];
    if (track) {
      track.removeEventListener('ended', this.handleTrackEnded);
    }
    this.stream?.getTracks().forEach((t) => t.stop());
    this.source?.disconnect();
    this.analyser?.disconnect();
    if (this.ctx) {
      void this.ctx.close().catch(() => undefined);
    }
    this.stream = null;
    this.source = null;
    this.analyser = null;
    this.ctx = null;
    this.freqData = null;
  }

  /**
   * Get the current byte frequency data (0..255 per bin). Returns null when
   * no capture is running. The returned buffer is reused across calls.
   */
  getFrequencyData(): Uint8Array<ArrayBuffer> | null {
    if (!this.analyser) {
      return null;
    }
    if (!this.freqData || this.freqData.length !== this.analyser.frequencyBinCount) {
      this.freqData = new Uint8Array(this.analyser.frequencyBinCount);
    }
    this.analyser.getByteFrequencyData(this.freqData);
    return this.freqData;
  }

  private handleTrackEnded = (): void => {
    this.onEnded?.();
  };

  private attach(stream: MediaStream): void {
    const ctx = new AudioContext();
    void ctx.resume();
    this.ctx = ctx;
    this.stream = stream;
    this.source = ctx.createMediaStreamSource(stream);
    this.analyser = ctx.createAnalyser();
    this.analyser.fftSize = AudioCapture.FFT_SIZE;
    // Raw FFT output — smoothing is applied by the engine, not the analyser.
    this.analyser.smoothingTimeConstant = 0;
    this.source.connect(this.analyser);
  }
}

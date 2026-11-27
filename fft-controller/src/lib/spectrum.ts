/**
 * FFT band helpers. The spectrum data comes from a Web Audio `AnalyserNode`
 * (an FFT internally), so this module only maps bins to frequency bands.
 */

/**
 * Compute the normalized (0..1) energy of the frequency band [lowHz, highHz].
 *
 * @param data - Byte frequency data from `AnalyserNode.getByteFrequencyData`
 * @param sampleRate - Audio sample rate in Hz
 * @param fftSize - The analyser's `fftSize` (data.length === fftSize / 2)
 * @param lowHz - Band lower bound in Hz
 * @param highHz - Band upper bound in Hz
 */
export function bandEnergy(
  data: Uint8Array,
  sampleRate: number,
  fftSize: number,
  lowHz: number,
  highHz: number
): number {
  if (data.length === 0 || sampleRate <= 0 || fftSize <= 0) {
    return 0;
  }
  if (highHz <= lowHz) {
    return 0;
  }

  const binHz = sampleRate / fftSize;
  let i0 = Math.floor(lowHz / binHz);
  let i1 = Math.ceil(highHz / binHz);
  if (i0 < 0) i0 = 0;
  if (i1 > data.length - 1) i1 = data.length - 1;
  if (i1 < i0) return 0;

  let sum = 0;
  for (let i = i0; i <= i1; i++) {
    sum += data[i];
  }
  return sum / ((i1 - i0 + 1) * 255);
}

/** Clamp `norm` to 0..1 and map it linearly onto [min, max]. */
export function mapToRange(norm: number, min: number, max: number): number {
  const t = Math.min(1, Math.max(0, norm));
  return min + t * (max - min);
}

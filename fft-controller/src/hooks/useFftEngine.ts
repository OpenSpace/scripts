import { useEffect, useRef, useState } from 'react';
import type { AudioCapture } from '../lib/audio';
import type { OpenSpaceClient } from '../lib/openspace';
import { bandEnergy, mapToRange } from '../lib/spectrum';
import type { BandMapping } from '../lib/types';

/** Per-band state for one update frame. */
export interface BandState {
  id: string;
  /** Raw normalized band energy, 0..1 */
  energy: number;
  /** Smoothed band energy, 0..1 */
  smoothed: number;
  /** Mapped property value (min + smoothed * (max - min)) */
  value: number;
}

/**
 * Mutable state the engine writes every animation frame. Components read it
 * directly (canvas) or poll it on an interval (text readouts) instead of
 * going through React state at 60 Hz.
 */
export interface EngineState {
  /** True while a capture is running and producing data */
  running: boolean;
  sampleRate: number;
  fftSize: number;
  /** Raw byte frequency data (reused buffer) or null when idle */
  freqData: Uint8Array | null;
  bands: BandState[];
  lastSendAt: number;
  /** Total number of update ticks sent to OpenSpace */
  sends: number;
}

export function createEngineState(): EngineState {
  return {
    running: false,
    sampleRate: 0,
    fftSize: 0,
    freqData: null,
    bands: [],
    lastSendAt: 0,
    sends: 0
  };
}

interface EngineOptions {
  capture: AudioCapture;
  client: OpenSpaceClient;
  mappings: BandMapping[];
  /** How often (in Hz) property updates are sent to OpenSpace */
  updateRateHz: number;
  /** 0..1 — 1 means no smoothing, 0 means very slow response */
  smoothing: number;
  /** Shared mutable state, written every frame */
  stateRef: { current: EngineState };
  /** Master switch: only capture/send while true */
  enabled: boolean;
}

/**
 * The core loop: every animation frame read the FFT, compute each band's
 * energy, smooth it, map it to [min, max] and (throttled to `updateRateHz`)
 * push all values to OpenSpace in one batched Lua script.
 */
export function useFftEngine(opts: EngineOptions): void {
  const { capture, client, stateRef } = opts;

  // Keep the latest config in a ref so the rAF loop never restarts.
  const cfgRef = useRef(opts);
  cfgRef.current = opts;

  // Per-band smoothed energy, persisted across frames.
  const smoothRef = useRef(new Map<string, number>());

  useEffect(() => {
    let raf = 0;
    let last = performance.now();

    const tick = (now: number): void => {
      raf = requestAnimationFrame(tick);
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;

      const cfg = cfgRef.current;
      const state = stateRef.current;

      const freqData = cfg.enabled ? capture.getFrequencyData() : null;
      state.freqData = freqData;
      state.sampleRate = capture.sampleRate;
      state.fftSize = capture.fftSize;
      state.running = cfg.enabled && freqData !== null;

      const bands: BandState[] = [];
      const entries: { property: string; value: number }[] = [];

      for (const m of cfg.mappings) {
        const energy = freqData
          ? bandEnergy(freqData, state.sampleRate, state.fftSize, m.lowHz, m.highHz)
          : 0;

        // Exponential moving average; tau in [20 ms, 320 ms].
        const tau = 0.02 + (1 - cfg.smoothing) * 0.3;
        const alpha = 1 - Math.exp(-dt / tau);
        const prev = smoothRef.current.get(m.id) ?? energy;
        const smoothed = prev + (energy - prev) * alpha;
        smoothRef.current.set(m.id, smoothed);

        const value = mapToRange(smoothed, m.min, m.max);
        bands.push({ id: m.id, energy, smoothed, value });

        if (m.enabled && m.property.length > 0 && cfg.enabled && client.status === 'connected') {
          entries.push({ property: m.property, value });
        }
      }

      state.bands = bands;

      const intervalMs = 1000 / Math.max(1, cfg.updateRateHz);
      if (entries.length > 0 && now - state.lastSendAt >= intervalMs) {
        state.lastSendAt = now;
        client.setValues(entries);
        state.sends++;
      }
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [capture, client, stateRef]);
}

/**
 * Poll a band's live value from the shared engine state on an interval.
 * Used for the per-mapping readouts (10 Hz is plenty for text).
 */
export function useLiveBandValue(
  stateRef: { current: EngineState },
  id: string,
  intervalMs = 100
): BandState | null {
  const [band, setBand] = useState<BandState | null>(null);
  useEffect(() => {
    const update = (): void => {
      setBand(stateRef.current.bands.find((b) => b.id === id) ?? null);
    };
    update();
    const timer = setInterval(update, intervalMs);
    return () => clearInterval(timer);
  }, [stateRef, id, intervalMs]);
  return band;
}

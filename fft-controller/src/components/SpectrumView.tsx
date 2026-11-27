import { useEffect, useRef } from 'react';
import type { EngineState } from '../hooks/useFftEngine';
import { BAND_COLORS, type BandMapping } from '../lib/types';

const F_MIN = 20;
const F_MAX = 20000;
const GRID_FREQS = [50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000];

interface Props {
  stateRef: { current: EngineState };
  mappings: BandMapping[];
}

/**
 * Live spectrum on a log-frequency axis with one colored overlay per
 * mapping (its band range and current smoothed level).
 */
export function SpectrumView({ stateRef, mappings }: Props): React.ReactElement {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const mappingsRef = useRef(mappings);
  mappingsRef.current = mappings;

  useEffect(() => {
    let raf = 0;

    const draw = (): void => {
      raf = requestAnimationFrame(draw);
      const canvas = canvasRef.current;
      if (!canvas) return;

      const dpr = window.devicePixelRatio || 1;
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      if (w === 0 || h === 0) return;
      if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
        canvas.width = Math.round(w * dpr);
        canvas.height = Math.round(h * dpr);
      }

      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);

      const state = stateRef.current;
      const freqData = state.freqData;
      const sampleRate = state.sampleRate;
      const fftSize = state.fftSize;
      const binHz = sampleRate > 0 && fftSize > 0 ? sampleRate / fftSize : 0;
      const logSpan = Math.log(F_MAX / F_MIN);

      const xForFreq = (f: number): number =>
        ((Math.log(Math.min(Math.max(f, F_MIN), F_MAX)) / Math.log(F_MIN)) / logSpan) * w;

      // Grid + labels
      ctx.strokeStyle = 'rgba(255,255,255,0.08)';
      ctx.fillStyle = 'rgba(255,255,255,0.45)';
      ctx.font = '10px system-ui, sans-serif';
      ctx.lineWidth = 1;
      for (const f of GRID_FREQS) {
        const x = xForFreq(f);
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
        ctx.stroke();
        ctx.fillText(f >= 1000 ? `${f / 1000}k` : `${f}`, x + 3, h - 4);
      }

      // Spectrum (log-spaced sampling)
      if (freqData && binHz > 0) {
        ctx.beginPath();
        ctx.moveTo(0, h);
        const steps = Math.max(120, Math.floor(w / 2));
        for (let s = 0; s <= steps; s++) {
          const x = (s / steps) * w;
          const f = F_MIN * Math.pow(F_MAX / F_MIN, s / steps);
          const bin = f / binHz;
          const i0 = Math.floor(bin);
          const i1 = Math.min(freqData.length - 1, i0 + 1);
          const frac = bin - i0;
          const v = (freqData[i0] * (1 - frac) + freqData[i1] * frac) / 255;
          ctx.lineTo(x, h - v * (h - 8) - 4);
        }
        ctx.lineTo(w, h);
        ctx.closePath();
        const grad = ctx.createLinearGradient(0, 0, 0, h);
        grad.addColorStop(0, 'rgba(79,195,247,0.55)');
        grad.addColorStop(1, 'rgba(79,195,247,0.06)');
        ctx.fillStyle = grad;
        ctx.fill();
        ctx.strokeStyle = 'rgba(79,195,247,0.9)';
        ctx.stroke();
      } else {
        ctx.fillStyle = 'rgba(255,255,255,0.35)';
        ctx.font = '12px system-ui, sans-serif';
        ctx.fillText('No audio — start a capture to see the spectrum', 12, 20);
      }

      // Band overlays
      const bands = state.bands;
      mappingsRef.current.forEach((m, idx) => {
        if (!m.enabled) return;
        const color = BAND_COLORS[idx % BAND_COLORS.length];
        const x0 = xForFreq(m.lowHz);
        const x1 = xForFreq(m.highHz);
        ctx.fillStyle = withAlpha(color, 0.10);
        ctx.fillRect(x0, 0, x1 - x0, h);
        ctx.strokeStyle = withAlpha(color, 0.8);
        ctx.lineWidth = 1;
        ctx.strokeRect(x0 + 0.5, 0.5, x1 - x0 - 1, h - 1);

        const band = bands.find((b) => b.id === m.id);
        if (band) {
          const y = h - band.smoothed * (h - 8) - 4;
          ctx.strokeStyle = color;
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.moveTo(x0, y);
          ctx.lineTo(x1, y);
          ctx.stroke();
        }
      });
    };

    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [stateRef]);

  return <canvas ref={canvasRef} className="spectrum-canvas" />;
}

function withAlpha(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

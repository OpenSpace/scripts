import { useLiveBandValue, type EngineState } from '../hooks/useFftEngine';
import { BAND_COLORS, type BandMapping } from '../lib/types';

interface Props {
  mappings: BandMapping[];
  stateRef: { current: EngineState };
  onChange: (mappings: BandMapping[]) => void;
  onBrowse: (mappingId: string) => void;
}

export function MappingList({ mappings, stateRef, onChange, onBrowse }: Props): React.ReactElement {
  const update = (id: string, patch: Partial<BandMapping>): void => {
    onChange(mappings.map((m) => (m.id === id ? { ...m, ...patch } : m)));
  };

  const remove = (id: string): void => {
    onChange(mappings.filter((m) => m.id !== id));
  };

  const add = (): void => {
    const mapping: BandMapping = {
      id: `band-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`,
      enabled: true,
      property: '',
      lowHz: 100,
      highHz: 1000,
      min: 0,
      max: 1
    };
    onChange([...mappings, mapping]);
  };

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Band → property mappings</h2>
        <button onClick={add}>Add mapping</button>
      </div>
      {mappings.length === 0 && (
        <p className="hint">No mappings yet — add one to map a frequency band to a property.</p>
      )}
      <div className="mapping-list">
        {mappings.map((m, idx) => (
          <MappingRow
            key={m.id}
            mapping={m}
            color={BAND_COLORS[idx % BAND_COLORS.length]}
            stateRef={stateRef}
            onUpdate={(patch) => update(m.id, patch)}
            onRemove={() => remove(m.id)}
            onBrowse={() => onBrowse(m.id)}
          />
        ))}
      </div>
    </section>
  );
}

interface RowProps {
  mapping: BandMapping;
  color: string;
  stateRef: { current: EngineState };
  onUpdate: (patch: Partial<BandMapping>) => void;
  onRemove: () => void;
  onBrowse: () => void;
}

function MappingRow({ mapping, color, stateRef, onUpdate, onRemove, onBrowse }: RowProps): React.ReactElement {
  const band = useLiveBandValue(stateRef, mapping.id);
  const num = (v: string): number => Number(v);

  return (
    <div className={`mapping-row ${mapping.enabled ? '' : 'disabled'}`}>
      <div className="mapping-head">
        <input
          type="checkbox"
          checked={mapping.enabled}
          onChange={(e) => onUpdate({ enabled: e.target.checked })}
          title="Enable this mapping"
        />
        <span className="swatch" style={{ background: color }} />
        <input
          className="uri-input"
          type="text"
          value={mapping.property}
          placeholder="Property URI (e.g. Scene.Sun.Renderable.Layers.Sun.Sun.Gamma)"
          onChange={(e) => onUpdate({ property: e.target.value })}
        />
        <button onClick={onBrowse} title="Browse the OpenSpace property tree">
          Browse…
        </button>
        <span className="live-value" title="Current mapped value">
          {band ? band.value.toFixed(3) : '—'}
        </span>
        <button className="danger" onClick={onRemove} title="Remove mapping">
          ✕
        </button>
      </div>
      <div className="mapping-params">
        <label>
          From (Hz)
          <input
            type="number"
            min={1}
            value={mapping.lowHz}
            onChange={(e) => onUpdate({ lowHz: num(e.target.value) })}
          />
        </label>
        <label>
          To (Hz)
          <input
            type="number"
            min={1}
            value={mapping.highHz}
            onChange={(e) => onUpdate({ highHz: num(e.target.value) })}
          />
        </label>
        <label>
          Min
          <input
            type="number"
            step="any"
            value={mapping.min}
            onChange={(e) => onUpdate({ min: num(e.target.value) })}
          />
        </label>
        <label>
          Max
          <input
            type="number"
            step="any"
            value={mapping.max}
            onChange={(e) => onUpdate({ max: num(e.target.value) })}
          />
        </label>
        <div className="band-meter" title="Smoothed band energy">
          <div
            className="band-meter-fill"
            style={{ width: `${(band?.smoothed ?? 0) * 100}%`, background: color }}
          />
        </div>
      </div>
    </div>
  );
}

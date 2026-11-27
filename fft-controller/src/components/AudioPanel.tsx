import type { CaptureSource } from '../lib/audio';

interface Props {
  devices: MediaDeviceInfo[];
  deviceId: string;
  running: boolean;
  mode: CaptureSource | null;
  error: string | null;
  onDevicesChange: (deviceId: string) => void;
  onRefreshDevices: () => void;
  onStartDevice: () => void;
  onStartSystem: () => void;
  onStop: () => void;
}

export function AudioPanel({
  devices,
  deviceId,
  running,
  mode,
  error,
  onDevicesChange,
  onRefreshDevices,
  onStartDevice,
  onStartSystem,
  onStop
}: Props): React.ReactElement {
  return (
    <section className="panel">
      <h2>Audio</h2>
      <div className="row">
        <label className="grow">
          Input device
          <select value={deviceId} onChange={(e) => onDevicesChange(e.target.value)}>
            <option value="">(default input)</option>
            {devices.map((d) => (
              <option key={d.deviceId} value={d.deviceId}>
                {d.label || `Audio input ${d.deviceId.slice(0, 8)}`}
              </option>
            ))}
          </select>
        </label>
        <button onClick={onRefreshDevices} title="Re-enumerate audio input devices">
          Refresh
        </button>
      </div>
      <div className="row">
        {running ? (
          <button className="danger" onClick={onStop}>
            Stop capture
          </button>
        ) : (
          <>
            <button onClick={onStartDevice}>Start (input device)</button>
            <button onClick={onStartSystem} title="Captures system audio via the screen picker">
              Start (system audio)
            </button>
          </>
        )}
      </div>
      <div className={`status ${running ? 'status-connected' : 'status-disconnected'}`}>
        <span className="dot" />
        {running
          ? mode === 'system'
            ? 'Capturing system audio'
            : 'Capturing input device'
          : 'No capture running'}
      </div>
      {error && <p className="error">{error}</p>}
      <p className="hint">
        To drive OpenSpace from what you <em>hear</em>, capture the system output: either pick a
        loopback input such as <strong>Stereo Mix</strong> (Windows), or use{' '}
        <strong>Start (system audio)</strong> and choose “Entire screen” in the picker.
      </p>
    </section>
  );
}

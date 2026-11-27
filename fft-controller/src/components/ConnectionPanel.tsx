import type { OsStatus } from '../lib/types';

interface Props {
  address: string;
  port: number;
  status: OsStatus;
  onAddressChange: (address: string) => void;
  onPortChange: (port: number) => void;
  onConnect: () => void;
  onDisconnect: () => void;
}

export function ConnectionPanel({
  address,
  port,
  status,
  onAddressChange,
  onPortChange,
  onConnect,
  onDisconnect
}: Props): React.ReactElement {
  const connected = status === 'connected';

  return (
    <section className="panel">
      <h2>OpenSpace</h2>
      <div className="row">
        <label>
          Host
          <input
            type="text"
            value={address}
            disabled={status !== 'disconnected'}
            onChange={(e) => onAddressChange(e.target.value)}
          />
        </label>
        <label>
          Port
          <input
            type="number"
            value={port}
            disabled={status !== 'disconnected'}
            onChange={(e) => onPortChange(Number(e.target.value))}
          />
        </label>
        {connected ? (
          <button className="danger" onClick={onDisconnect}>
            Disconnect
          </button>
        ) : (
          <button onClick={onConnect} disabled={status === 'connecting'}>
            {status === 'connecting' ? 'Connecting…' : 'Connect'}
          </button>
        )}
      </div>
      <div className={`status status-${status}`}>
        <span className="dot" />
        {status === 'connected'
          ? `Connected to ${address}:${port}`
          : status === 'connecting'
            ? 'Connecting…'
            : 'Disconnected'}
      </div>
      {!connected && (
        <p className="hint">
          OpenSpace must be running with its WebSocket server interface enabled (default port
          4682, see the <code>Server</code> section of <code>openspace.cfg</code>).
        </p>
      )}
    </section>
  );
}

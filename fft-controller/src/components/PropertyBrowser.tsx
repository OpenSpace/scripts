import { useEffect, useMemo, useState } from 'react';
import type { OpenSpaceClient } from '../lib/openspace';
import { NUMERIC_PROPERTY_TYPES } from '../lib/types';

const MAX_ROWS = 500;

interface Props {
  client: OpenSpaceClient;
  /** Pre-filled URI (the mapping's current value) */
  initialUri: string;
  onPick: (uri: string) => void;
  onClose: () => void;
}

/**
 * Modal that lists the numeric properties of the live OpenSpace property
 * tree (streamed via the `propertyTree` topic) so the user can pick a
 * property URI for a mapping.
 */
export function PropertyBrowser({ client, initialUri, onPick, onClose }: Props): React.ReactElement {
  const [query, setQuery] = useState('');
  const [uri, setUri] = useState(initialUri);
  const [version, setVersion] = useState(client.version);

  useEffect(() => client.onPropertiesChange(() => setVersion(client.version)), [client]);

  const { total, shown } = useMemo(() => {
    const numeric = [...client.properties.values()].filter((p) =>
      NUMERIC_PROPERTY_TYPES.has(p.type)
    );
    const q = query.trim().toLowerCase();
    const filtered = q ? numeric.filter((p) => p.uri.toLowerCase().includes(q)) : numeric;
    return { total: filtered.length, shown: filtered.slice(0, MAX_ROWS) };
    // `version` changes whenever the property snapshot updates.
  }, [client, query, version]);

  const pick = (candidate: string): void => {
    onPick(candidate.trim());
    onClose();
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Pick a property</h2>
          <button className="danger" onClick={onClose}>
            ✕
          </button>
        </div>
        <p className="hint">
          Numeric properties from the live property tree ({total}
          {query ? ' matching' : ''}). The tree streams in — wait a moment after connecting if the
          list is short.
        </p>
        <input
          className="grow"
          type="search"
          placeholder="Filter by URI substring…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoFocus
        />
        <div className="property-list">
          {shown.map((p) => (
            <button
              key={p.uri}
              className="property-row"
              onClick={() => pick(p.uri)}
              title={p.type}
            >
              <span className="property-uri">{p.uri}</span>
              <span className="property-value">
                {p.value === undefined ? '…' : String(p.value)}
              </span>
            </button>
          ))}
          {shown.length === 0 && <p className="hint">No numeric properties found.</p>}
          {total > shown.length && (
            <p className="hint">
              Showing {shown.length} of {total} — refine the filter to narrow the list.
            </p>
          )}
        </div>
        <div className="modal-footer">
          <input
            className="grow"
            type="text"
            value={uri}
            placeholder="…or type a property URI"
            onChange={(e) => setUri(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && uri.trim()) pick(uri);
            }}
          />
          <button onClick={() => pick(uri)} disabled={!uri.trim()}>
            Use URI
          </button>
        </div>
      </div>
    </div>
  );
}

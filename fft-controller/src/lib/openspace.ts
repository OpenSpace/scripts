/**
 * Thin wrapper around `openspace-api-js` (the OpenSpace JavaScript API).
 *
 * The browser build of the library connects to OpenSpace's WebSocket
 * interface (port 4682 by default). This wrapper adds:
 *
 *  - status tracking (disconnected / connecting / connected)
 *  - a live snapshot of the property tree:
 *      * initial full tree via the `get` topic with `__rootOwner`
 *        (the `propertyTree` subscription topic only streams *changes*,
 *        it never sends an initial dump)
 *      * live value updates via the `propertyTree` subscription
 *    so the UI can browse and pick properties
 *  - `setValues()`, which batches all property writes of one update tick
 *    into a single Lua script. OpenSpace's `set` topic is one-shot
 *    (`SetPropertyTopic::isDone()` returns true), so batching keeps the
 *    message rate at one topic per tick instead of two messages per
 *    property per tick.
 */
import openspaceApi from 'openspace-api-js';
import type { OpenSpaceApi } from 'openspace-api-js/api';
import type { OsStatus, PropertyInfo } from './types';

/** A node of the property-owner tree as returned by `get __rootOwner`. */
interface OwnerNode {
  uri: string;
  properties?: Array<{
    uri: string;
    metaData?: { type?: string };
    value?: unknown;
  }>;
  subowners?: OwnerNode[];
}

function flattenOwner(owner: OwnerNode, map: Map<string, PropertyInfo>): void {
  for (const p of owner.properties ?? []) {
    map.set(p.uri, {
      uri: p.uri,
      type: p.metaData?.type ?? 'unknown',
      value: p.value
    });
  }
  for (const sub of owner.subowners ?? []) {
    flattenOwner(sub, map);
  }
}

export class OpenSpaceClient {
  readonly address: string;
  readonly port: number;

  private api: OpenSpaceApi;
  private _status: OsStatus = 'disconnected';
  private _properties = new Map<string, PropertyInfo>();
  private _version = 0;
  private _snapshotLoaded = false;
  private _statusListeners = new Set<() => void>();
  private _propertyListeners = new Set<() => void>();
  private _treeTopic: ReturnType<OpenSpaceApi['startTopic']> | null = null;
  private _notifyScheduled = false;

  constructor(address: string, port: number) {
    this.address = address;
    this.port = port;
    this.api = openspaceApi(address, port);

    this.api.onConnect(() => {
      this._setStatus('connected');
      void this.loadSnapshot();
      this.startPropertyTree();
    });
    this.api.onDisconnect(() => {
      this._treeTopic?.cancel();
      this._treeTopic = null;
      this._properties.clear();
      this._snapshotLoaded = false;
      this._version++;
      this._notifyProperties();
      this._setStatus('disconnected');
    });
  }

  get status(): OsStatus {
    return this._status;
  }

  /** True once the initial `__rootOwner` snapshot has been received. */
  get snapshotLoaded(): boolean {
    return this._snapshotLoaded;
  }

  /** Snapshot of all properties seen so far (uri -> info). */
  get properties(): ReadonlyMap<string, PropertyInfo> {
    return this._properties;
  }

  /** Increments whenever the property snapshot changes (throttled). */
  get version(): number {
    return this._version;
  }

  onStatusChange(cb: () => void): () => void {
    this._statusListeners.add(cb);
    return () => this._statusListeners.delete(cb);
  }

  onPropertiesChange(cb: () => void): () => void {
    this._propertyListeners.add(cb);
    return () => this._propertyListeners.delete(cb);
  }

  connect(): void {
    if (this._status !== 'disconnected') {
      return;
    }
    this._setStatus('connecting');
    this.api.connect();
  }

  disconnect(): void {
    this.api.disconnect();
  }

  /**
   * Write several numeric properties in a single Lua script (one topic).
   * No-op when `entries` is empty.
   */
  setValues(entries: ReadonlyArray<{ property: string; value: number }>): void {
    if (entries.length === 0) {
      return;
    }
    const lines = entries.map(
      (e) =>
        `openspace.setPropertyValueSingle(${JSON.stringify(e.property)}, ${Number(e.value).toFixed(6)})`
    );
    // Fire and forget: no return value, so the topic is closed immediately.
    void this.api.executeLuaScript(lines.join('\n'), false);
  }

  /**
   * Fetch the full property tree in one message (`get __rootOwner`) and
   * flatten it into the uri -> info map.
   */
  private async loadSnapshot(): Promise<void> {
    try {
      const res = await this.api.getProperty('__rootOwner');
      if (res.type === 'propertyOwner') {
        const map = new Map<string, PropertyInfo>();
        flattenOwner(res.value as unknown as OwnerNode, map);
        // Merge: keep live updates that arrived while the snapshot was in flight.
        for (const [uri, info] of map) {
          const existing = this._properties.get(uri);
          this._properties.set(
            uri,
            existing ? { ...info, value: existing.value ?? info.value } : info
          );
        }
        this._snapshotLoaded = true;
        this._version++;
        this._notifyProperties();
      }
    } catch (e) {
      console.error('Failed to load property snapshot:', e);
    }
  }

  /**
   * Subscribe to live property changes. Note: this topic only sends
   * `value`/`metaData` messages when a property *changes* — the initial
   * tree comes from `loadSnapshot()`.
   */
  private startPropertyTree(): void {
    const topic = this.api.startTopic(
      'propertyTree',
      { event: 'start_subscription' },
      { event: 'stop_subscription' }
    );
    this._treeTopic = topic;

    void (async () => {
      try {
        for await (const data of topic) {
          if (data.type === 'metaData') {
            const existing = this._properties.get(data.uri);
            this._properties.set(data.uri, {
              uri: data.uri,
              type: data.metaData.type,
              value: existing?.value
            });
          } else {
            const existing = this._properties.get(data.uri);
            if (existing) {
              existing.value = data.value;
            } else {
              this._properties.set(data.uri, {
                uri: data.uri,
                type: 'unknown',
                value: data.value
              });
            }
          }
          this._schedulePropertyNotify();
        }
      } catch {
        // Topic cancelled or connection lost — nothing to do.
      }
    })();
  }

  private _setStatus(status: OsStatus): void {
    if (this._status === status) {
      return;
    }
    this._status = status;
    this._statusListeners.forEach((cb) => cb());
  }

  /**
   * Property-tree messages can arrive in large bursts; coalesce the React
   * notifications to at most ~4 per second.
   */
  private _schedulePropertyNotify(): void {
    if (this._notifyScheduled) {
      return;
    }
    this._notifyScheduled = true;
    setTimeout(() => {
      this._notifyScheduled = false;
      this._version++;
      this._notifyProperties();
    }, 250);
  }

  private _notifyProperties(): void {
    this._propertyListeners.forEach((cb) => cb());
  }
}

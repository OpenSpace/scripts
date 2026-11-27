import { useCallback, useEffect, useRef, useState } from 'react';
import { AudioPanel } from './components/AudioPanel';
import { ConnectionPanel } from './components/ConnectionPanel';
import { MappingList } from './components/MappingList';
import { PropertyBrowser } from './components/PropertyBrowser';
import { SpectrumView } from './components/SpectrumView';
import { createEngineState, useFftEngine } from './hooks/useFftEngine';
import { AudioCapture, type CaptureSource } from './lib/audio';
import { OpenSpaceClient } from './lib/openspace';
import type { BandMapping, OsStatus } from './lib/types';

const STORAGE_KEY = 'fft-controller.mappings.v1';
const SETTINGS_KEY = 'fft-controller.settings.v1';

function defaultMappings(): BandMapping[] {
  // Property URIs verified against a running OpenSpace (master, v0.22.x).
  return [
    {
      id: 'band-bass',
      enabled: true,
      property: 'RenderEngine.Gamma',
      lowHz: 20,
      highHz: 250,
      min: 0.5,
      max: 1.4
    },
    {
      id: 'band-mids',
      enabled: true,
      property: 'Scene.Sun.Renderable.Opacity',
      lowHz: 250,
      highHz: 2000,
      min: 0.3,
      max: 1
    },
    {
      id: 'band-highs',
      enabled: true,
      property: 'Scene.SloanDigitalSkySurvey.Renderable.Opacity',
      lowHz: 2000,
      highHz: 8000,
      min: 0.2,
      max: 1
    }
  ];
}

function loadMappings(): BandMapping[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as BandMapping[];
      if (Array.isArray(parsed)) {
        return parsed;
      }
    }
  } catch {
    // fall through to defaults
  }
  return defaultMappings();
}

interface Settings {
  address: string;
  port: number;
  updateRateHz: number;
  smoothing: number;
}

function loadSettings(): Settings {
  const fallback: Settings = { address: 'localhost', port: 4682, updateRateHz: 30, smoothing: 0.5 };
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (raw) {
      return { ...fallback, ...(JSON.parse(raw) as Partial<Settings>) };
    }
  } catch {
    // fall through to defaults
  }
  return fallback;
}

export default function App(): React.ReactElement {
  const initial = useRef(loadSettings());
  const [address, setAddress] = useState(initial.current.address);
  const [port, setPort] = useState(initial.current.port);
  const [client, setClient] = useState<OpenSpaceClient>(
    () => new OpenSpaceClient(initial.current.address, initial.current.port)
  );
  const [status, setStatus] = useState<OsStatus>(client.status);

  const [mappings, setMappings] = useState<BandMapping[]>(loadMappings);
  const [updateRateHz, setUpdateRateHz] = useState(initial.current.updateRateHz);
  const [smoothing, setSmoothing] = useState(initial.current.smoothing);

  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [deviceId, setDeviceId] = useState('');
  const [captureRunning, setCaptureRunning] = useState(false);
  const [captureMode, setCaptureMode] = useState<CaptureSource | null>(null);
  const [audioError, setAudioError] = useState<string | null>(null);

  const [browseTarget, setBrowseTarget] = useState<string | null>(null);

  const captureRef = useRef<AudioCapture | null>(null);
  if (!captureRef.current) {
    captureRef.current = new AudioCapture();
  }
  const stateRef = useRef(createEngineState());

  // Persist mappings + settings
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(mappings));
  }, [mappings]);
  useEffect(() => {
    localStorage.setItem(
      SETTINGS_KEY,
      JSON.stringify({ address, port, updateRateHz, smoothing } satisfies Settings)
    );
  }, [address, port, updateRateHz, smoothing]);

  // Track client status
  useEffect(() => {
    const off = client.onStatusChange(() => setStatus(client.status));
    setStatus(client.status);
    return off;
  }, [client]);

  // The core engine loop
  useFftEngine({
    capture: captureRef.current,
    client,
    mappings,
    updateRateHz,
    smoothing,
    stateRef,
    enabled: captureRunning
  });

  const handleConnect = useCallback((): void => {
    const c = new OpenSpaceClient(address, port);
    setClient(c);
    c.connect();
  }, [address, port]);

  const handleDisconnect = useCallback((): void => {
    client.disconnect();
  }, [client]);

  const refreshDevices = useCallback(async (): Promise<void> => {
    try {
      // Requesting permission first makes device labels available.
      const tmp = await navigator.mediaDevices.getUserMedia({ audio: true });
      tmp.getTracks().forEach((t) => t.stop());
      const list = await navigator.mediaDevices.enumerateDevices();
      setDevices(list.filter((d) => d.kind === 'audioinput'));
    } catch (e) {
      const list = await navigator.mediaDevices.enumerateDevices();
      setDevices(list.filter((d) => d.kind === 'audioinput'));
      setAudioError(`Could not enumerate devices with permission: ${String(e)}`);
    }
  }, []);

  const stopCapture = useCallback((): void => {
    captureRef.current?.stop();
    setCaptureRunning(false);
    setCaptureMode(null);
  }, []);

  const startDevice = useCallback(async (): Promise<void> => {
    setAudioError(null);
    try {
      await captureRef.current?.startDevice(deviceId);
      setCaptureRunning(true);
      setCaptureMode('device');
    } catch (e) {
      setAudioError(`Failed to start device capture: ${String(e)}`);
    }
  }, [deviceId]);

  const startSystem = useCallback(async (): Promise<void> => {
    setAudioError(null);
    try {
      const capture = captureRef.current;
      if (!capture) return;
      capture.onEnded = stopCapture;
      await capture.startSystem();
      setCaptureRunning(true);
      setCaptureMode('system');
    } catch (e) {
      setAudioError(`Failed to start system audio capture: ${String(e)}`);
    }
  }, [stopCapture]);

  // Clean up audio on unmount
  useEffect(() => {
    const capture = captureRef.current;
    return () => {
      capture?.stop();
      client.disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const browseMapping = browseTarget !== null ? mappings.find((m) => m.id === browseTarget) : null;

  return (
    <div className="app">
      <header className="app-header">
        <h1>
          OpenSpace <span className="accent">FFT Controller</span>
        </h1>
        <div className="header-controls">
          <label>
            Update rate (Hz)
            <input
              type="number"
              min={1}
              max={60}
              value={updateRateHz}
              onChange={(e) => setUpdateRateHz(Math.max(1, Math.min(60, Number(e.target.value))))}
            />
          </label>
          <label>
            Response
            <input
              type="range"
              min={0}
              max={1}
              step={0.01}
              value={smoothing}
              onChange={(e) => setSmoothing(Number(e.target.value))}
              title="Low = slow/smooth, high = instant"
            />
          </label>
        </div>
      </header>

      <div className="layout">
        <div className="column">
          <ConnectionPanel
            address={address}
            port={port}
            status={status}
            onAddressChange={setAddress}
            onPortChange={setPort}
            onConnect={handleConnect}
            onDisconnect={handleDisconnect}
          />
          <AudioPanel
            devices={devices}
            deviceId={deviceId}
            running={captureRunning}
            mode={captureMode}
            error={audioError}
            onDevicesChange={setDeviceId}
            onRefreshDevices={() => void refreshDevices()}
            onStartDevice={() => void startDevice()}
            onStartSystem={() => void startSystem()}
            onStop={stopCapture}
          />
          <section className="panel">
            <h2>Spectrum</h2>
            <SpectrumView stateRef={stateRef} mappings={mappings} />
          </section>
        </div>
        <div className="column">
          <MappingList
            mappings={mappings}
            stateRef={stateRef}
            onChange={setMappings}
            onBrowse={setBrowseTarget}
          />
        </div>
      </div>

      {browseMapping && (
        <PropertyBrowser
          client={client}
          initialUri={browseMapping.property}
          onPick={(uri) =>
            setMappings((ms) => ms.map((m) => (m.id === browseTarget ? { ...m, property: uri } : m)))
          }
          onClose={() => setBrowseTarget(null)}
        />
      )}
    </div>
  );
}

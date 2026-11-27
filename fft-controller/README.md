# OpenSpace FFT Controller

A TypeScript + Vite + React app that captures the output of a system audio
device, runs an FFT on it (via the Web Audio `AnalyserNode`), and drives
OpenSpace properties from the frequency-band energies — using the
[OpenSpace JavaScript API](../openspace-api-js) (`openspace-api-js`) over
OpenSpace's WebSocket interface.

## How it works

```
audio device ──► Web Audio AnalyserNode (FFT, 8192)
                        │
                        ▼
        per-band energy (0..1)  ──►  smoothing (EMA)
                        │
                        ▼
        linear map onto [min, max] per mapping
                        │
                        ▼
   one batched Lua script per tick ──► OpenSpace (ws://host:4682)
   openspace.setPropertyValueSingle("URI", value)  (×N mappings)
```

- **Capturing system audio.** Browsers cannot read the audio *output*
  directly, so the app offers two capture paths:
  1. **Input device** — pick a loopback input such as Windows
     *Stereo Mix* (or any loopback device) in the device dropdown.
  2. **System audio** — `getDisplayMedia({ video: false, audio: true })`;
     choose *Entire screen* in the picker to capture all system audio (or a
     specific window to capture only that window).
- **FFT.** The `AnalyserNode` (fftSize 8192, `smoothingTimeConstant = 0`)
  produces raw byte frequency data; each mapping averages the bins inside
  its `[lowHz, highHz]` range and normalizes to 0..1.
- **Mappings.** Each mapping is `{ property URI, lowHz, highHz, min, max }`.
  The smoothed band energy is mapped linearly: `value = min + t·(max − min)`.
  Mappings persist in `localStorage`.
- **Property browser.** After connecting, the app fetches the full property
  tree in one message (`get` topic with `__rootOwner`) and keeps a
  `propertyTree` subscription open for live value updates (that topic only
  streams *changes*, no initial dump). *Browse…* lists every numeric
  property (Float/Double/Int/…) with its current value.
- **Batching.** OpenSpace's `set` topic is one-shot
  (`SetPropertyTopic::isDone()` returns `true`), so instead of one topic per
  property per tick, all enabled mappings are written in a single Lua script
  per update tick (`executeLuaScript` without a return value) — one topic
  per tick.

## Prerequisites

- OpenSpace running with its WebSocket server interface enabled. The default
  `openspace.cfg` on this machine already has it:

  ```lua
  Server = {
    Interfaces = {
      { Type = "WebSocket", Port = 4682, Enabled = true,
        AllowAddresses = { "127.0.0.1", "localhost" }, ... },
      ...
    }
  }
  ```

- Node.js ≥ 20.

## Run

```sh
npm install
npm run dev        # http://localhost:5173
```

1. Click **Connect** (defaults to `localhost:4682`).
2. Start an audio capture (Stereo Mix device or *Start (system audio)*).
3. For each mapping, pick a property via **Browse…** (or type the URI), set
   the band range and min/max.
4. Play some audio — the spectrum shows the bands, and the property values
   follow.

## Verify the OpenSpace link without the browser

```sh
npm run smoke-test
```

Connects over TCP (port 4681, same topic protocol), lists numeric
properties, and round-trips a value through the exact batched Lua path the
app uses (setting, reading back, restoring).

## Build

```sh
npm run build      # tsc -b && vite build → dist/
```

## Layout

```
src/
  lib/
    audio.ts        AudioCapture: getUserMedia / getDisplayMedia + AnalyserNode
    openspace.ts    OpenSpaceClient: status, property-tree snapshot, batched set
    spectrum.ts     band energy + range mapping
    types.ts        BandMapping, property types, colors
  hooks/
    useFftEngine.ts rAF engine loop + shared mutable EngineState
  components/
    ConnectionPanel.tsx  host/port + connect
    AudioPanel.tsx       device picker + capture controls
    MappingList.tsx      band→property mapping rows
    PropertyBrowser.tsx  live property-tree picker (modal)
    SpectrumView.tsx     canvas spectrum with band overlays
scripts/
  smoke-test.cjs    Node/TCP protocol test against a running OpenSpace
```

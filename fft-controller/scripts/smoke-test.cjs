/**
 * Smoke test for the OpenSpace connection path used by the FFT controller.
 *
 * Runs in Node against OpenSpace's TCP interface (port 4681 by default) —
 * the same topic protocol the browser app uses over WebSocket (4682).
 *
 *  1. connect + handshake
 *  2. read the version
 *  3. fetch the property-tree snapshot (`get __rootOwner`) and list
 *     numeric properties
 *  4. round-trip a value through the batched Lua path the app uses
 *     (openspace.setPropertyValueSingle), then restore the original value
 *
 * Usage:
 *   node scripts/smoke-test.cjs
 *   OPENSPACE_HOST=... OPENSPACE_PORT=... node scripts/smoke-test.cjs
 *
 * Note: CJS on purpose — the package's ESM build uses extensionless imports
 * that only resolve through a bundler; the CJS build works in raw Node.
 */
const openspaceApi = require('openspace-api-js').default;

const address = process.env.OPENSPACE_HOST ?? 'localhost';
const port = Number(process.env.OPENSPACE_PORT ?? 4681);

const NUMERIC_TYPES = new Set([
  'FloatProperty',
  'DoubleProperty',
  'IntProperty',
  'LongProperty',
  'ShortProperty',
  'UIntProperty',
  'ULongProperty',
  'UShortProperty'
]);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (...a) => console.log('[smoke]', ...a);

const api = openspaceApi(address, port);
let exitCode = 0;
let finishing = false;
let watchdog;

const finish = () => {
  finishing = true;
  try {
    api.disconnect();
  } catch {
    // ignore
  }
  process.exit(exitCode);
};

api.onConnect(async () => {
  clearTimeout(watchdog);
  log('connected to', address, port);
  try {
    // 1. version
    const version = await api.executeLuaScript('return openspace.version()');
    log('version:', JSON.stringify(version));

    // 2. property tree snapshot (get __rootOwner — the propertyTree
    //    subscription topic only streams changes, no initial dump)
    const t0 = Date.now();
    const res = await api.getProperty('__rootOwner');
    if (res.type !== 'propertyOwner') {
      throw new Error(`unexpected get response type: ${res.type}`);
    }
    const props = new Map();
    const walk = (o) => {
      for (const p of o.properties ?? []) {
        props.set(p.uri, { uri: p.uri, type: p.metaData?.type, value: p.value });
      }
      for (const s of o.subowners ?? []) walk(s);
    };
    walk(res.value);
    log(`fetched property tree in ${Date.now() - t0} ms: ${props.size} properties`);

    const numeric = [...props.values()].filter(
      (p) => NUMERIC_TYPES.has(p.type) && typeof p.value === 'number'
    );
    log(`numeric properties with numeric values: ${numeric.length}`);
    for (const p of numeric.slice(0, 20)) {
      log('  ', p.type.padEnd(14), p.uri, '=', p.value);
    }

    if (numeric.length === 0) {
      throw new Error('no numeric properties found — cannot test set path');
    }

    // 3. round-trip through the batched Lua path the app uses
    const target = numeric.find((p) => /Gamma|Multiplier|Offset/.test(p.uri)) ?? numeric[0];
    const original = target.value;
    const testValue = original + 0.25;

    const script = `openspace.setPropertyValueSingle(${JSON.stringify(
      target.uri
    )}, ${testValue.toFixed(6)})`;
    await api.executeLuaScript(script, false);
    await sleep(500);

    const got = await api.getProperty(target.uri);
    const gotValue = got.type === 'property' ? got.value.value : null;
    log('after set:', target.uri, '->', gotValue, '(expected', testValue + ')');
    if (typeof gotValue !== 'number' || Math.abs(gotValue - testValue) > 1e-6) {
      log('MISMATCH');
      exitCode = 1;
    } else {
      log('set/get round-trip OK');
    }

    // 4. restore
    await api.setProperty(target.uri, original);
    await sleep(300);
    const restored = await api.getProperty(target.uri);
    const restoredValue = restored.type === 'property' ? restored.value.value : null;
    log('restored:', target.uri, '->', restoredValue, '(original', original + ')');
    if (typeof restoredValue !== 'number' || Math.abs(restoredValue - original) > 1e-6) {
      log('RESTORE MISMATCH');
      exitCode = 1;
    }
  } catch (e) {
    log('ERROR:', e instanceof Error ? e.message : e);
    exitCode = 1;
  } finally {
    finish();
  }
});

api.onDisconnect(() => {
  if (!finishing) {
    log('disconnected unexpectedly');
    process.exit(1);
  }
});

api.connect();

watchdog = setTimeout(() => {
  log('timed out waiting for connection — is OpenSpace running with its server enabled?');
  process.exit(1);
}, 10000);

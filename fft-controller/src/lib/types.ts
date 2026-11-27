/**
 * A single frequency-band -> property mapping.
 *
 * The (normalized) energy of the FFT band [lowHz, highHz] is mapped linearly
 * onto [min, max] and written to the OpenSpace property `property`.
 */
export interface BandMapping {
  id: string;
  enabled: boolean;
  /** OpenSpace property URI, e.g. `Scene.Sun.Renderable.Layers.Sun.Sun.Gamma` */
  property: string;
  /** Band lower bound in Hz */
  lowHz: number;
  /** Band upper bound in Hz */
  highHz: number;
  /** Property value when the band is silent */
  min: number;
  /** Property value when the band is at full scale */
  max: number;
}

export type OsStatus = 'disconnected' | 'connecting' | 'connected';

/** A property from OpenSpace's property tree (as streamed by the `propertyTree` topic). */
export interface PropertyInfo {
  uri: string;
  /** Property type name, e.g. `FloatProperty`, `DoubleProperty`, `IntProperty` */
  type: string;
  /** Current value (may be undefined until the value message arrives) */
  value: unknown;
}

/** Property types that hold a single number and can be driven by a band. */
export const NUMERIC_PROPERTY_TYPES: ReadonlySet<string> = new Set([
  'FloatProperty',
  'DoubleProperty',
  'IntProperty',
  'LongProperty',
  'ShortProperty',
  'UIntProperty',
  'ULongProperty',
  'UShortProperty'
]);

/** Colors used for the spectrum band overlays, one per mapping (cycled). */
export const BAND_COLORS: readonly string[] = [
  '#4fc3f7',
  '#ffb74d',
  '#81c784',
  '#f06292',
  '#ba68c8',
  '#fff176',
  '#4db6ac',
  '#ff8a65'
];

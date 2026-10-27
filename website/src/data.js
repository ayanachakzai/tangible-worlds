// Recorded project data used by the interactive chapters.
// Sources are named beside each block; nothing here is invented.

// phase3-tabletop/rendering/assignments.json — the session filmed in Part 2.2.
// Prop photographs and normalised positions were measured from the tracker RGB
// inset at 4.0 s of that recording (ROI 111..446 x 430..878 px).
export const SESSION = [
  { id: 1, meaning: 'a windmill scale huge', generation: 'a windmill', slug: 'a-windmill', intent: 'very_large', target: 3.0, source: 'participant_marked', prop: 'red box', x: 0.233, y: 0.183 },
  { id: 2, meaning: 'a fire truck', generation: 'a fire truck', slug: 'a-fire-truck', intent: 'neutral', target: 1.0, source: 'neutral_default', prop: 'silver tin', x: 0.680, y: 0.339 },
  { id: 3, meaning: 'a house scale large', generation: 'a house', slug: 'a-house', intent: 'large', target: 1.8, source: 'participant_marked', prop: 'wallet', x: 0.257, y: 0.641 },
  { id: 4, meaning: 'a horse', generation: 'a horse', slug: 'a-horse', intent: 'neutral', target: 1.0, source: 'neutral_default', prop: 'small wallet', x: 0.812, y: 0.616 },
];

// conversation_log.json — the accepted voice assignments of that session.
export const UTTERANCES = {
  1: { said: 'object one is a windmill scale huge', handle: 'object one', meaning: 'a windmill', scale: 'scale huge' },
  2: { said: 'object two is a fire truck', handle: 'object two', meaning: 'a fire truck', scale: null },
  3: { said: 'object three is a house scale large', handle: 'object three', meaning: 'a house', scale: 'scale large' },
  4: { said: 'object four is a horse', handle: 'object four', meaning: 'a horse', scale: null },
};

// serve.py MARKED_SCALE_TARGETS
export const SCALE = {
  tiny: ['very_small', 0.35], miniature: ['very_small', 0.35], small: ['small', 0.65],
  big: ['large', 1.8], large: ['large', 1.8], huge: ['very_large', 3.0],
};

// conversation_log.json — atmosphere commands and the exact 12-field state
// Qwen3-8B returned for each. "make it night" is included because it shows
// the documented partial-execution problem: rain and lightning survived.
export const ATMOSPHERE_COMMANDS = [
  { cmd: 'neutral default', note: 'schema default', m: { sky_elevation: 45, light_elevation: 45, light_azimuth: 45, light_level: 0.65, light_warmth: 0, sky_haze: 0.2, mist_amount: 0, mist_height: 0.35, mist_motion: 0.25, rain_amount: 0, lightning_amount: 0, mood: 'neutral' } },
  { cmd: 'make it a golden hour', note: 'logged', m: { sky_elevation: 12, light_elevation: 65, light_azimuth: 45, light_level: 0.85, light_warmth: 0.75, sky_haze: 0.3, mist_amount: 0, mist_height: 0.35, mist_motion: 0.25, rain_amount: 0, lightning_amount: 0, mood: 'golden hour' } },
  { cmd: 'make it a warm hazy sunset', note: 'logged', m: { sky_elevation: 7, light_elevation: 10, light_azimuth: 45, light_level: 0.85, light_warmth: 0.85, sky_haze: 0.7, mist_amount: 0, mist_height: 0.35, mist_motion: 0.25, rain_amount: 0, lightning_amount: 0, mood: 'warm hazy sunset' } },
  { cmd: 'make it a clear moonlit night', note: 'logged', m: { sky_elevation: -6, light_elevation: 22, light_azimuth: 45, light_level: 0.42, light_warmth: -0.35, sky_haze: 0.1, mist_amount: 0, mist_height: 0.35, mist_motion: 0.25, rain_amount: 0, lightning_amount: 0, mood: 'clear moonlit night' } },
  // Both logged "make it foggy" calls (26 and 30 Aug) returned this same state:
  // mist 0.5, everything else at the neutral default. No production screenshot
  // of this command exists; the rendering is the deterministic mapping, checked
  // against the Phase 5E qualification fog renders.
  { cmd: 'make it foggy', label: 'by day', note: 'logged', m: { sky_elevation: 45, light_elevation: 45, light_azimuth: 45, light_level: 0.65, light_warmth: 0, sky_haze: 0.2, mist_amount: 0.5, mist_height: 0.35, mist_motion: 0.25, rain_amount: 0, lightning_amount: 0, mood: 'foggy' },
    evidence: 'Logged Qwen3-8B output for “make it foggy” said over a daytime scene (26 and 30 Aug, identical): mist 0.5, every other field at its neutral default. Production mist at this level is faint; the dissertation records faint mist as a persistent qualification issue (Fig. 5.22). No production screenshot of this command exists, so this view is the deterministic mapping, matched against the qualification fog renders.' },
  // The same words said over a clear moonlit night (26 Aug 19:42 UTC,
  // conversation_log timestamp 1787773374.73). Qwen kept the night and added
  // mist 0.6; its mood label came back as "foggy moonlit night".
  { cmd: 'make it foggy', label: 'at night', note: 'logged over a moonlit night', m: { sky_elevation: -6, light_elevation: 22, light_azimuth: 45, light_level: 0.42, light_warmth: -0.35, sky_haze: 0.1, mist_amount: 0.6, mist_height: 0.35, mist_motion: 0.25, rain_amount: 0, lightning_amount: 0, mood: 'foggy moonlit night' },
    evidence: 'Logged Qwen3-8B output when “make it foggy” was said over a clear moonlit night (26 Aug): it kept the night (sky below the horizon, light level 0.42, cool key light) and added mist 0.6. No production screenshot exists; the closest reference is the qualification render for “a foggy moonlit night”, whose output differs only in light elevation (15 instead of 22).' },
  { cmd: 'make it a stormy night', note: 'logged', m: { sky_elevation: -6, light_elevation: 15, light_azimuth: 45, light_level: 0.65, light_warmth: -0.35, sky_haze: 0.8, mist_amount: 0.75, mist_height: 0.25, mist_motion: 0.75, rain_amount: 0.8, lightning_amount: 0.5, mood: 'stormy night' } },
  { cmd: 'make it a spooky night', note: 'logged', m: { sky_elevation: -6, light_elevation: 15, light_azimuth: 45, light_level: 0.6, light_warmth: -0.3, sky_haze: 0.4, mist_amount: 0.2, mist_height: 0.25, mist_motion: 0.4, rain_amount: 0, lightning_amount: 0.1, mood: 'spooky night' } },
  { cmd: 'make it sunny', note: 'logged', m: { sky_elevation: 70, light_elevation: 85, light_azimuth: 45, light_level: 0.85, light_warmth: 0.2, sky_haze: 0.1, mist_amount: 0, mist_height: 0.35, mist_motion: 0.25, rain_amount: 0, lightning_amount: 0, mood: 'sunny' } },
  // Standalone "make it night" (typed, 1 Sep 00:50 UTC). The production
  // screenshot captured for this exact state (screenshots/TEST/1788223851…jpg)
  // is reproduced by this renderer: sky (17,21,30), table (43,44,46).
  { cmd: 'make it night', note: 'logged', m: { sky_elevation: -6, light_elevation: 15, light_azimuth: 45, light_level: 0.65, light_warmth: -0.35, sky_haze: 0.1, mist_amount: 0, mist_height: 0.35, mist_motion: 0.25, rain_amount: 0, lightning_amount: 0, mood: 'night' },
    evidence: 'Logged Qwen3-8B output for a standalone “make it night” (1 Sep): sky below the horizon, low cool key light, no rain, no lightning. It matches the production screenshot captured for this state: navy sky, dark grey table, long shadows.' },
  // The same command issued straight after "make it a thunderstorm" (2 Sep).
  // Qwen kept rain and lightning: the partial-execution failure the page cites.
  { cmd: 'make it night', label: 'after a thunderstorm', note: 'logged after a thunderstorm', m: { sky_elevation: -6, light_elevation: 15, light_azimuth: 45, light_level: 0.65, light_warmth: -0.35, sky_haze: 0.1, mist_amount: 0, mist_height: 0.35, mist_motion: 0.25, rain_amount: 1, lightning_amount: 1, mood: 'night' },
    evidence: 'Logged output when “make it night” followed “make it a thunderstorm” (2 Sep): Qwen3-8B kept rain 1.0 and lightning 1.0 from the previous state. This is the state filmed in the opening recording.' },
];

// Final 12-field contract ranges (PROJECT_AUDIT §21.B)
export const FIELDS = [
  ['sky_elevation', -12, 90, 1], ['light_elevation', 0, 90, 1], ['light_azimuth', 0, 360, 1],
  ['light_level', 0, 1, 0.01], ['light_warmth', -1, 1, 0.01], ['sky_haze', 0, 1, 0.01],
  ['mist_amount', 0, 1, 0.01], ['mist_height', 0, 1, 0.01], ['mist_motion', 0, 1, 0.01],
  ['rain_amount', 0, 1, 0.01], ['lightning_amount', 0, 1, 0.01],
];

export const MODELS_GOOD = [
  ['a-lighthouse', 'a lighthouse'], ['a-windmill', 'a windmill'], ['a-fire-truck', 'a fire truck'], ['a-horse', 'a horse'],
  ['a-house', 'a house'], ['a-castle', 'a castle'], ['a-tent', 'a tent'], ['a-dragon', 'a dragon'],
  ['a-truck', 'a truck'], ['a-petrol-station', 'a petrol station'], ['a-stone-cairn', 'a stone cairn'],
  ['a-stone-bridge', 'a stone bridge'], ['a-mountain', 'a mountain'], ['a-car', 'a car'],
];
export const MODELS_WEAK = [
  ['a-gravel-driveway', 'a gravel driveway'], ['a-stone-pathway', 'a stone pathway'], ['a-stone-foundation', 'a stone foundation'],
  ['a-stone-retaining-wall', 'a stone retaining wall'], ['a-cliff', 'a cliff'],
];

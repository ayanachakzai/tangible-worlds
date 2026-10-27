"""
test_atmosphere_schema_deep.py
------------------------------
deep robustness test for the approved atmosphere schema and v2 qwen prompt.

this does not write scene_modifiers.json and does not touch serve.py,
converse.py, index.html, or the tracker. it imports the already tested v2
schema/prompt so this suite cannot silently test a different prompt.

run from phase3-tabletop/conversation:
    python test_atmosphere_schema_deep.py

it saves full evidence to:
    atmosphere_schema_deep_results.json

source basis lives in test_atmosphere_schema_v2.py, where every schema field
has its meaning, range, renderer target, and exact external references.

# ref: https://huggingface.co/Qwen/Qwen3-8B
# ref: https://lmstudio.ai/docs/developer/openai-compat/chat-completions
"""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import test_atmosphere_schema_v2 as base


RESULTS_FILE = Path("atmosphere_schema_deep_results.json")
EXPECTED_BASE_SHA256 = "9ed48c17fa5d6c61078e4d5ae47d8e27ad34774be93484e63912e69a6028aa55"
BASE_FILE = Path(base.__file__)

LIGHTING_FIELDS = [
    "sky_elevation",
    "light_elevation",
    "light_azimuth",
    "light_level",
    "light_warmth",
    "sky_haze",
]
WEATHER_FIELDS = ["mist_amount", "mist_height", "mist_motion", "rain_amount", "lightning_amount"]
ALL_NUMERIC_FIELDS = list(base.RANGES)
ALL_FIELDS = list(base.MODIFIER_SCHEMA)


def state(**changes):
    result = deepcopy(base.MODIFIER_SCHEMA)
    result.update(changes)
    return result


# strict tests only encode meanings that are explicit enough to judge.
# ambiguous aesthetic language is kept in REVIEW_CASES instead of being forced
# into arbitrary numeric expectations.
STRICT_TESTS = [
    # time of day
    {"category": "time", "name": "deep_midnight", "request": "deep midnight, clear and dry", "expect": {"sky_elevation": (-12, -1), "light_level": (0.15, 0.65), "mist_amount": (0, 0.05), "rain_amount": (0, 0.05), "lightning_amount": (0, 0.05)}},
    {"category": "time", "name": "moonlit_night", "request": "a clear moonlit night", "expect": {"sky_elevation": (-12, -0.1), "light_elevation": (5, 45), "light_warmth": (-1, 0.15)}},
    {"category": "time", "name": "predawn", "request": "the blue hour just before dawn", "expect": {"sky_elevation": (-8, 4), "light_elevation": (3, 30), "light_warmth": (-1, 0.2)}},
    {"category": "time", "name": "dawn", "request": "soft dawn light", "expect": {"sky_elevation": (0, 15), "light_elevation": (0, 25)}},
    {"category": "time", "name": "sunrise", "request": "warm sunrise", "expect": {"sky_elevation": (0, 15), "light_elevation": (0, 25), "light_warmth": (0.35, 1)}},
    {"category": "time", "name": "early_morning", "request": "clear early morning", "expect": {"sky_elevation": (8, 40), "light_elevation": (8, 45)}},
    {"category": "time", "name": "noon", "request": "bright clear noon", "expect": {"sky_elevation": (65, 90), "light_elevation": (65, 90), "light_level": (0.65, 1)}},
    {"category": "time", "name": "afternoon", "request": "bright afternoon sunlight", "expect": {"sky_elevation": (35, 80), "light_elevation": (35, 80)}},
    {"category": "time", "name": "golden_hour", "request": "golden hour, warm and clear", "expect": {"sky_elevation": (3, 15), "light_elevation": (3, 20), "light_warmth": (0.5, 1), "sky_haze": (0, 0.55)}},
    {"category": "time", "name": "sunset", "request": "a warm sunset", "expect": {"sky_elevation": (0, 15), "light_elevation": (0, 25), "light_warmth": (0.4, 1)}},
    {"category": "time", "name": "dusk", "request": "cool dusk after the sun has gone down", "expect": {"sky_elevation": (-6, 5), "light_elevation": (3, 30), "light_warmth": (-1, 0.15)}},
    {"category": "time", "name": "evening", "request": "a calm evening just before night", "expect": {"sky_elevation": (-2, 20), "light_elevation": (3, 35)}},

    # direct lighting semantics
    {"category": "lighting", "name": "cold_light", "request": "make the light distinctly colder, keep everything else exactly the same", "current": state(light_warmth=0.45), "expect": {"light_warmth": (-1, -0.15)}, "preserve": [f for f in ALL_FIELDS if f != "light_warmth"]},
    {"category": "lighting", "name": "warm_light", "request": "make the light much warmer, keep everything else exactly the same", "current": state(light_warmth=-0.4), "expect": {"light_warmth": (0.35, 1)}, "preserve": [f for f in ALL_FIELDS if f != "light_warmth"]},
    {"category": "lighting", "name": "long_shadows", "request": "give me much longer raking shadows, keep the time of day and all weather unchanged", "current": state(light_elevation=65, sky_elevation=45, mist_amount=0.3), "expect": {"light_elevation": (0, 25)}, "preserve": ["sky_elevation", "light_azimuth", "light_level", "light_warmth", "sky_haze"] + WEATHER_FIELDS},
    {"category": "lighting", "name": "overhead_light", "request": "move the key light high overhead, keep everything else unchanged", "current": state(light_elevation=12), "expect": {"light_elevation": (70, 90)}, "preserve": [f for f in ALL_FIELDS if f != "light_elevation"]},
    {"category": "lighting", "name": "dim_readable", "request": "make the lighting dimmer but keep the scene readable, change nothing else", "current": state(light_level=0.9), "expect": {"light_level": (0.2, 0.65)}, "preserve": [f for f in ALL_FIELDS if f != "light_level"]},
    {"category": "lighting", "name": "brighter", "request": "make the key light clearly brighter, change nothing else", "current": state(light_level=0.35), "expect": {"light_level": (0.6, 1)}, "preserve": [f for f in ALL_FIELDS if f != "light_level"]},
    {"category": "lighting", "name": "opposite_side", "request": "move the key light to the opposite side of the table, change nothing else", "current": state(light_azimuth=30), "expect": {"light_azimuth": (180, 240)}, "preserve": [f for f in ALL_FIELDS if f != "light_azimuth"]},
    {"category": "lighting", "name": "neutral_overcast", "request": "neutral overcast daylight, no rain", "expect": {"sky_elevation": (25, 75), "light_warmth": (-0.25, 0.25), "sky_haze": (0.45, 1), "rain_amount": (0, 0.05), "lightning_amount": (0, 0.05)}},

    # mist semantics
    {"category": "mist", "name": "thin_ground_mist", "request": "a thin layer of ground-hugging mist", "expect": {"mist_amount": (0.1, 0.5), "mist_height": (0, 0.3)}},
    {"category": "mist", "name": "thick_high_mist", "request": "thick mist reaching high into the scene", "expect": {"mist_amount": (0.65, 1), "mist_height": (0.6, 1)}},
    {"category": "mist", "name": "still_fog", "request": "dense fog with completely still air", "expect": {"mist_amount": (0.55, 1), "mist_motion": (0, 0.12)}},
    {"category": "mist", "name": "fast_drifting_mist", "request": "mist drifting and morphing strongly in the wind", "expect": {"mist_amount": (0.25, 1), "mist_motion": (0.65, 1)}},
    {"category": "mist", "name": "remove_mist", "request": "remove all mist and fog, keep everything else exactly the same", "current": state(mist_amount=0.8, mist_height=0.75, mist_motion=0.8), "exact": {"mist_amount": 0.0}, "preserve": [f for f in ALL_FIELDS if f != "mist_amount"]},
    {"category": "mist", "name": "raise_mist_only", "request": "make the existing mist reach much higher, keep its amount and movement exactly the same and change nothing else", "current": state(mist_amount=0.55, mist_height=0.18, mist_motion=0.42), "expect": {"mist_height": (0.55, 1)}, "preserve": [f for f in ALL_FIELDS if f != "mist_height"]},
    {"category": "mist", "name": "lower_mist_only", "request": "pull the existing mist down close to the ground, keep its density and movement exactly the same", "current": state(mist_amount=0.65, mist_height=0.8, mist_motion=0.35), "expect": {"mist_height": (0, 0.3)}, "preserve": [f for f in ALL_FIELDS if f != "mist_height"]},
    {"category": "mist", "name": "less_and_slower", "request": "make the mist thinner and slower, keep everything else unchanged", "current": state(mist_amount=0.85, mist_motion=0.8), "less_than_current": ["mist_amount", "mist_motion"], "preserve": [f for f in ALL_FIELDS if f not in ("mist_amount", "mist_motion")]},

    # rain and lightning semantics
    {"category": "weather", "name": "light_drizzle", "request": "light drizzle, no lightning", "expect": {"rain_amount": (0.1, 0.45), "lightning_amount": (0, 0.05)}},
    {"category": "weather", "name": "heavy_rain_no_lightning", "request": "heavy rain but absolutely no lightning", "expect": {"rain_amount": (0.7, 1), "lightning_amount": (0, 0.05)}},
    {"category": "weather", "name": "violent_thunderstorm", "request": "a violent thunderstorm with heavy rain and frequent lightning", "expect": {"rain_amount": (0.7, 1), "lightning_amount": (0.65, 1), "sky_haze": (0.25, 1)}},
    {"category": "weather", "name": "dry_lightning", "request": "dry lightning in clear air, no rain", "expect": {"rain_amount": (0, 0.05), "lightning_amount": (0.45, 1)}},
    {"category": "weather", "name": "stop_rain_keep_lightning", "request": "stop the rain completely but keep the lightning exactly as it is and change nothing else", "current": state(rain_amount=0.9, lightning_amount=0.7), "exact": {"rain_amount": 0.0, "lightning_amount": 0.7}, "preserve": [f for f in ALL_FIELDS if f != "rain_amount"]},
    {"category": "weather", "name": "stop_lightning_keep_rain", "request": "stop all lightning but keep the rain exactly as it is and change nothing else", "current": state(rain_amount=0.75, lightning_amount=0.8), "exact": {"rain_amount": 0.75, "lightning_amount": 0.0}, "preserve": [f for f in ALL_FIELDS if f != "lightning_amount"]},
    {"category": "weather", "name": "storm_clearing", "request": "the storm is clearing, make the rain and lightning much weaker but do not change the time of day", "current": state(sky_elevation=-4, rain_amount=0.95, lightning_amount=0.9), "less_than_current": ["rain_amount", "lightning_amount"], "preserve": ["sky_elevation"]},

    # composition across independent controls
    {"category": "composition", "name": "warm_rainy_sunset", "request": "warm rainy sunset, no lightning", "expect": {"sky_elevation": (0, 15), "light_elevation": (0, 25), "light_warmth": (0.35, 1), "rain_amount": (0.2, 1), "lightning_amount": (0, 0.05)}},
    {"category": "composition", "name": "foggy_moonlit_night", "request": "a foggy moonlit night with slow-moving mist", "expect": {"sky_elevation": (-12, -0.1), "light_elevation": (5, 45), "mist_amount": (0.45, 1), "mist_motion": (0, 0.45)}},
    {"category": "composition", "name": "clear_cold_dawn", "request": "cold clear dawn with no mist or rain", "expect": {"sky_elevation": (0, 15), "light_warmth": (-1, 0.1), "sky_haze": (0, 0.4), "mist_amount": (0, 0.05), "rain_amount": (0, 0.05)}},
    {"category": "composition", "name": "eerie_dry_evening", "request": "a subtly eerie dry evening, no mist, no rain, no lightning, keep it readable", "expect": {"sky_elevation": (-2, 20), "light_level": (0.2, 0.75), "mist_amount": (0, 0.05), "rain_amount": (0, 0.05), "lightning_amount": (0, 0.05)}},
    {"category": "composition", "name": "bright_hazy_midday", "request": "bright hazy midday", "expect": {"sky_elevation": (65, 90), "light_elevation": (65, 90), "light_level": (0.65, 1), "sky_haze": (0.4, 1)}},
    {"category": "composition", "name": "warm_sunrise_ground_fog", "request": "warm sunrise through thick ground fog with very little movement", "expect": {"sky_elevation": (0, 15), "light_warmth": (0.35, 1), "mist_amount": (0.55, 1), "mist_height": (0, 0.35), "mist_motion": (0, 0.3)}},
    {"category": "composition", "name": "night_thunderstorm", "request": "a dark but readable night thunderstorm with heavy rain and lightning", "expect": {"sky_elevation": (-12, -0.1), "light_level": (0.15, 0.7), "rain_amount": (0.65, 1), "lightning_amount": (0.5, 1)}},

    # explicit preservation and conversational continuity
    {"category": "preservation", "name": "add_mist_preserve_lighting", "request": "add thick active mist but keep all lighting exactly as it is", "current": state(sky_elevation=7, light_elevation=10, light_azimuth=225, light_level=0.82, light_warmth=0.78, sky_haze=0.62), "expect": {"mist_amount": (0.6, 1), "mist_motion": (0.5, 1)}, "preserve": LIGHTING_FIELDS},
    {"category": "preservation", "name": "warmth_only", "request": "only make the light warmer, change absolutely nothing else", "current": state(light_warmth=-0.25, mist_amount=0.45, rain_amount=0.3), "expect": {"light_warmth": (0.15, 1)}, "preserve": [f for f in ALL_FIELDS if f != "light_warmth"]},
    {"category": "preservation", "name": "azimuth_only", "request": "only change where the light comes from, rotate it to about 250 degrees", "current": state(light_azimuth=40, mist_amount=0.4), "expect": {"light_azimuth": (235, 265)}, "preserve": [f for f in ALL_FIELDS if f != "light_azimuth"]},
    {"category": "preservation", "name": "stop_storm_preserve_scene", "request": "stop the rain and lightning but keep the mist and all lighting exactly the same", "current": state(sky_elevation=-6, light_elevation=18, light_azimuth=228, light_level=0.42, light_warmth=-0.35, sky_haze=0.7, mist_amount=0.7, mist_height=0.6, mist_motion=0.5, rain_amount=0.9, lightning_amount=0.8), "exact": {"rain_amount": 0.0, "lightning_amount": 0.0}, "preserve": LIGHTING_FIELDS + ["mist_amount", "mist_height", "mist_motion"]},
    {"category": "preservation", "name": "clear_mist_only", "request": "remove the mist only, keep the rain, lightning and lighting exactly unchanged", "current": state(mist_amount=0.8, rain_amount=0.65, lightning_amount=0.5, light_level=0.55), "exact": {"mist_amount": 0.0, "rain_amount": 0.65, "lightning_amount": 0.5}, "preserve": LIGHTING_FIELDS + ["rain_amount", "lightning_amount"]},
    {"category": "preservation", "name": "heavier_rain_same_lightning", "request": "make the rain heavier but keep the lightning exactly the same and change nothing else", "current": state(rain_amount=0.25, lightning_amount=0.62), "greater_than_current": ["rain_amount"], "exact": {"lightning_amount": 0.62}, "preserve": [f for f in ALL_FIELDS if f != "rain_amount"]},
    {"category": "preservation", "name": "make_night_keep_weather", "request": "make it night but keep all mist, rain and lightning exactly as they are", "current": state(mist_amount=0.5, mist_height=0.4, mist_motion=0.6, rain_amount=0.45, lightning_amount=0.2), "expect": {"sky_elevation": (-12, -0.1)}, "preserve": WEATHER_FIELDS},
    {"category": "preservation", "name": "leave_exactly", "request": "leave the atmosphere exactly as it is, change nothing", "current": state(sky_elevation=8, light_elevation=12, light_azimuth=210, light_level=0.72, light_warmth=0.6, sky_haze=0.45, mist_amount=0.4, mist_height=0.25, mist_motion=0.3, rain_amount=0.2, lightning_amount=0.1, mood="warm rainy dusk"), "preserve": ALL_FIELDS},
    {"category": "preservation", "name": "non_atmosphere_mountain", "request": "make the mountain taller", "current": state(sky_elevation=8, mist_amount=0.4, rain_amount=0.2), "preserve_numeric": ALL_NUMERIC_FIELDS},
    {"category": "preservation", "name": "non_atmosphere_object_colour", "request": "turn the car red", "current": state(sky_elevation=-6, mist_amount=0.5, rain_amount=0.4), "preserve_numeric": ALL_NUMERIC_FIELDS},

    # negation and conflicting modifiers
    {"category": "conflict", "name": "spooky_no_mist", "request": "make it spooky at night but absolutely no mist, rain or lightning", "expect": {"sky_elevation": (-12, -0.1), "mist_amount": (0, 0.05), "rain_amount": (0, 0.05), "lightning_amount": (0, 0.05), "light_level": (0.15, 0.75)}},
    {"category": "conflict", "name": "stormy_no_precipitation", "request": "stormy dark clouds, but no rain and no lightning", "expect": {"sky_haze": (0.35, 1), "rain_amount": (0, 0.05), "lightning_amount": (0, 0.05)}},
    {"category": "conflict", "name": "cold_sunset", "request": "sunset, but make the light distinctly cold rather than warm", "expect": {"sky_elevation": (0, 15), "light_elevation": (0, 25), "light_warmth": (-1, -0.15)}},
    {"category": "conflict", "name": "warm_night", "request": "nighttime, but with distinctly warm key lighting", "expect": {"sky_elevation": (-12, -0.1), "light_warmth": (0.25, 1)}},
    {"category": "conflict", "name": "dark_midday", "request": "midday, but dim and eerie while still readable", "expect": {"sky_elevation": (65, 90), "light_elevation": (65, 90), "light_level": (0.15, 0.65)}},
    {"category": "conflict", "name": "storm_keep_lighting", "request": "make it a heavy thunderstorm but keep every lighting value exactly unchanged", "current": state(sky_elevation=8, light_elevation=12, light_azimuth=220, light_level=0.8, light_warmth=0.7, sky_haze=0.55), "expect": {"rain_amount": (0.65, 1), "lightning_amount": (0.5, 1)}, "preserve": LIGHTING_FIELDS},
    {"category": "conflict", "name": "sunset_keep_sky", "request": "make it feel like sunset but keep the current sky elevation exactly unchanged", "current": state(sky_elevation=45, light_elevation=45, light_warmth=0), "exact": {"sky_elevation": 45}, "expect": {"light_elevation": (0, 25), "light_warmth": (0.3, 1)}},
    {"category": "conflict", "name": "neutral_midday_reset", "request": "remove the weather effects and return to a clear neutral midday atmosphere", "current": state(sky_elevation=-6, light_elevation=18, light_warmth=-0.4, sky_haze=0.8, mist_amount=0.8, rain_amount=0.9, lightning_amount=0.8), "expect": {"sky_elevation": (65, 90), "light_elevation": (65, 90), "light_warmth": (-0.25, 0.25), "sky_haze": (0, 0.35), "mist_amount": (0, 0.05), "rain_amount": (0, 0.05), "lightning_amount": (0, 0.05)}},

    # vocabulary and paraphrase coverage
    {"category": "vocabulary", "name": "twilight", "request": "twilight with clear air", "expect": {"sky_elevation": (-5, 12), "sky_haze": (0, 0.4)}},
    {"category": "vocabulary", "name": "pea_soup_fog", "request": "pea-soup fog, almost no movement", "expect": {"mist_amount": (0.7, 1), "mist_motion": (0, 0.2)}},
    {"category": "vocabulary", "name": "drizzle_word", "request": "a gentle drizzle", "expect": {"rain_amount": (0.1, 0.5)}},
    {"category": "vocabulary", "name": "downpour_word", "request": "a heavy downpour", "expect": {"rain_amount": (0.7, 1)}},
    {"category": "vocabulary", "name": "distant_lightning", "request": "occasional lightning flickering in the distance, no rain", "expect": {"lightning_amount": (0.15, 0.65), "rain_amount": (0, 0.05)}},
    {"category": "vocabulary", "name": "crisp_winter_morning", "request": "a crisp clear cold winter morning", "expect": {"sky_elevation": (8, 45), "light_warmth": (-1, 0.15), "sky_haze": (0, 0.35)}},
    {"category": "vocabulary", "name": "foggy_af", "request": "make it foggy af but keep the lighting the same", "current": state(sky_elevation=7, light_elevation=10, light_level=0.8, light_warmth=0.7, sky_haze=0.4), "expect": {"mist_amount": (0.55, 1)}, "preserve": LIGHTING_FIELDS},
    {"category": "vocabulary", "name": "sunset_vibes_no_storm", "request": "sunset vibes, warm and hazy, but no rain or lightning", "expect": {"sky_elevation": (0, 15), "light_warmth": (0.4, 1), "sky_haze": (0.4, 1), "rain_amount": (0, 0.05), "lightning_amount": (0, 0.05)}},
]


REVIEW_CASES = [
    {"name": "cinematic", "request": "make it more cinematic"},
    {"name": "ominous", "request": "make the atmosphere ominous"},
    {"name": "dreamlike", "request": "make it dreamlike and quiet"},
    {"name": "romantic", "request": "make the evening romantic"},
    {"name": "murky", "request": "make the air murky"},
    {"name": "alien_green", "request": "an eerie green alien night"},
    {"name": "geographic", "request": "a cold clear evening in the mountains around Quetta"},
    {"name": "minimal_change", "request": "just make it a tiny bit moodier"},
]


SEQUENCES = [
    {
        "name": "sunset_to_misty_night",
        "start": state(),
        "steps": [
            {"request": "make it a warm sunset", "expect": {"sky_elevation": (0, 15), "light_warmth": (0.4, 1)}},
            {"request": "add thick mist but keep the lighting exactly as it is", "expect": {"mist_amount": (0.6, 1)}, "preserve_previous": LIGHTING_FIELDS},
            {"request": "make the mist almost completely still, change nothing else", "expect": {"mist_motion": (0, 0.15)}, "preserve_previous": [f for f in ALL_FIELDS if f != "mist_motion"]},
            {"request": "turn it into night but keep the mist exactly as it is", "expect": {"sky_elevation": (-12, -0.1)}, "preserve_previous": ["mist_amount", "mist_height", "mist_motion"]},
            {"request": "remove the mist only", "exact": {"mist_amount": 0.0}, "preserve_previous": LIGHTING_FIELDS + ["rain_amount", "lightning_amount"]},
        ],
    },
    {
        "name": "storm_control",
        "start": state(),
        "steps": [
            {"request": "heavy thunderstorm with frequent lightning", "expect": {"rain_amount": (0.65, 1), "lightning_amount": (0.55, 1)}},
            {"request": "stop the lightning but keep the rain and lighting exactly the same", "exact": {"lightning_amount": 0.0}, "preserve_previous": LIGHTING_FIELDS + ["rain_amount", "mist_amount", "mist_height", "mist_motion"]},
            {"request": "reduce the rain to a light drizzle and change nothing else", "expect": {"rain_amount": (0.1, 0.45)}, "preserve_previous": [f for f in ALL_FIELDS if f != "rain_amount"]},
            {"request": "stop the rain too, change nothing else", "exact": {"rain_amount": 0.0}, "preserve_previous": [f for f in ALL_FIELDS if f != "rain_amount"]},
            {"request": "now make it clear neutral midday", "expect": {"sky_elevation": (65, 90), "light_elevation": (65, 90), "sky_haze": (0, 0.35), "rain_amount": (0, 0.05), "lightning_amount": (0, 0.05)}},
        ],
    },
    {
        "name": "night_refinement",
        "start": state(),
        "steps": [
            {"request": "clear moonlit night", "expect": {"sky_elevation": (-12, -0.1), "light_warmth": (-1, 0.15)}},
            {"request": "make only the key light warmer, keep the time of day exactly the same", "expect": {"light_warmth": (0.15, 1)}, "preserve_previous": ["sky_elevation"]},
            {"request": "add moderate rain but no lightning, keep the lighting exactly the same", "expect": {"rain_amount": (0.25, 0.7), "lightning_amount": (0, 0.05)}, "preserve_previous": LIGHTING_FIELDS},
            {"request": "make it eerie but do not make it darker and do not change the weather", "preserve_previous": ["light_level"] + WEATHER_FIELDS},
            {"request": "remove the rain only and keep everything else", "exact": {"rain_amount": 0.0}, "preserve_previous": [f for f in ALL_FIELDS if f != "rain_amount"]},
        ],
    },
]


REPEATABILITY_CASES = [
    {"name": "repeat_sunset", "request": "warm hazy sunset", "expect": {"sky_elevation": (0, 15), "light_warmth": (0.4, 1), "sky_haze": (0.4, 1)}},
    {"name": "repeat_night", "request": "clear moonlit night", "expect": {"sky_elevation": (-12, -0.1), "light_warmth": (-1, 0.15)}},
    {"name": "repeat_mist", "request": "thick ground-hugging mist with little movement", "expect": {"mist_amount": (0.6, 1), "mist_height": (0, 0.35), "mist_motion": (0, 0.4)}},
    {"name": "repeat_storm", "request": "heavy thunderstorm with frequent lightning", "expect": {"rain_amount": (0.65, 1), "lightning_amount": (0.55, 1)}},
    {"name": "repeat_preserve", "request": "make the mist thicker but keep all lighting exactly the same", "current": state(sky_elevation=7, light_elevation=10, light_azimuth=225, light_level=0.85, light_warmth=0.8, sky_haze=0.7, mist_amount=0.2), "expect": {"mist_amount": (0.45, 1)}, "preserve": LIGHTING_FIELDS},
]
REPEAT_RUNS = 3


def file_sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_case(case, current, result, previous=None):
    errors = base.validate_schema(result)

    for key, bounds in case.get("expect", {}).items():
        value = result.get(key)
        low, high = bounds
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not low <= value <= high:
            errors.append(f"expected {key} in {low}..{high}, got {value!r}")

    for key, expected in case.get("exact", {}).items():
        if result.get(key) != expected:
            errors.append(f"expected {key} exactly {expected!r}, got {result.get(key)!r}")

    for key in case.get("preserve", []):
        if result.get(key) != current.get(key):
            errors.append(f"preservation failed for {key}: expected {current.get(key)!r}, got {result.get(key)!r}")

    for key in case.get("preserve_numeric", []):
        if result.get(key) != current.get(key):
            errors.append(f"numeric preservation failed for {key}: expected {current.get(key)!r}, got {result.get(key)!r}")

    for key in case.get("less_than_current", []):
        if not result.get(key) < current.get(key):
            errors.append(f"expected {key} < current {current.get(key)!r}, got {result.get(key)!r}")

    for key in case.get("greater_than_current", []):
        if not result.get(key) > current.get(key):
            errors.append(f"expected {key} > current {current.get(key)!r}, got {result.get(key)!r}")

    if previous is not None:
        for key in case.get("preserve_previous", []):
            if result.get(key) != previous.get(key):
                errors.append(f"sequence preservation failed for {key}: expected {previous.get(key)!r}, got {result.get(key)!r}")

    return errors


def run_case(case, current=None, previous=None):
    current = deepcopy(current if current is not None else case.get("current", base.MODIFIER_SCHEMA))
    result = base.ask_qwen(case["request"], current)
    errors = validate_case(case, current, result, previous=previous)
    return current, result, errors


def category_summary(records):
    totals = {}
    for record in records:
        category = record["category"]
        bucket = totals.setdefault(category, {"passed": 0, "total": 0})
        bucket["total"] += 1
        if record["status"] == "pass":
            bucket["passed"] += 1
    return totals


def main():
    actual_hash = file_sha256(BASE_FILE)
    if actual_hash != EXPECTED_BASE_SHA256:
        raise SystemExit(
            "refusing to run: test_atmosphere_schema_v2.py has changed\n"
            f"expected: {EXPECTED_BASE_SHA256}\n"
            f"actual:   {actual_hash}"
        )

    print("tangible worlds deep atmosphere schema test")
    print(f"model: {base.LMSTUDIO_MODEL}")
    print(f"base prompt sha256: {actual_hash}")
    print(f"strict tests: {len(STRICT_TESTS)}")
    print(f"review-only cases: {len(REVIEW_CASES)}")
    print(f"stateful sequence steps: {sum(len(s['steps']) for s in SEQUENCES)}")
    print(f"repeatability calls: {len(REPEATABILITY_CASES) * REPEAT_RUNS}")
    print()

    evidence = {
        "model": base.LMSTUDIO_MODEL,
        "base_prompt_sha256": actual_hash,
        "strict": [],
        "review": [],
        "sequences": [],
        "repeatability": [],
    }

    strict_passed = 0
    for index, case in enumerate(STRICT_TESTS, start=1):
        try:
            current, result, errors = run_case(case)
            status = "pass" if not errors else "fail"
        except Exception as exc:
            current = deepcopy(case.get("current", base.MODIFIER_SCHEMA))
            result = None
            errors = [f"request/error: {exc}"]
            status = "error"

        if status == "pass":
            strict_passed += 1
            print(f"[{index:02d}/{len(STRICT_TESTS)}] PASS {case['category']}/{case['name']}")
        else:
            print(f"[{index:02d}/{len(STRICT_TESTS)}] FAIL {case['category']}/{case['name']}")
            for error in errors:
                print(f"    - {error}")
            if result is not None:
                print(f"    output: {json.dumps(result, sort_keys=True)}")

        evidence["strict"].append({
            "category": case["category"],
            "name": case["name"],
            "request": case["request"],
            "current": current,
            "result": result,
            "errors": errors,
            "status": status,
        })

    print("\nreview-only cases, no pass/fail because the language is deliberately ambiguous")
    for case in REVIEW_CASES:
        try:
            current, result, errors = run_case(case)
        except Exception as exc:
            current = deepcopy(base.MODIFIER_SCHEMA)
            result = None
            errors = [f"request/error: {exc}"]
        print(f"  REVIEW {case['name']}: {json.dumps(result, sort_keys=True) if result else errors[0]}")
        evidence["review"].append({"name": case["name"], "request": case["request"], "current": current, "result": result, "schema_errors": errors})

    print("\nstateful conversational sequences")
    sequence_passed = 0
    sequence_total = 0
    for sequence in SEQUENCES:
        current = deepcopy(sequence["start"])
        seq_record = {"name": sequence["name"], "steps": []}
        print(f"  sequence: {sequence['name']}")
        for step_index, step in enumerate(sequence["steps"], start=1):
            sequence_total += 1
            previous = deepcopy(current)
            try:
                _, result, errors = run_case(step, current=current, previous=previous)
                status = "pass" if not errors else "fail"
            except Exception as exc:
                result = None
                errors = [f"request/error: {exc}"]
                status = "error"

            if status == "pass":
                sequence_passed += 1
                current = deepcopy(result)
                print(f"    step {step_index}: PASS")
            else:
                print(f"    step {step_index}: FAIL")
                for error in errors:
                    print(f"      - {error}")
                if result is not None:
                    current = deepcopy(result)

            seq_record["steps"].append({
                "step": step_index,
                "request": step["request"],
                "previous": previous,
                "result": result,
                "errors": errors,
                "status": status,
            })
        evidence["sequences"].append(seq_record)

    print("\nrepeatability")
    repeat_passed = 0
    repeat_total = 0
    for case in REPEATABILITY_CASES:
        record = {"name": case["name"], "request": case["request"], "runs": []}
        print(f"  {case['name']}")
        for run_index in range(1, REPEAT_RUNS + 1):
            repeat_total += 1
            try:
                current, result, errors = run_case(case)
                status = "pass" if not errors else "fail"
            except Exception as exc:
                current = deepcopy(case.get("current", base.MODIFIER_SCHEMA))
                result = None
                errors = [f"request/error: {exc}"]
                status = "error"
            if status == "pass":
                repeat_passed += 1
            print(f"    run {run_index}: {status.upper()}")
            if errors:
                for error in errors:
                    print(f"      - {error}")
            record["runs"].append({"run": run_index, "current": current, "result": result, "errors": errors, "status": status})
        evidence["repeatability"].append(record)

    categories = category_summary(evidence["strict"])
    strict_rate = strict_passed / len(STRICT_TESTS)
    sequence_rate = sequence_passed / sequence_total if sequence_total else 0
    repeat_rate = repeat_passed / repeat_total if repeat_total else 0

    preservation_records = [r for r in evidence["strict"] if r["category"] == "preservation"]
    preservation_passed = sum(r["status"] == "pass" for r in preservation_records)
    preservation_rate = preservation_passed / len(preservation_records)

    schema_failures = 0
    for record in evidence["strict"]:
        result = record.get("result")
        if result is None or base.validate_schema(result):
            schema_failures += 1
    for sequence in evidence["sequences"]:
        for step in sequence["steps"]:
            result = step.get("result")
            if result is None or base.validate_schema(result):
                schema_failures += 1
    for record in evidence["repeatability"]:
        for run in record["runs"]:
            result = run.get("result")
            if result is None or base.validate_schema(result):
                schema_failures += 1

    # gate is deliberately stricter on structure and explicit preservation than
    # on subjective semantic ranges. a model can disagree slightly on aesthetics,
    # but it must not break the contract or overwrite protected scene state.
    gate_pass = (
        schema_failures == 0
        and strict_rate >= 0.90
        and preservation_rate == 1.0
        and sequence_rate >= 0.90
        and repeat_rate >= 0.90
    )

    evidence["summary"] = {
        "strict_passed": strict_passed,
        "strict_total": len(STRICT_TESTS),
        "strict_rate": strict_rate,
        "categories": categories,
        "preservation_passed": preservation_passed,
        "preservation_total": len(preservation_records),
        "preservation_rate": preservation_rate,
        "sequence_passed": sequence_passed,
        "sequence_total": sequence_total,
        "sequence_rate": sequence_rate,
        "repeatability_passed": repeat_passed,
        "repeatability_total": repeat_total,
        "repeatability_rate": repeat_rate,
        "schema_failures": schema_failures,
        "gate_pass": gate_pass,
    }

    RESULTS_FILE.write_text(json.dumps(evidence, indent=2), encoding="utf-8")

    print("\ncategory summary")
    for category, counts in categories.items():
        print(f"  {category}: {counts['passed']}/{counts['total']}")

    print("\nfinal summary")
    print(f"  strict: {strict_passed}/{len(STRICT_TESTS)} ({strict_rate:.1%})")
    print(f"  explicit preservation: {preservation_passed}/{len(preservation_records)} ({preservation_rate:.1%})")
    print(f"  stateful sequence steps: {sequence_passed}/{sequence_total} ({sequence_rate:.1%})")
    print(f"  repeatability: {repeat_passed}/{repeat_total} ({repeat_rate:.1%})")
    print(f"  schema/format failures: {schema_failures}")
    print(f"  integration gate: {'PASS' if gate_pass else 'FAIL'}")
    print(f"  saved: {RESULTS_FILE}")


if __name__ == "__main__":
    main()

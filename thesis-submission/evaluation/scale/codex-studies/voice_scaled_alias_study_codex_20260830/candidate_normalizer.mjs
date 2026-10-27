// Isolated candidate only. Production remains untouched during qualification.
// ref: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/RegExp
// ref: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/String/match
const VOICE_SCALED_SIZE_ALIAS_RE = /^(?<generation>.+?)\s+scaled\s+(?<modifier>tiny|miniature|small|big|large|huge)\s*[.!?]*\s*$/i;
const EARLIER_SCALE_CONTROL_RE = /(?:^|\s)(?:scale|scaled)\s+(?:tiny|miniature|small|big|large|huge)(?=$|[\s,.!?])/i;

export function normalizeVoiceScaleAlias(meaning) {
    const match = (meaning || '').match(VOICE_SCALED_SIZE_ALIAS_RE);
    if (!match) return meaning;

    const generation = match.groups.generation.trim();
    if (
        !generation
        || generation.endsWith(';')
        || generation.endsWith(':')
        || EARLIER_SCALE_CONTROL_RE.test(generation)
    ) {
        return meaning;
    }
    return `${generation} scale ${match.groups.modifier}`;
}

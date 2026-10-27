#!/usr/bin/env node

import fs from 'node:fs';
import { normalizeVoiceScaleAlias } from './candidate_normalizer.mjs';

const inputPath = new URL('./holdout_cases.json', import.meta.url);
const holdout = JSON.parse(fs.readFileSync(inputPath, 'utf8'));

const NUMBER_WORDS = {
    one: '1', two: '2', three: '3', four: '4', five: '5',
    six: '6', seven: '7', eight: '8', nine: '9', ten: '10',
};

const SCALE_TARGETS = {
    tiny: ['very_small', 0.35],
    miniature: ['very_small', 0.35],
    small: ['small', 0.65],
    big: ['large', 1.80],
    large: ['large', 1.80],
    huge: ['very_large', 3.00],
};

function parseVoiceAssignment(text) {
    const match = (text || '').trim().match(
        /^object\s+(?:number\s+)?(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+is\s+(.+?)\s*[.!?]*$/i
    );
    if (!match) return null;
    const spokenKey = match[1].toLowerCase();
    const objectKey = /^\d+$/.test(spokenKey)
        ? String(parseInt(spokenKey, 10))
        : NUMBER_WORDS[spokenKey];
    const meaning = match[2].replace(/[.!?]+$/, '').trim();
    if (!objectKey || !meaning) return null;
    return { object_key: objectKey, meaning };
}

// Exact JavaScript mirror of the current Python marked-scale grammar.  The
// isolated server-import regression separately checks the production function.
function parseMarkedScale(meaning) {
    const neutral = {
        meaning,
        generation_meaning: meaning,
        explicit_scale_intent: 'neutral',
        target_size: 1.0,
        scale_source: 'neutral_default',
    };
    const match = meaning.match(
        /^(?<generation>.+?)(?:\s*,\s*|\s+)scale\s+(?<modifier>tiny|miniature|small|big|large|huge)\s*[.!?]*\s*$/i
    );
    if (!match) return neutral;
    const generation = match.groups.generation.trim();
    const fragment = /,\s*(?:scale|scaled|make\s+it)\s+\S+|(?:^|\s)(?:scale|scaled|make\s+it)\s+(?:tiny|miniature|small|big|large|huge)(?=$|[\s,.!?])/i;
    if (!generation || generation.endsWith(';') || generation.endsWith(':') || fragment.test(generation)) {
        return neutral;
    }
    const [intent, target] = SCALE_TARGETS[match.groups.modifier.toLowerCase()];
    return {
        meaning,
        generation_meaning: generation,
        explicit_scale_intent: intent,
        target_size: target,
        scale_source: 'participant_marked',
    };
}

function sameNumber(a, b) {
    return a === b || (typeof a === 'number' && typeof b === 'number' && Math.abs(a - b) < 1e-12);
}

const rows = [];
for (const test of holdout.cases) {
    const assignment = parseVoiceAssignment(test.transcript);
    let actual;
    if (!assignment) {
        actual = {
            route: 'converse', object_key: null, original_meaning: null,
            alias_detected: false, sent_meaning: null, generation_meaning: null,
            explicit_scale_intent: null, target_size: null, scale_source: null,
        };
    } else {
        const sentMeaning = normalizeVoiceScaleAlias(assignment.meaning);
        const parsed = parseMarkedScale(sentMeaning);
        actual = {
            route: 'assignment', object_key: assignment.object_key,
            original_meaning: assignment.meaning,
            alias_detected: sentMeaning !== assignment.meaning,
            sent_meaning: sentMeaning,
            generation_meaning: parsed.generation_meaning,
            explicit_scale_intent: parsed.explicit_scale_intent,
            target_size: parsed.target_size,
            scale_source: parsed.scale_source,
        };
    }
    const expected = {
        route: test.expected_route,
        object_key: test.expected_object_key,
        original_meaning: test.expected_original_meaning,
        alias_detected: test.reserved_grammar_alias,
        sent_meaning: test.expected_sent_meaning,
        generation_meaning: test.expected_generation_meaning,
        explicit_scale_intent: test.expected_explicit_scale_intent,
        target_size: test.expected_target_size,
        scale_source: test.expected_scale_source,
    };
    const contractPass = Object.keys(expected).every(key => sameNumber(actual[key], expected[key]));
    rows.push({
        id: test.id,
        category: test.category,
        transcript: test.transcript,
        human_intended_alias: test.human_intended_alias,
        reserved_grammar_alias: test.reserved_grammar_alias,
        ...actual,
        contract_pass: contractPass,
    });
}

function confusion(labelField) {
    let TP = 0, FP = 0, FN = 0, TN = 0;
    for (let index = 0; index < rows.length; index++) {
        const expected = Boolean(holdout.cases[index][labelField]);
        const actual = rows[index].alias_detected;
        if (expected && actual) TP++;
        else if (!expected && actual) FP++;
        else if (expected && !actual) FN++;
        else TN++;
    }
    return {
        TP, FP, FN, TN,
        precision: TP + FP ? TP / (TP + FP) : null,
        recall: TP + FN ? TP / (TP + FN) : null,
    };
}

const typedScaled = parseMarkedScale('a car scaled tiny');
const typedScale = parseMarkedScale('a car scale tiny');
const typedProtection = {
    input: 'a car scaled tiny',
    candidate_normalizer_invoked: false,
    output: typedScaled,
    existing_explicit_control: typedScale,
    pass: typedScaled.generation_meaning === 'a car scaled tiny'
        && typedScaled.explicit_scale_intent === 'neutral'
        && typedScaled.target_size === 1.0
        && typedScale.generation_meaning === 'a car'
        && typedScale.target_size === 0.35,
};

const result = {
    study_date: holdout.study_date,
    holdout_frozen_at: holdout.frozen_at,
    holdout_case_count: holdout.case_count,
    category_counts: holdout.category_counts,
    human_intent_metrics: confusion('human_intended_alias'),
    reserved_voice_grammar_metrics: confusion('reserved_grammar_alias'),
    semantic_collisions: rows.filter(row => row.category === 'literal_semantic_collision'),
    exact_contract: {
        passed: rows.filter(row => row.contract_pass).length,
        total: rows.length,
        pass: rows.every(row => row.contract_pass),
    },
    atmosphere_routing: {
        passed: rows.filter(row => row.category === 'atmosphere_or_nonassignment' && row.route === 'converse').length,
        total: rows.filter(row => row.category === 'atmosphere_or_nonassignment').length,
    },
    typed_protection: typedProtection,
    rows,
};

function csvCell(value) {
    if (value === null || value === undefined) return '';
    const text = String(value);
    return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

if (process.argv.includes('--csv')) {
    const fields = [
        'id', 'category', 'transcript', 'human_intended_alias', 'reserved_grammar_alias',
        'route', 'object_key', 'original_meaning', 'alias_detected', 'sent_meaning',
        'generation_meaning', 'explicit_scale_intent', 'target_size', 'scale_source', 'contract_pass',
    ];
    console.log(fields.join(','));
    for (const row of rows) console.log(fields.map(field => csvCell(row[field])).join(','));
} else {
    console.log(JSON.stringify(result, null, 2));
}

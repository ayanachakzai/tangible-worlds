#!/usr/bin/env node

import fs from 'node:fs';

const [patchedPath, holdoutPath] = process.argv.slice(2);
if (!patchedPath || !holdoutPath) {
    throw new Error('usage: verify_patched_index.mjs PATCHED_INDEX HOLDOUT_JSON');
}

const html = fs.readFileSync(patchedPath, 'utf8');
const holdout = JSON.parse(fs.readFileSync(holdoutPath, 'utf8'));
const block = html.match(
    /const VOICE_SCALED_SIZE_ALIAS_RE[\s\S]+?function normalizeVoiceScaleAlias\(meaning\) \{[\s\S]+?\n\}/
);
if (!block) throw new Error('candidate normalizer not found in patched index');
const normalizeVoiceScaleAlias = new Function(
    `${block[0]}; return normalizeVoiceScaleAlias;`
)();

let passed = 0;
const failures = [];
for (const test of holdout.cases) {
    if (test.expected_route !== 'assignment') continue;
    const actual = normalizeVoiceScaleAlias(test.expected_original_meaning);
    const detected = actual !== test.expected_original_meaning;
    const ok = detected === test.reserved_grammar_alias
        && actual === test.expected_sent_meaning;
    if (ok) passed += 1;
    else failures.push({ id: test.id, expected: test.expected_sent_meaning, actual });
}

const total = holdout.cases.filter(test => test.expected_route === 'assignment').length;
console.log(JSON.stringify({ passed, total, failures, pass: passed === total }, null, 2));
if (passed !== total) process.exitCode = 1;

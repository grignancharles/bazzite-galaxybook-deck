// Run: gjs -m extension/tests/defaultAccents.test.js
import System from 'system';
import {DEFAULT_ACCENTS, parseTable} from '../defaultAccents.js';

let failures = 0;
function test(name, fn) {
    try {
        fn();
        print(`PASS ${name}`);
    } catch (e) {
        failures++;
        print(`FAIL ${name}: ${e.message}`);
    }
}
function check(cond, msg) {
    if (!cond)
        throw new Error(msg);
}

test('the built-in table round-trips through parseTable', () => {
    const table = parseTable(JSON.stringify(DEFAULT_ACCENTS));
    check(table !== null && table.e.join('') === DEFAULT_ACCENTS.e.join(''), 'same content');
});

test('a well-formed override is accepted, including empty lists', () => {
    const table = parseTable('{"e": ["é", "è"], "x": []}');
    check(table !== null && table.e.length === 2 && table.x.length === 0, 'accepted');
});

test('malformed overrides are rejected', () => {
    check(parseTable('') === null, 'empty text');
    check(parseTable('{') === null, 'not JSON');
    check(parseTable('[]') === null, 'array');
    check(parseTable('null') === null, 'null');
    check(parseTable('"e"') === null, 'string');
    check(parseTable('{"e": {"length": 1}}') === null, 'object instead of array');
    check(parseTable('{"e": "é"}') === null, 'string instead of array');
    check(parseTable('{"e": ["é", 1]}') === null, 'number candidate');
    check(parseTable('{"e": ["é", ""]}') === null, 'empty candidate');
    check(parseTable('{"": ["é"]}') === null, 'empty base');
});

if (failures)
    System.exit(1);

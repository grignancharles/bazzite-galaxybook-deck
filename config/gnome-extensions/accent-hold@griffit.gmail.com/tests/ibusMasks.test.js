// Run: gjs -m extension/tests/ibusMasks.test.js
// holdMachine.js spells out the IBus modifier bits so it needs no GI import;
// check them against the real enum (needs the IBus typelib, present on any
// GNOME desktop).
import System from 'system';
import IBus from 'gi://IBus';
import {SHORTCUT_MASK, describeKey} from '../holdMachine.js';

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

const M = IBus.ModifierType;

test('SHORTCUT_MASK matches IBus.ModifierType', () => {
    const expected = M.CONTROL_MASK | M.MOD1_MASK | M.MOD3_MASK | M.MOD4_MASK |
        M.SUPER_MASK | M.HYPER_MASK | M.META_MASK;
    check(SHORTCUT_MASK === expected, `${SHORTCUT_MASK} !== ${expected}`);
    check((SHORTCUT_MASK & M.SHIFT_MASK) === 0, 'Shift is not a shortcut modifier');
    check((SHORTCUT_MASK & M.MOD5_MASK) === 0, 'AltGr (MOD5) is not a shortcut modifier');
});

test('the release bit matches IBus.ModifierType.RELEASE_MASK', () => {
    const k = describeKey(0x65, 18, M.RELEASE_MASK | M.SHIFT_MASK, 'e', 'e');
    check(k.release, 'release');
    check(k.state === M.SHIFT_MASK, 'release bit stripped from state');
});

test('describeKey with real IBus helpers', () => {
    const name = kv => IBus.keyval_name(kv) || '';
    const uni = kv => IBus.keyval_to_unicode(kv);
    const e = describeKey(IBus.KEY_e, 18, 0, name(IBus.KEY_e), uni(IBus.KEY_e));
    check(e.char === 'e' && !e.modifier && e.name === '', 'e');
    const left = describeKey(IBus.KEY_Left, 105, 0, name(IBus.KEY_Left), uni(IBus.KEY_Left));
    check(left.char === '' && left.name === 'Left', 'Left');
    const kp3 = describeKey(IBus.KEY_KP_3, 81, 0, name(IBus.KEY_KP_3), uni(IBus.KEY_KP_3));
    check(kp3.keypadDigit === 2, 'KP_3');
    const shift = describeKey(IBus.KEY_Shift_L, 42, 0, name(IBus.KEY_Shift_L), uni(IBus.KEY_Shift_L));
    check(shift.modifier, 'Shift_L');
    const ctrlE = describeKey(IBus.KEY_e, 18, M.CONTROL_MASK, 'e', 'e');
    check(ctrlE.shortcut, 'Ctrl+e');
});

if (failures)
    System.exit(1);

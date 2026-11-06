// Run: gjs -m extension/tests/holdMachine.test.js
import System from 'system';
import {HoldMachine, makeKey, describeKey, surroundingRun, deletableCount} from '../holdMachine.js';
import {DEFAULT_ACCENTS} from '../defaultAccents.js';

let failures = 0;
function test(name, fn, table = DEFAULT_ACCENTS) {
    try {
        fn(new HoldMachine(() => table));
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
function same(a, b, msg) {
    check(JSON.stringify(a) === JSON.stringify(b), `${msg}: got ${JSON.stringify(a)}`);
}
function kinds(actions) {
    return actions.map(a => a[0]);
}

const e = makeKey({keyval: 0x65, keycode: 18, state: 0, char: 'e'});
const eUp = {...e, release: true};
const digit = n => makeKey({keyval: 0x30 + n, keycode: n + 1, char: String(n)});
const x = makeKey({keyval: 0x78, keycode: 45, char: 'x'});
// Navigation keys with their real keysyms (the machine tracks swallowed keys
// by keyval).
const KEYVALS = {
    Left: 0xff51, Up: 0xff52, Right: 0xff53, Down: 0xff54, Tab: 0xff09,
    ISO_Left_Tab: 0xfe20, Return: 0xff0d, KP_Enter: 0xff8d, space: 0x20,
    Escape: 0xff1b, KP_Left: 0xff96, KP_Up: 0xff97, KP_Right: 0xff98,
    KP_Down: 0xff99,
};
const nav = (name, fields = {}) => makeKey({keyval: KEYVALS[name], name, ...fields});

function open(m) {
    m.key(e);
    return m.holdElapsed();
}

// -- tap and hold ----------------------------------------------------------

test('tap types the letter and disarms', m => {
    check(!m.key(e).consumed, 'press passes');
    const r = m.key(eUp);
    check(!r.consumed && r.actions[0][0] === 'disarm', 'release disarms');
});

test('arm carries the key so the release can be forwarded later', m => {
    const r = m.key(e);
    same(r.actions, [['arm', e]], 'arm with key');
});

test('hold releases the key for the application, then shows', m => {
    m.key(e);
    const actions = m.holdElapsed();
    same(kinds(actions), ['release', 'show'], 'release before show');
    check(actions[0][1].keyval === 0x65 && actions[0][1].keycode === 18, 'release of the held key');
    same(actions[1][1], DEFAULT_ACCENTS.e, 'candidates');
});

test('hold then digit replaces', m => {
    check(m.key(e).actions[0][0] === 'arm', 'arms');
    check(m.holdElapsed()[1][0] === 'show', 'shows');
    check(!m.key(eUp).consumed, 'release of the held letter reaches the app');
    const r = m.key(digit(2));
    check(r.consumed, 'digit swallowed');
    same(r.actions, [['hide'], ['replace', 'e', 'è']], 'replace è');
});

test('holdElapsed when not armed does nothing', m => {
    same(m.holdElapsed(), [], 'idle');
    open(m);
    same(m.holdElapsed(), [], 'already open');
});

test('holdElapsed with a table entry that vanished goes idle', m => {
    const table = {e: ['é']};
    const mm = new HoldMachine(() => table);
    mm.key(e);
    delete table.e;
    same(mm.holdElapsed(), [], 'no show');
    check(mm.state === 'idle', 'idle');
});

test('non-array table entries never arm', m => {
    same(m.key(e).actions, [], 'object entry ignored');
}, {e: {length: 1}});

test('arrows move, a digit chooses the highlighted neighbour', m => {
    open(m);
    check(m.key(nav('Right')).actions[0][1] === 1, 'moves right');
    const r = m.key(digit(2));
    check(r.consumed && r.actions[1][2] === 'è', 'digit 2 is è');
});

// -- B5: space and Enter dismiss, keep the plain letter, reach the app ----

for (const name of ['space', 'Return', 'KP_Enter']) {
    test(`${name} while open closes without choosing and goes through`, m => {
        open(m);
        m.key(eUp);
        const r = m.key(nav(name, {char: name === 'space' ? ' ' : ''}));
        check(!r.consumed, `${name} reaches the application`);
        same(r.actions, [['hide']], 'only hides');
        check(m.state === 'idle', 'idle');
    });
}

test('Enter picks the highlighted variant once the arrows were used', m => {
    open(m);
    m.key(eUp);
    m.key(nav('Right'));
    const r = m.key(nav('Return'));
    check(r.consumed, 'Enter swallowed');
    same(r.actions, [['hide'], ['replace', 'e', 'è']], 'picks è');
});

test('Enter after navigating with the keypad picks too; space still dismisses', m => {
    open(m);
    m.key(nav('KP_Right'));
    const r = m.key(nav('space', {char: ' '}));
    check(!r.consumed && r.actions[0][0] === 'hide', 'space closes and goes through');
    open(m);
    m.key(nav('Left'));
    check(m.key(nav('KP_Enter')).consumed, 'KP_Enter picks');
});

// -- B6: the held letter pressed again -------------------------------------

test('held letter pressed again before its release is a repeat, swallowed', m => {
    open(m);
    const r = m.key(e);
    check(r.consumed && r.actions.length === 0, 'repeat swallowed');
    check(m.state === 'open', 'still open');
});

test('held letter pressed again after its release is a new keystroke', m => {
    open(m);
    check(!m.key(eUp).consumed, 'release forwarded');
    const r = m.key(e);
    check(!r.consumed, 'second e reaches the application');
    same(kinds(r.actions), ['hide', 'arm'], 'hides and arms again');
    check(m.state === 'armed', 'armed on the new press');
    check(!m.key(eUp).consumed && m.state === 'idle', 'tap: "ee" typed, idle');
});

test('other key while open keeps the letter', m => {
    open(m);
    const r = m.key(x);
    check(!r.consumed && r.actions[0][0] === 'hide', 'x passes and hides');
});

test('non-accentable keys and shortcuts never arm', m => {
    check(m.key(x).actions.length === 0, 'x');
    check(m.key({...e, shortcut: true}).actions.length === 0, 'Ctrl+e');
});

// -- swallowed keys stay swallowed until released --------------------------

test('a chosen digit: its repeats and release never reach the app', m => {
    open(m);
    m.key(eUp);
    check(m.key(digit(1)).consumed, 'press chooses');
    check(m.state === 'idle', 'idle after the choice');
    check(m.key(digit(1)).consumed && m.key(digit(1)).actions.length === 0, 'repeat swallowed');
    check(m.key({...digit(1), release: true}).consumed, 'release swallowed');
    check(!m.key(digit(1)).consumed, 'next press is a plain digit again');
});

test('Escape release is swallowed, the held letter release is not', m => {
    open(m);
    check(m.key(nav('Escape')).consumed, 'Escape press');
    check(m.key(nav('Escape', {release: true})).consumed, 'Escape release');
    check(!m.key(eUp).consumed, 'held letter release forwarded');
});

test('cancel forgets swallowed keys', m => {
    open(m);
    m.key(digit(9));   // out of range: swallowed, popup stays
    m.cancel();
    check(!m.key({...digit(9), release: true}).consumed, 'release forwarded after cancel');
});

test('keypad arrows navigate like the arrows', m => {
    open(m);
    check(m.key(nav('KP_Right')).actions[0][1] === 1, 'KP_Right');
    check(m.key(nav('KP_Left')).actions[0][1] === 0, 'KP_Left');
    check(m.key(nav('KP_Down')).actions[0][1] === 1, 'KP_Down');
    check(m.key(nav('KP_Up')).actions[0][1] === 0, 'KP_Up');
});

// -- navigation and selection ------------------------------------------------

test('Tab and ISO_Left_Tab navigate', m => {
    open(m);
    check(m.key(nav('Tab')).actions[0][1] === 1, 'Tab forward');
    check(m.key(nav('ISO_Left_Tab')).actions[0][1] === 0, 'Shift+Tab back');
});

test('navigation wraps around', m => {
    open(m);
    const n = DEFAULT_ACCENTS.e.length;
    check(m.key(nav('Left')).actions[0][1] === n - 1, 'Left from the first goes to the last');
    check(m.key(nav('Right')).actions[0][1] === 0, 'Right from the last goes to the first');
});

test('keypad digits choose', m => {
    open(m);
    const r = m.key(makeKey({keyval: 0xffb3, keypadDigit: 2}));
    check(r.consumed && r.actions[1][2] === 'ê', 'KP_3 is ê');
});

test('a digit beyond the candidates is swallowed and the popup stays', m => {
    open(m);
    const r = m.key(digit(9));
    check(r.consumed && r.actions.length === 0, 'swallowed, nothing happens');
    check(m.state === 'open', 'still open');
});

test('Ctrl+digit while open is a shortcut: forwarded, popup closed', m => {
    open(m);
    const r = m.key({...digit(1), shortcut: true});
    check(!r.consumed, 'forwarded');
    same(r.actions, [['hide']], 'hidden');
    check(m.state === 'idle', 'idle');
});

test('at most nine candidates are offered', m => {
    const table = {e: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12']};
    const mm = new HoldMachine(() => table);
    mm.key(e);
    const show = mm.holdElapsed()[1];
    check(show[1].length === 9, 'nine');
    check(mm.key(digit(9)).actions[1][2] === '9', 'digit 9 picks the ninth');
});

test('candidateClicked ignores bad indexes and the wrong state', m => {
    same(m.candidateClicked(0), [], 'idle');
    open(m);
    same(m.candidateClicked(-1), [], 'negative');
    same(m.candidateClicked(DEFAULT_ACCENTS.e.length), [], 'past the end');
    same(m.candidateClicked(1), [['hide'], ['replace', 'e', 'è']], 'click');
});

// -- cancel, modifiers, rollover, repeats ------------------------------------

test('cancel from each state', m => {
    same(m.cancel(), [], 'idle');
    m.key(e);
    same(m.cancel(), [['disarm']], 'armed');
    open(m);
    same(m.cancel(), [['hide']], 'open');
    check(m.state === 'idle', 'idle after cancel');
});

test('a modifier press while armed or open is forwarded and changes nothing', m => {
    const shift = makeKey({keyval: 0xffe1, modifier: true});
    m.key(e);
    check(!m.key(shift).consumed && m.state === 'armed', 'armed');
    check(!m.key({...shift, release: true}).consumed && m.state === 'armed', 'armed, release');
    m.holdElapsed();
    check(!m.key(shift).consumed && m.state === 'open', 'open');
});

test('rollover: a second letter before the release disarms and re-arms', m => {
    const a = makeKey({keyval: 0x61, keycode: 30, char: 'a'});
    m.key(e);
    const r = m.key(a);
    check(!r.consumed, 'a reaches the application');
    same(kinds(r.actions), ['disarm', 'arm'], 'disarm e, arm a');
    check(!m.key(eUp).consumed, 'late release of e forwarded');
    const show = m.holdElapsed()[1];
    same(show[1], DEFAULT_ACCENTS.a, 'variants of a');
});

test('compositor repeats while armed are swallowed', m => {
    m.key(e);
    const r = m.key(e);
    check(r.consumed && r.actions.length === 0, 'repeat swallowed');
    check(m.state === 'armed', 'still armed');
    check(!m.key(eUp).consumed && m.state === 'idle', 'release is a tap');
});

// -- describeKey (what the input method filter hands to the machine) -------

test('describeKey maps the filter arguments to a key', () => {
    const RELEASE = 1 << 30, CONTROL = 1 << 2, SHIFT = 1 << 0;
    const press = describeKey(0x65, 18, SHIFT, 'e', 'e');
    check(press.char === 'e' && !press.release && !press.shortcut && !press.modifier, 'Shift+e is text');
    check(press.state === SHIFT, 'state kept');
    const release = describeKey(0x65, 18, RELEASE | SHIFT, 'e', 'e');
    check(release.release && release.state === SHIFT, 'release bit stripped from state');
    check(describeKey(0x65, 18, CONTROL, 'e', 'e').shortcut, 'Ctrl+e is a shortcut');
    check(describeKey(0xffe1, 42, 0, 'Shift_L', '').modifier, 'Shift_L is a modifier');
    check(describeKey(0xff51, 105, 0, 'Left', '').name === 'Left', 'navigation key named');
    check(describeKey(0x41, 30, 0, 'A', 'A').name === '', 'letters have no name');
    check(describeKey(0xffb3, 81, 0, 'KP_3', '3').keypadDigit === 2, 'KP_3 → index 2');
    check(describeKey(0xff08, 14, 0, 'BackSpace', '\b').char === '', 'control char dropped');
    check(describeKey(0x65, 18, 0, 'e', 0x65).char === 'e', 'numeric unicode accepted');
    check(describeKey(0xff51, 105, 0, 'Left', 0).char === '', 'zero unicode is no char');
});

// -- surrounding text (GNOME 45: [text, cursor]; 46+: [text, cursor, anchor])

test('surroundingRun counts the letters before the cursor', () => {
    check(surroundingRun(['thee', 4, 4], 'e') === 2, '46+ tuple');
    check(surroundingRun(['thee', 4], 'e') === 2, '45 tuple');
    check(surroundingRun(['thee', 2, 2], 'e') === 0, 'cursor in the middle');
    check(surroundingRun(['eee', 3, 3], 'e') === 3, 'whole text');
    check(surroundingRun(['', 0, 0], 'e') === 0, 'empty text');
});

test('surroundingRun rejects unusable surrounding text', () => {
    check(surroundingRun([null, null, null], 'e') === -1, 'no text');
    check(surroundingRun([null, null], 'e') === -1, 'no text (45)');
    check(surroundingRun(['thee', 2, 4], 'e') === -1, 'selection');
    check(surroundingRun(['the', 9, 9], 'e') === -1, 'cursor out of range');
    check(surroundingRun(undefined, 'e') === -1, 'not an array');
});

test('deletableCount deletes only what was inserted since the press', () => {
    check(deletableCount(0, 1) === 1, 'one letter');
    check(deletableCount(0, 5) === 5, 'client repeated four times');
    check(deletableCount(2, 3) === 1, 'after "thee"');
    check(deletableCount(2, 2) === 0, 'stale text: BackSpace path');
    check(deletableCount(-1, 3) === 1, 'no snapshot: only the last letter');
    check(deletableCount(0, 0) === 0, 'no letter before the cursor');
    check(deletableCount(0, -1) === 0, 'unusable now');
});

if (failures)
    System.exit(1);

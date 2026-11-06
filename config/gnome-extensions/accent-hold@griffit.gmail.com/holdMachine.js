// Press-and-hold state machine, free of Shell imports so it can be tested with
// plain gjs. Same model as ibus/holdcore.py: a tapped letter is forwarded to the
// application right away, holding an accentable letter for `hold-ms` opens the
// variants, and picking one replaces the letter that was already inserted.

// Hardware (evdev) keycodes of the digit row: KEY_1 = 2 ... KEY_9 = 10. The
// digit row is selected by position so it works on AZERTY too.
const DIGIT_ROW_FIRST = 2;
const DIGIT_ROW_LAST = 10;
export const MAX_LABELS = DIGIT_ROW_LAST - DIGIT_ROW_FIRST + 1;

export const IDLE = 'idle';
export const ARMED = 'armed';
export const OPEN = 'open';

// KP_* are what the keypad arrows produce with Num Lock off.
const NAV_PREV = new Set(['Left', 'Up', 'KP_Left', 'KP_Up', 'ISO_Left_Tab']);
const NAV_NEXT = new Set(['Right', 'Down', 'KP_Right', 'KP_Down', 'Tab']);
// Enter picks the highlighted variant, but only once the arrows were used:
// a pause on `e` followed by Enter in a chat must send the message, not
// type "é". Space never picks: a pause followed by a space is "e ", not "é".
// Either key otherwise closes the variants and goes on to the application.
const NAV_CONFIRM = new Set(['Return', 'KP_Enter']);
const NAV_DISMISS = new Set(['space']);
const NAV_CANCEL = new Set(['Escape']);
export const NAV_KEYS = new Set([...NAV_PREV, ...NAV_NEXT, ...NAV_CONFIRM, ...NAV_DISMISS, ...NAV_CANCEL]);

// A key event: {keyval, keycode, state, char, release, shortcut, modifier,
// name, keypadDigit}. `keycode` is the evdev code, `state` the modifier mask
// of the press (without the release bit), `char` is '' for non-printing keys,
// `name` is set for NAV_KEYS only, `keypadDigit` is 0..8 for keypad 1..9,
// else -1.
export function makeKey(fields) {
    return {
        keyval: 0, keycode: 0, state: 0, char: '', release: false,
        shortcut: false, modifier: false, name: '', keypadDigit: -1, ...fields,
    };
}

// Modifier bits of the state IBus receives (IBus.ModifierType, the X11
// values), written out so this module needs no GI import; ibusMasks.test.js
// checks them against the real enum.
const RELEASE_MASK = 1 << 30;
// Modifiers that turn a letter into a shortcut rather than text: Control,
// Alt (MOD1), ISO_Level5_Shift (MOD3 on the layouts that have it), Super
// (MOD4), and the Super/Hyper/Meta virtual bits.
export const SHORTCUT_MASK = (1 << 2) | (1 << 3) | (1 << 5) | (1 << 6) |
    (1 << 26) | (1 << 27) | (1 << 28);
export const MODIFIER_KEYS = new Set([
    'Shift_L', 'Shift_R', 'Control_L', 'Control_R', 'Alt_L', 'Alt_R',
    'Meta_L', 'Meta_R', 'Super_L', 'Super_R', 'Hyper_L', 'Hyper_R',
    'Caps_Lock', 'Shift_Lock', 'Num_Lock', 'Scroll_Lock',
    'ISO_Level3_Shift', 'ISO_Level5_Shift', 'Mode_switch',
    'ISO_Next_Group', 'ISO_Prev_Group', 'Multi_key',
]);

// Build the key the machine works on from what the input method filter
// sees: `keyval`, evdev `keycode` and IBus `state`, plus the keysym `name`
// (IBus.keyval_name, '' when unknown) and the character it produces
// (IBus.keyval_to_unicode: a one-character string in gjs, '' or 0 for none).
export function describeKey(keyval, keycode, state, name, unicode) {
    let char = unicode;
    if (typeof char === 'number')
        char = char > 0 ? String.fromCodePoint(char) : '';
    if (!char || /\p{C}/u.test(char))
        char = '';
    let keypadDigit = -1;
    const kp = /^KP_([1-9])$/.exec(name);
    if (kp)
        keypadDigit = Number(kp[1]) - 1;
    return makeKey({
        keyval,
        keycode,
        state: state & ~RELEASE_MASK,
        char,
        release: (state & RELEASE_MASK) !== 0,
        shortcut: (state & SHORTCUT_MASK) !== 0,
        modifier: MODIFIER_KEYS.has(name),
        name: NAV_KEYS.has(name) ? name : '',
        keypadDigit,
    });
}

// Number of `base` characters right before the cursor in the surrounding
// text, or -1 when the surrounding text cannot be trusted. `surrounding` is
// what InputMethod.getSurroundingText() returns: [text, cursor] on GNOME 45,
// [text, cursor, anchor] since GNOME 46. Only a collapsed cursor is usable:
// with a selection the next keystroke replaces it.
export function surroundingRun(surrounding, base) {
    if (!Array.isArray(surrounding) || surrounding.length < 2)
        return -1;
    const [text, cursor] = surrounding;
    const anchor = surrounding.length >= 3 ? surrounding[2] : cursor;
    if (typeof text !== 'string' || typeof cursor !== 'number' || cursor !== anchor)
        return -1;
    const chars = Array.from(text);
    if (cursor < 0 || cursor > chars.length)
        return -1;
    let n = 0;
    while (n < cursor && chars[cursor - 1 - n] === base)
        n++;
    return n;
}

// How many characters to delete before the cursor when replacing the held
// letter: the letters the application inserted since the hold started (one,
// plus any client-side key repeats). `before` is the run measured when the
// key was pressed, `now` the run measured when the variant is chosen. 0 means
// the surrounding text is unusable or stale: the caller falls back to a
// single BackSpace.
export function deletableCount(before, now) {
    if (now < 1)
        return 0;
    if (before < 0)
        return 1;
    return now > before ? now - before : 0;
}

function digitIndex(key) {
    if (key.keycode >= DIGIT_ROW_FIRST && key.keycode <= DIGIT_ROW_LAST)
        return key.keycode - DIGIT_ROW_FIRST;
    return key.keypadDigit;
}

// key() returns {consumed, actions}. Actions are arrays:
//   ['arm', key] / ['disarm']       start / cancel the hold timer
//   ['release', key]                tell the application the held key is up
//   ['show', candidates, index]     show the variants
//   ['move', index]                 move the highlight
//   ['hide']                        hide the variants
//   ['replace', base, text]         replace the inserted `base` with `text`
export class HoldMachine {
    constructor(getTable) {
        this._getTable = getTable;
        // Keys whose press was swallowed and that are still down: their
        // repeats and release are swallowed too, whatever the state, so the
        // application never sees a release without its press.
        this._swallowed = new Set();
        this._toIdle();
    }

    key(key) {
        if (this._swallowed.has(key.keyval)) {
            if (key.release)
                this._swallowed.delete(key.keyval);
            return {consumed: true, actions: []};
        }
        const held = this.held;
        let result;
        if (this.state === OPEN)
            result = this._keyOpen(key);
        else if (this.state === ARMED)
            result = this._keyArmed(key);
        else
            result = this._keyIdle(key);
        // The held letter is the exception: its press reached the
        // application, so its release must too.
        if (result.consumed && !key.release && key.keyval !== held)
            this._swallowed.add(key.keyval);
        return result;
    }

    holdElapsed() {
        if (this.state !== ARMED)
            return [];
        const variants = this._getTable()[this.base];
        if (!Array.isArray(variants) || variants.length === 0) {
            this._toIdle();
            return [];
        }
        this.state = OPEN;
        this.candidates = variants.slice(0, MAX_LABELS);
        this.index = 0;
        // The press reached the application and its release will not until
        // the user lets go: send a release now so the application stops its
        // own key repeat (clients that repeat on their side).
        return [['release', this.heldKey], ['show', this.candidates, this.index]];
    }

    candidateClicked(index) {
        if (this.state !== OPEN || index < 0 || index >= this.candidates.length)
            return [];
        return this._choose(index);
    }

    cancel() {
        const actions = [];
        if (this.state === OPEN)
            actions.push(['hide']);
        else if (this.state === ARMED)
            actions.push(['disarm']);
        this._toIdle();
        this._swallowed.clear();
        return actions;
    }

    _keyIdle(key) {
        const variants = this._getTable()[key.char];
        if (!key.release && !key.shortcut && Array.isArray(variants) && variants.length) {
            this.state = ARMED;
            this.base = key.char;
            this.held = key.keyval;
            this.heldKey = key;
            return {consumed: false, actions: [['arm', key]]};
        }
        return {consumed: false, actions: []};
    }

    _keyArmed(key) {
        if (key.keyval === this.held) {
            if (key.release) {
                // Quick tap: the letter is already in the application.
                this._toIdle();
                return {consumed: false, actions: [['disarm']]};
            }
            return {consumed: true, actions: []};
        }
        if (key.release || key.modifier)
            return {consumed: false, actions: []};
        this._toIdle();
        const result = this._keyIdle(key);
        result.actions.unshift(['disarm']);
        return result;
    }

    _keyOpen(key) {
        if (key.keyval === this.held) {
            if (key.release) {
                // The press reached the application, so must its release.
                this.released = true;
                return {consumed: false, actions: []};
            }
            // Before the release: a compositor key repeat, swallowed. After
            // it: the user typed the letter again, a new keystroke.
            if (!this.released)
                return {consumed: true, actions: []};
            return this._newKey(key);
        }
        if (key.release || key.modifier)
            return {consumed: false, actions: []};

        const index = digitIndex(key);
        if (index >= 0 && !key.shortcut) {
            if (index < this.candidates.length)
                return {consumed: true, actions: this._choose(index)};
            return {consumed: true, actions: []};
        }
        if (NAV_PREV.has(key.name) || NAV_NEXT.has(key.name)) {
            const n = this.candidates.length;
            const step = NAV_PREV.has(key.name) ? -1 : 1;
            this.index = (this.index + step + n) % n;
            this.navigated = true;
            return {consumed: true, actions: [['move', this.index]]};
        }
        if (NAV_CONFIRM.has(key.name) && this.navigated)
            return {consumed: true, actions: this._choose(this.index)};
        if (NAV_CONFIRM.has(key.name) || NAV_DISMISS.has(key.name)) {
            this._toIdle();
            return {consumed: false, actions: [['hide']]};
        }
        if (NAV_CANCEL.has(key.name)) {
            this._toIdle();
            return {consumed: true, actions: [['hide']]};
        }

        return this._newKey(key);
    }

    // Anything else keeps the plain letter and is handled as a new key.
    _newKey(key) {
        this._toIdle();
        const result = this._keyIdle(key);
        result.actions.unshift(['hide']);
        return result;
    }

    _choose(index) {
        const base = this.base, text = this.candidates[index];
        this._toIdle();
        return [['hide'], ['replace', base, text]];
    }

    _toIdle() {
        this.state = IDLE;
        this.base = null;
        this.held = null;
        this.heldKey = null;
        this.released = false;
        this.navigated = false;
        this.candidates = [];
        this.index = 0;
    }
}

import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import Shell from 'gi://Shell';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as KeyboardStatus from 'resource:///org/gnome/shell/ui/status/keyboard.js';
import {monitorAt, clampToMonitor} from './placement.js';

// Accent picker opened by a keyboard shortcut. Two phases: first wait for a base
// letter, then show its accented variants for selection. A failsafe timeout and
// try/catch around the key handler guarantee the modal grab is always released.
// The chosen character is committed through the GNOME input method, like the
// press-and-hold variants, so it needs an application using it.

// After the modal grab is released the application re-enables its text
// input, which takes a round trip; the commit waits for the input method to
// report a focus again, polling at this interval for at most this many turns.
const FOCUS_POLL_MS = 20;
const FOCUS_POLL_MAX = 15;

export class AccentPicker {
    // getTable is a callback because the extension reloads the table when the
    // `accents` setting changes.
    constructor(settings, getTable, gettext) {
        this._settings = settings;
        this._getTable = getTable;
        this._ = gettext || ((s) => s);

        this._actor = null;
        this._grab = null;
        this._hint = null;
        this._phase = null;        // 'await-letter' | 'variants'
        this._variants = [];
        this._index = 0;
        this._chips = [];
        this._timeoutId = 0;       // failsafe auto-close
        this._delayId = 0;         // optional delay before opening
        this._commitId = 0;        // commit waiting for the input method focus
        this._window = null;       // window focused when the picker opened
    }

    start() {
        if (this._actor || this._delayId)
            return;

        if (!this._layoutAllowed())
            return;

        const delay = Math.max(0, this._settings.get_int('delay-ms'));
        if (delay === 0) {
            this._open();
            return;
        }
        this._delayId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, delay, () => {
            this._delayId = 0;
            this._open();
            return GLib.SOURCE_REMOVE;
        });
    }

    // Restrict activation to the xkb layouts listed in `layouts` (empty = all).
    _layoutAllowed() {
        const wanted = this._settings.get_strv('layouts');
        if (wanted.length === 0)
            return true;
        const cur = KeyboardStatus.getInputSourceManager().currentSource;
        if (!cur)
            return true;
        // Match both ids: prefs stores the input-source id, the runtime may
        // expose xkbId.
        return wanted.includes(cur.xkbId) || wanted.includes(cur.id);
    }

    _open() {
        if (this._actor)
            return;

        this._phase = 'await-letter';
        this._variants = [];
        this._index = 0;
        this._chips = [];
        this._window = global.display.focus_window;

        this._actor = new St.BoxLayout({
            style_class: 'accent-popup',
            reactive: true,
            can_focus: true,
        });
        this._hint = new St.Label({
            style_class: 'accent-hint',
            text: this._('Type a letter…'),
        });
        this._actor.add_child(this._hint);

        Main.layoutManager.uiGroup.add_child(this._actor);
        this._place();

        this._grab = Main.pushModal(this._actor, {actionMode: Shell.ActionMode.NORMAL});
        if (!this._grab) {
            this._close();
            return;
        }

        // Arm the failsafe right after grabbing so the popup always closes even
        // if a later call throws.
        const timeout = Math.max(1000, this._settings.get_int('popup-timeout-ms'));
        this._removeSource('_timeoutId');
        this._timeoutId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, timeout, () => {
            this._timeoutId = 0;
            this._close();
            return GLib.SOURCE_REMOVE;
        });

        try {
            this._actor.grab_key_focus();
            this._actor.connectObject('key-press-event', (_a, e) => this._onKey(e), this);
        } catch (e) {
            logError(e, 'accent-hold: open');
            this._close();
        }
    }

    _onKey(event) {
        try {
            const sym = event.get_key_symbol();
            if (sym === Clutter.KEY_Escape) {
                this._close();
                return Clutter.EVENT_STOP;
            }
            if (this._phase === 'await-letter')
                return this._onAwaitLetter(event, sym);
            return this._onVariants(event, sym);
        } catch (e) {
            logError(e, 'accent-hold: key handler');
            this._close();
            return Clutter.EVENT_STOP;
        }
    }

    // Phase 1: wait for the base letter.
    _onAwaitLetter(event, sym) {
        if (this._isModifier(sym))
            return Clutter.EVENT_STOP;

        // In GJS get_key_unicode() returns the character as a one-char string
        // (case included). Handle a numeric codepoint defensively.
        let ch = event.get_key_unicode();
        if (typeof ch === 'number')
            ch = ch > 0 ? String.fromCodePoint(ch) : '';
        if (!ch) {
            this._close();
            return Clutter.EVENT_STOP;
        }
        const table = this._getTable() || {};
        const variants = table[ch];
        if (variants && variants.length > 0)
            this._showVariants(ch, variants);
        else
            this._close();
        return Clutter.EVENT_STOP;
    }

    _isModifier(sym) {
        return (
            sym === Clutter.KEY_Shift_L || sym === Clutter.KEY_Shift_R ||
            sym === Clutter.KEY_Control_L || sym === Clutter.KEY_Control_R ||
            sym === Clutter.KEY_Alt_L || sym === Clutter.KEY_Alt_R ||
            sym === Clutter.KEY_Super_L || sym === Clutter.KEY_Super_R ||
            sym === Clutter.KEY_Meta_L || sym === Clutter.KEY_Meta_R ||
            sym === Clutter.KEY_Hyper_L || sym === Clutter.KEY_Hyper_R ||
            sym === Clutter.KEY_Caps_Lock || sym === Clutter.KEY_Num_Lock ||
            sym === Clutter.KEY_ISO_Level3_Shift || sym === Clutter.KEY_ISO_Level5_Shift ||
            sym === Clutter.KEY_Mode_switch
        );
    }

    // Phase 2: show the accented variants as buttons.
    _showVariants(_letter, variants) {
        this._phase = 'variants';
        this._variants = variants.slice(0, 9); // 1..9 selectable by number
        this._index = 0;

        if (this._hint) {
            this._actor.remove_child(this._hint);
            this._hint.destroy();
            this._hint = null;
        }

        this._chips = this._variants.map((v, i) => {
            const chip = new St.Button({
                style_class: 'accent-chip',
                label: `${i + 1} ${v}`,
                can_focus: false,
            });
            chip.connectObject('clicked', () => this._choose(i), this);
            this._actor.add_child(chip);
            return chip;
        });
        this._highlight();
        // The popup just grew: keep it on screen.
        this._place();
    }

    // Below the pointer, inside its monitor. The picker is meant for
    // applications that report no text cursor, so the pointer is the anchor.
    _place() {
        let [x, y] = global.get_pointer();
        y += 24;
        const layout = Main.layoutManager;
        const monitor = monitorAt(layout.monitors, layout.primaryMonitor, x, y);
        const [, width] = this._actor.get_preferred_width(-1);
        const [, height] = this._actor.get_preferred_height(-1);
        [x, y] = clampToMonitor(x, y, width, height, monitor);
        this._actor.set_position(Math.round(x), Math.round(y));
    }

    _onVariants(event, sym) {
        if (sym === Clutter.KEY_Left) {
            this._move(-1);
            return Clutter.EVENT_STOP;
        }
        if (sym === Clutter.KEY_Right) {
            this._move(1);
            return Clutter.EVENT_STOP;
        }
        if (sym === Clutter.KEY_Return || sym === Clutter.KEY_KP_Enter ||
            sym === Clutter.KEY_space) {
            this._choose(this._index);
            return Clutter.EVENT_STOP;
        }
        const n = this._digitIndex(event, sym);
        if (n >= 0) {
            if (n < this._variants.length)
                this._choose(n);
            return Clutter.EVENT_STOP;
        }
        // Any other key cancels.
        this._close();
        return Clutter.EVENT_STOP;
    }

    // Map a number key to an index 0..8, or -1. Match the hardware keycode first
    // (digit row = keycodes 10..18 on any layout) so number selection works on
    // AZERTY, where the unshifted top row produces symbols. Also accept the digit
    // keysyms and the numeric keypad.
    _digitIndex(event, sym) {
        const code = event.get_key_code();
        if (code >= 10 && code <= 18)
            return code - 10;
        if (sym >= Clutter.KEY_1 && sym <= Clutter.KEY_9)
            return sym - Clutter.KEY_1;
        if (sym >= Clutter.KEY_KP_1 && sym <= Clutter.KEY_KP_9)
            return sym - Clutter.KEY_KP_1;
        return -1;
    }

    _move(d) {
        const n = this._variants.length;
        if (n === 0)
            return;
        this._index = Math.max(0, Math.min(n - 1, this._index + d));
        this._highlight();
    }

    _highlight() {
        this._chips.forEach((c, i) =>
            i === this._index
                ? c.add_style_pseudo_class('selected')
                : c.remove_style_pseudo_class('selected'));
    }

    _choose(i) {
        const ch = this._variants[i];
        const window = this._window;
        this._close();          // release the grab before committing
        if (ch)
            this._commitWhenFocused(ch, window);
    }

    // The modal grab took the keyboard focus away from the application, and
    // with it the input method focus; it comes back once the application
    // has re-enabled its text input. Commit then, and only into the window
    // the picker was opened for.
    _commitWhenFocused(ch, window) {
        this._removeSource('_commitId');
        let turns = 0;
        this._commitId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, FOCUS_POLL_MS, () => {
            const im = Main.inputMethod;
            if (global.display.focus_window !== window || ++turns > FOCUS_POLL_MAX) {
                this._commitId = 0;
                return GLib.SOURCE_REMOVE;
            }
            if (!im.currentFocus)
                return GLib.SOURCE_CONTINUE;
            this._commitId = 0;
            im.commit(ch);
            return GLib.SOURCE_REMOVE;
        });
    }

    _removeSource(field) {
        if (this[field]) {
            GLib.source_remove(this[field]);
            this[field] = 0;
        }
    }

    _close() {
        this._removeSource('_delayId');
        this._removeSource('_timeoutId');
        if (this._grab) {
            Main.popModal(this._grab);
            this._grab = null;
        }
        if (this._actor) {
            Main.layoutManager.uiGroup.remove_child(this._actor);
            this._actor.destroy();
            this._actor = null;
        }
        this._hint = null;
        this._chips = [];
        this._variants = [];
        this._index = 0;
        this._phase = null;
        this._window = null;
    }

    destroy() {
        this._close();
        this._removeSource('_commitId');
        this._settings = null;
    }
}

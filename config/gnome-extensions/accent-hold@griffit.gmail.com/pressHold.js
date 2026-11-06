import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import IBus from 'gi://IBus';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as KeyboardStatus from 'resource:///org/gnome/shell/ui/status/keyboard.js';
import {HoldMachine, describeKey, surroundingRun, deletableCount} from './holdMachine.js';
import {installKeyFilter} from './imPatch.js';
import {monitorAt, clampToMonitor, anchorPoint} from './placement.js';

// Press-and-hold without an input method engine.
//
// On Wayland, GNOME Shell's input method (misc/inputMethod.js) sees every key
// typed into a text field and asks IBus about it through
// IBus.InputContext.process_key_event_async(). Wrapping that call (imPatch.js)
// lets the extension watch the keys and swallow the few it needs (digits,
// arrows... while the variants are shown); everything else goes on to IBus
// unchanged. Only applications using the Wayland text-input protocol go
// through it.

// Time given to the application to process a forwarded BackSpace before the
// replacement is committed.
const COMMIT_DELAY_MS = 120;
const BACKSPACE_EVCODE = 14;

export class PressHold {
    constructor(settings, getTable) {
        this._settings = settings;
        this._machine = new HoldMachine(getTable);
        this._popup = null;
        this._chips = [];
        this._holdId = 0;
        this._commitId = 0;
        this._timeoutId = 0;
        this._armRun = -1;
        this._armWindow = null;
        this._patch = null;

        // Settings read on every key go through a cache; the prototype is
        // only wrapped while press-and-hold is on.
        this._settings.connectObject(
            'changed::press-and-hold', () => this._readSettings(),
            'changed::layouts', () => this._readSettings(),
            this);
        this._readSettings();

        // The shell never clears InputMethod._cursorRect, so after a focus
        // change the stored rectangle belongs to the previous application
        // until the new one reports its own. The shell stores a fresh object
        // on every report, so remembering the current one is enough to tell
        // the two apart.
        this._staleRect = Main.inputMethod._cursorRect;
        global.display.connectObject('notify::focus-window', () => {
            this._staleRect = Main.inputMethod._cursorRect;
            this._cancel();
        }, this);
    }

    destroy() {
        this._settings.disconnectObject(this);
        this._uninstall();
        global.display.disconnectObject(this);
        this._cancel();
        // Remove every source, whatever state the machine was in.
        this._hide();
        this._removeSource('_holdId');
        this._removeSource('_commitId');
        this._settings = null;
    }

    _readSettings() {
        this._layouts = this._settings.get_strv('layouts');
        if (this._settings.get_boolean('press-and-hold'))
            this._install();
        else
            this._uninstall();
    }

    _install() {
        if (this._patch)
            return;
        this._patch = installKeyFilter(IBus.InputContext.prototype,
            (keyval, keycode, state) => this._filter(keyval, keycode, state));
    }

    _uninstall() {
        if (!this._patch)
            return;
        this._patch.remove();
        this._patch = null;
        this._cancel();
    }

    // Returns true when the key must not reach the application.
    _filter(keyval, keycode, state) {
        try {
            if (!this._settings || !this._active())
                return false;
            const result = this._machine.key(this._key(keyval, keycode, state));
            this._run(result.actions);
            return result.consumed;
        } catch (e) {
            logError(e, 'accent-hold: press-and-hold');
            this._cancel();
            return false;
        }
    }

    _active() {
        const source = KeyboardStatus.getInputSourceManager().currentSource;
        // An IBus engine (ours or a CJK one) handles the keys itself.
        if (!source || source.type !== 'xkb')
            return false;
        const wanted = this._layouts;
        return wanted.length === 0 || wanted.includes(source.id) || wanted.includes(source.xkbId);
    }

    _key(keyval, keycode, state) {
        return describeKey(keyval, keycode, state,
            IBus.keyval_name(keyval) || '', IBus.keyval_to_unicode(keyval));
    }

    _run(actions) {
        for (const [kind, ...args] of actions) {
            if (kind === 'arm') {
                this._removeSource('_holdId');
                // The letter is not in the application yet: remember how many
                // identical letters already precede the cursor, to delete only
                // what gets inserted from now on.
                this._armRun = surroundingRun(Main.inputMethod.getSurroundingText(), args[0].char);
                // The replacement must land in the window that got the
                // letter, not in whatever has the focus a moment later.
                this._armWindow = global.display.focus_window;
                const ms = this._settings.get_int('hold-ms');
                this._holdId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => {
                    this._holdId = 0;
                    this._run(this._machine.holdElapsed());
                    return GLib.SOURCE_REMOVE;
                });
            } else if (kind === 'disarm') {
                this._removeSource('_holdId');
            } else if (kind === 'release') {
                this._forwardRelease(args[0]);
            } else if (kind === 'show') {
                this._show(...args);
            } else if (kind === 'move') {
                this._highlight(args[0]);
            } else if (kind === 'hide') {
                this._hide();
            } else if (kind === 'replace') {
                this._replace(...args);
            }
        }
    }

    // Focus change, failsafe timeout, disable: drop everything, including
    // a replacement still waiting for its BackSpace to be processed.
    _cancel() {
        this._run(this._machine.cancel());
        this._removeSource('_commitId');
        this._armWindow = null;
    }

    // -- variants popup ------------------------------------------------------

    _show(candidates, index) {
        this._hide();
        this._popup = new St.BoxLayout({style_class: 'accent-popup', reactive: true});
        this._chips = candidates.map((text, i) => {
            const chip = new St.Button({
                style_class: 'accent-chip',
                label: `${i + 1} ${text}`,
                can_focus: false,
            });
            chip.connect('clicked', () => this._run(this._machine.candidateClicked(i)));
            this._popup.add_child(chip);
            return chip;
        });
        Main.layoutManager.uiGroup.add_child(this._popup);
        this._place();
        this._highlight(index);

        // Failsafe: never leave the popup up.
        const timeout = Math.max(1000, this._settings.get_int('popup-timeout-ms'));
        this._timeoutId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, timeout, () => {
            this._timeoutId = 0;
            this._cancel();
            return GLib.SOURCE_REMOVE;
        });
    }

    // Below the text cursor when the focused application reports it, else
    // below the pointer; always inside the monitor.
    _place() {
        const rect = Main.inputMethod._cursorRect;
        const window = global.display.focus_window;
        const frame = window ? window.get_frame_rect() : null;
        let [x, y] = anchorPoint(rect === this._staleRect ? null : rect, frame,
            global.get_pointer());
        const layout = Main.layoutManager;
        const monitor = monitorAt(layout.monitors, layout.primaryMonitor, x, y);
        const [, width] = this._popup.get_preferred_width(-1);
        const [, height] = this._popup.get_preferred_height(-1);
        [x, y] = clampToMonitor(x, y, width, height, monitor);
        this._popup.set_position(Math.round(x), Math.round(y));
    }

    _highlight(index) {
        this._chips.forEach((chip, i) =>
            i === index
                ? chip.add_style_pseudo_class('selected')
                : chip.remove_style_pseudo_class('selected'));
    }

    _hide() {
        this._removeSource('_timeoutId');
        if (this._popup) {
            this._popup.destroy();
            this._popup = null;
        }
        this._chips = [];
    }

    // -- text replacement ----------------------------------------------------

    // Send the application a release of the held key. The event takes the
    // same path as the keys IBus engines forward (InputMethod.forward_key):
    // it is flagged as coming from the input method, so mutter hands it to
    // the focused client without running it through this filter again. The
    // real release, forwarded later, is a second release of an already
    // released key, which clients ignore.
    _forwardRelease(key) {
        const im = Main.inputMethod;
        const time = global.display.get_current_time_roundtrip();
        im.forward_key(key.keyval, key.keycode + 8,
            key.state & Clutter.ModifierType.MODIFIER_MASK, time, false);
    }

    // The letter was inserted by the application itself (possibly several
    // times if it repeated the key before the release above reached it):
    // delete what was inserted, then commit the accented variant.
    _replace(base, text) {
        const im = Main.inputMethod;
        const window = this._armWindow;
        this._armWindow = null;
        if (global.display.focus_window !== window)
            return;
        const count = deletableCount(this._armRun,
            surroundingRun(im.getSurroundingText(), base));
        if (count > 0) {
            im.delete_surrounding(-count, count);
            im.commit(text);
            return;
        }
        // No usable surrounding text (terminals, some toolkits): one
        // BackSpace for the letter; client-side repeats cannot be counted.
        const time = global.display.get_current_time_roundtrip();
        const code = BACKSPACE_EVCODE + 8;
        im.forward_key(Clutter.KEY_BackSpace, code, 0, time, true);
        im.forward_key(Clutter.KEY_BackSpace, code, 0, time, false);
        this._removeSource('_commitId');
        this._commitId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, COMMIT_DELAY_MS, () => {
            this._commitId = 0;
            if (global.display.focus_window === window)
                im.commit(text);
            return GLib.SOURCE_REMOVE;
        });
    }

    _removeSource(field) {
        if (this[field]) {
            GLib.source_remove(this[field]);
            this[field] = 0;
        }
    }
}

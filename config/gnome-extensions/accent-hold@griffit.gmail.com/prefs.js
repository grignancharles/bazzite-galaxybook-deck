import Adw from 'gi://Adw';
import Gtk from 'gi://Gtk';
import Gdk from 'gi://Gdk';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

import {ExtensionPreferences, gettext as _} from 'resource:///org/gnome/Shell/Extensions/js/extensions/prefs.js';
import {DEFAULT_ACCENTS, parseTable} from './defaultAccents.js';

const SHORTCUT_KEY = 'accent-hold-shortcut';

// A shortcut must not hijack an ordinary key: it needs a modifier other than
// Shift or Caps Lock (Shift+e is just E), or a function key.
function shortcutAcceptable(keyval, mods) {
    const strong = mods & ~(Gdk.ModifierType.SHIFT_MASK | Gdk.ModifierType.LOCK_MASK);
    if (strong !== 0)
        return true;
    return keyval >= Gdk.KEY_F1 && keyval <= Gdk.KEY_F35;
}

// Readable labels for a few common xkb layouts; unknown ids fall back to the raw
// id. A function (not a const) so _() runs on use, after the gettext domain is
// resolved, rather than at module import time.
function layoutLabels() {
    return {
        'fr': _('French (fr)'),
        'fr+oss': _('French (oss variant)'),
        'us': _('English US (us)'),
        'us+intl': _('English US International'),
        'gb': _('English GB (gb)'),
        'de': _('German (de)'),
        'es': _('Spanish (es)'),
        'it': _('Italian (it)'),
        'pt': _('Portuguese (pt)'),
        'be': _('Belgian (be)'),
        'ch': _('Swiss (ch)'),
        'ca': _('Canadian (ca)'),
    };
}

export default class AccentHoldPreferences extends ExtensionPreferences {
    fillPreferencesWindow(window) {
        const settings = this.getSettings();

        const page = new Adw.PreferencesPage({
            title: _('Accent Hold'),
            icon_name: 'preferences-desktop-keyboard-shortcuts-symbolic',
        });
        window.add(page);

        this._buildHoldGroup(page, settings);
        this._buildShortcutGroup(page, settings);
        this._buildBehaviorGroup(page, settings);
        this._buildAccentsGroup(page, settings, window);
        this._buildLayoutsGroup(page, settings);
        this._buildFamilyGroup(page);
    }

    // Accent Hold needs nothing installed. Its siblings do, and carry an
    // Installation page of their own.
    _buildFamilyGroup(page) {
        const group = new Adw.PreferencesGroup({
            title: _('More from the Hold family'),
            description: _('Same gesture, same look. Each one installs its engine from its own settings, without a terminal.'),
        });
        page.add(group);
        for (const [title, subtitle, url] of [
            [_('Voice Hold'), _('Hold a key and dictate, offline.'), 'https://extensions.gnome.org/extension/11610/voice-hold/'],
            [_('Command Hold'), _('Hold a key and say what to do.'), 'https://github.com/d101c/command-hold'],
        ]) {
            const row = new Adw.ActionRow({title, subtitle, activatable: true});
            row.add_suffix(new Gtk.Image({icon_name: 'external-link-symbolic', valign: Gtk.Align.CENTER}));
            row.connect('activated', () => Gtk.show_uri(row.get_root(), url, Gdk.CURRENT_TIME));
            group.add(row);
        }
    }

    _buildHoldGroup(page, settings) {
        const group = new Adw.PreferencesGroup({
            title: _('Press and hold'),
            description: _('Hold a letter to choose its accent: press its number, or move with the arrows and press Enter, or click. Space, or Enter alone, keeps the plain letter.'),
        });
        page.add(group);

        const holdRow = new Adw.SwitchRow({
            title: _('Enabled'),
            subtitle: _('Works in applications that support the GNOME input method.'),
        });
        group.add(holdRow);
        settings.bind('press-and-hold', holdRow, 'active',
            Gio.SettingsBindFlags.DEFAULT);

        const durationRow = new Adw.SpinRow({
            title: _('Hold duration'),
            subtitle: _('Milliseconds a letter must be held.'),
            adjustment: new Gtk.Adjustment({
                lower: 200,
                upper: 1500,
                step_increment: 50,
                page_increment: 100,
            }),
        });
        group.add(durationRow);
        settings.bind('hold-ms', durationRow, 'value',
            Gio.SettingsBindFlags.DEFAULT);
    }

    _buildShortcutGroup(page, settings) {
        const group = new Adw.PreferencesGroup({
            title: _('Shortcut'),
            description: _('Key that triggers the accent picker.'),
        });
        page.add(group);

        const enabledRow = new Adw.SwitchRow({
            title: _('Enabled'),
            subtitle: _('Enable or disable the shortcut.'),
        });
        group.add(enabledRow);
        settings.bind('enabled', enabledRow, 'active',
            Gio.SettingsBindFlags.DEFAULT);

        // Capture button: click, then press the combination.
        const defaultHint = _('Click the button, then press the combination.');
        const triggerRow = new Adw.ActionRow({
            title: _('Combination'),
            subtitle: defaultHint,
        });
        const setHint = (msg, error) => {
            triggerRow.subtitle = msg;
            if (error)
                triggerRow.add_css_class('error');
            else
                triggerRow.remove_css_class('error');
        };
        const rejectHint = _('Use a modifier (Ctrl, Alt, Super…) or a function key.');

        const button = new Gtk.Button({
            valign: Gtk.Align.CENTER,
            has_frame: true,
        });

        const accelLabel = (arr) => {
            const a = arr && arr.length ? arr[0] : '';
            return a ? a : _('Disabled');
        };
        const refreshButton = () => {
            button.label = accelLabel(settings.get_strv(SHORTCUT_KEY));
        };
        refreshButton();

        let capturing = false;
        const keyController = new Gtk.EventControllerKey();
        button.add_controller(keyController);

        const stopCapture = () => {
            capturing = false;
            refreshButton();
        };

        button.connect('clicked', () => {
            if (capturing) {
                stopCapture();
                return;
            }
            capturing = true;
            button.label = _('Press a key…');
            button.grab_focus();
        });

        keyController.connect('key-pressed', (_c, keyval, _keycode, state) => {
            if (!capturing)
                return Gdk.EVENT_PROPAGATE;

            // Escape cancels; Backspace/Delete clears.
            if (keyval === Gdk.KEY_Escape) {
                stopCapture();
                return Gdk.EVENT_STOP;
            }
            if (keyval === Gdk.KEY_BackSpace || keyval === Gdk.KEY_Delete) {
                settings.set_strv(SHORTCUT_KEY, []);
                stopCapture();
                return Gdk.EVENT_STOP;
            }

            if (this._isModifierKey(keyval))
                return Gdk.EVENT_STOP;

            const mask = state & Gtk.accelerator_get_default_mod_mask();
            if (!Gtk.accelerator_valid(keyval, mask))
                return Gdk.EVENT_STOP;

            // A bare letter is a valid accelerator for GTK but would open
            // the picker on every press of that letter: refuse it.
            if (!shortcutAcceptable(keyval, mask)) {
                setHint(rejectHint, true);
                stopCapture();
                return Gdk.EVENT_STOP;
            }
            setHint(defaultHint, false);
            settings.set_strv(SHORTCUT_KEY, [Gtk.accelerator_name(keyval, mask)]);
            stopCapture();
            return Gdk.EVENT_STOP;
        });

        triggerRow.add_suffix(button);
        triggerRow.activatable_widget = button;
        group.add(triggerRow);

        // Text fallback: type the accelerator by hand.
        const entryRow = new Adw.EntryRow({
            title: _('Accelerator (text)'),
        });
        const syncEntry = () => {
            const arr = settings.get_strv(SHORTCUT_KEY);
            entryRow.text = arr && arr.length ? arr[0] : '';
        };
        syncEntry();
        entryRow.connect('apply', () => {
            const txt = entryRow.text.trim();
            if (txt === '') {
                settings.set_strv(SHORTCUT_KEY, []);
                return;
            }
            // Only store what parses and passes the same rule as the
            // capture; otherwise put the stored value back in the entry.
            const [ok, keyval, mods] = Gtk.accelerator_parse(txt);
            if (!ok || !Gtk.accelerator_valid(keyval, mods) || !shortcutAcceptable(keyval, mods)) {
                setHint(rejectHint, true);
                syncEntry();
                return;
            }
            setHint(defaultHint, false);
            settings.set_strv(SHORTCUT_KEY, [Gtk.accelerator_name(keyval, mods)]);
        });
        group.add(entryRow);

        const changedId = settings.connect(`changed::${SHORTCUT_KEY}`, () => {
            refreshButton();
            syncEntry();
        });
        disconnectOnDestroy(group, settings, changedId);
    }

    _isModifierKey(keyval) {
        switch (keyval) {
            case Gdk.KEY_Shift_L:
            case Gdk.KEY_Shift_R:
            case Gdk.KEY_Control_L:
            case Gdk.KEY_Control_R:
            case Gdk.KEY_Alt_L:
            case Gdk.KEY_Alt_R:
            case Gdk.KEY_Super_L:
            case Gdk.KEY_Super_R:
            case Gdk.KEY_Meta_L:
            case Gdk.KEY_Meta_R:
            case Gdk.KEY_Hyper_L:
            case Gdk.KEY_Hyper_R:
            case Gdk.KEY_Caps_Lock:
            case Gdk.KEY_ISO_Level3_Shift:
                return true;
            default:
                return false;
        }
    }

    _buildBehaviorGroup(page, settings) {
        const group = new Adw.PreferencesGroup({
            title: _('Behavior'),
        });
        page.add(group);

        const delayRow = new Adw.SpinRow({
            title: _('Delay before display'),
            subtitle: _('Milliseconds before the shortcut picker appears (press and hold is not delayed).'),
            adjustment: new Gtk.Adjustment({
                lower: 0,
                upper: 1000,
                step_increment: 10,
                page_increment: 100,
            }),
        });
        group.add(delayRow);
        settings.bind('delay-ms', delayRow, 'value',
            Gio.SettingsBindFlags.DEFAULT);

        const timeoutRow = new Adw.SpinRow({
            title: _('Auto-close (failsafe)'),
            subtitle: _('Milliseconds before automatic close.'),
            adjustment: new Gtk.Adjustment({
                lower: 1000,
                upper: 30000,
                step_increment: 250,
                page_increment: 1000,
            }),
        });
        group.add(timeoutRow);
        settings.bind('popup-timeout-ms', timeoutRow, 'value',
            Gio.SettingsBindFlags.DEFAULT);
    }

    _buildAccentsGroup(page, settings, window) {
        const group = new Adw.PreferencesGroup({
            title: _('Accentable characters'),
            description: _('JSON table: base letter → list of accented variants.'),
        });
        page.add(group);

        const defaultJson = JSON.stringify(DEFAULT_ACCENTS, null, 2);

        const buffer = new Gtk.TextBuffer();
        const loadFromSettings = () => {
            const stored = settings.get_string('accents');
            buffer.text = stored && stored.trim() !== '' ? stored : defaultJson;
        };
        loadFromSettings();

        const textView = new Gtk.TextView({
            buffer: buffer,
            monospace: true,
            top_margin: 8,
            bottom_margin: 8,
            left_margin: 8,
            right_margin: 8,
            wrap_mode: Gtk.WrapMode.WORD_CHAR,
        });

        const scrolled = new Gtk.ScrolledWindow({
            min_content_height: 220,
            vexpand: true,
            hscrollbar_policy: Gtk.PolicyType.AUTOMATIC,
            vscrollbar_policy: Gtk.PolicyType.AUTOMATIC,
        });
        scrolled.add_css_class('card');
        scrolled.set_child(textView);
        group.add(scrolled);

        const statusRow = new Adw.ActionRow({
            title: 'JSON',
            subtitle: _('Modified = saved automatically.'),
        });

        const saveButton = new Gtk.Button({
            label: _('Save'),
            valign: Gtk.Align.CENTER,
        });
        const resetButton = new Gtk.Button({
            label: _('Reset'),
            valign: Gtk.Align.CENTER,
        });
        resetButton.add_css_class('destructive-action');

        const setStatus = (msg, error) => {
            statusRow.subtitle = msg;
            if (error)
                statusRow.add_css_class('error');
            else
                statusRow.remove_css_class('error');
        };

        const save = () => {
            const text = buffer.text.trim();
            if (text === '' || text === defaultJson.trim()) {
                settings.set_string('accents', '');
                setStatus(_('Built-in default table active.'), false);
                return;
            }
            if (parseTable(text) === null) {
                setStatus(_('Not saved: expected {"e": ["é", "è"], …} — an object of string lists.'), true);
                return;
            }
            settings.set_string('accents', text);
            setStatus(_('Saved.'), false);
        };

        saveButton.connect('clicked', save);

        // Debounced auto-save while typing.
        let saveTimer = 0;
        buffer.connect('changed', () => {
            if (saveTimer)
                GLib.source_remove(saveTimer);
            saveTimer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 600, () => {
                saveTimer = 0;
                save();
                return GLib.SOURCE_REMOVE;
            });
        });
        // Closing the window within the debounce: save now rather than
        // leaving a timeout behind (or losing the edit).
        window.connect('close-request', () => {
            if (saveTimer) {
                GLib.source_remove(saveTimer);
                saveTimer = 0;
                save();
            }
            return false;
        });

        resetButton.connect('clicked', () => {
            settings.set_string('accents', '');
            buffer.text = defaultJson;
            setStatus(_('Reset to the built-in table.'), false);
        });

        statusRow.add_suffix(saveButton);
        statusRow.add_suffix(resetButton);
        group.add(statusRow);
    }

    _buildLayoutsGroup(page, settings) {
        const group = new Adw.PreferencesGroup({
            title: _('Keyboards'),
            description: _('Layouts where press and hold and the shortcut are active (none checked = all active).'),
        });
        page.add(group);

        let sources = [];
        const inputSettings = new Gio.Settings({
            schema_id: 'org.gnome.desktop.input-sources',
        });
        // 'sources' is an a(ss) of (type, id), e.g. ('xkb', 'fr+oss').
        const variant = inputSettings.get_value('sources');
        const n = variant.n_children();
        for (let i = 0; i < n; i++) {
            const child = variant.get_child_value(i);
            const type = child.get_child_value(0).get_string()[0];
            const id = child.get_child_value(1).get_string()[0];
            if (type === 'xkb')
                sources.push(id);
        }

        sources = [...new Set(sources)];

        if (sources.length === 0) {
            const empty = new Adw.ActionRow({
                title: _('No xkb layout detected'),
                subtitle: _('Accent Hold is active on all keyboards.'),
            });
            group.add(empty);
            return;
        }

        const enabledLayouts = () => settings.get_strv('layouts');
        const labels = layoutLabels();

        for (const id of sources) {
            const label = labels[id] || id;
            const row = new Adw.SwitchRow({
                title: label,
                subtitle: id,
            });
            // Checked when listed in `layouts`, or when `layouts` is empty (all on).
            const current = enabledLayouts();
            row.active = current.length === 0 || current.includes(id);

            row.connect('notify::active', () => {
                let list = enabledLayouts();
                const allIds = sources;
                // Materialize the implicit "all" list before editing it.
                if (list.length === 0)
                    list = [...allIds];

                const set = new Set(list);
                if (row.active)
                    set.add(id);
                else
                    set.delete(id);

                let next = allIds.filter(x => set.has(x));
                // All checked => empty list (the "all" default).
                if (next.length === allIds.length)
                    next = [];
                settings.set_strv('layouts', next);
            });

            group.add(row);
        }
    }
}

// Disconnect a settings handler when the widget is destroyed.
function disconnectOnDestroy(widget, settings, handlerId) {
    widget.connect('destroy', () => {
        if (handlerId) {
            settings.disconnect(handlerId);
            handlerId = 0;
        }
    });
}

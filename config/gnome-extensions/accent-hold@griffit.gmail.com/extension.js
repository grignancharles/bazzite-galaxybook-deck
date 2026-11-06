import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension, gettext as _} from 'resource:///org/gnome/shell/extensions/extension.js';
import {AccentPicker} from './accentPicker.js';
import {PressHold} from './pressHold.js';
import {addIndicator} from './panelIndicator.js';
import {DEFAULT_ACCENTS, parseTable} from './defaultAccents.js';

// Mutter keybinding names are global to the session, so the shortcut's
// settings key (which is also its keybinding name) carries the extension's
// name.
const SHORTCUT_KEY = 'accent-hold-shortcut';
const OLD_SHORTCUT_KEY = 'trigger';

// Hold an accentable letter to choose its accented variant (pressHold.js), or
// press the picker shortcut (e.g. <Super>e) then type the base letter.
export default class AccentHoldExtension extends Extension {
    enable() {
        this._settings = this.getSettings();
        this._migrateShortcutKey();
        this._table = this._loadTable();
        this._bound = false;

        this._picker = new AccentPicker(
            this._settings,
            () => this._table,
            _,
        );

        this._bind();

        this._pressHold = new PressHold(this._settings, () => this._table);

        this._indicator = null;
        if (this._settings.get_boolean('show-indicator'))
            this._addIndicator();

        const rebind = () => {
            this._unbind();
            this._bind();
        };
        const toggleIndicator = () => {
            if (this._settings.get_boolean('show-indicator'))
                this._addIndicator();
            else
                this._removeIndicator();
        };
        const reloadTable = () => {
            this._table = this._loadTable();
        };
        // No handler for the shortcut key itself: Mutter watches the settings
        // key given to addKeybinding() and rebinds on its own.
        this._settings.connectObject(
            'changed::enabled', rebind,
            'changed::accents', reloadTable,
            'changed::show-indicator', toggleIndicator,
            this);
    }

    disable() {
        this._unbind();
        this._removeIndicator();

        if (this._pressHold) {
            this._pressHold.destroy();
            this._pressHold = null;
        }
        if (this._picker) {
            this._picker.destroy();
            this._picker = null;
        }
        if (this._settings) {
            this._settings.disconnectObject(this);
            this._settings = null;
        }
        this._table = null;
    }

    _addIndicator() {
        if (this._indicator)
            return;
        const iconPath = this.path + '/icons/accent-hold-symbolic.svg';
        this._indicator = addIndicator(
            this.uuid,
            this._settings,
            iconPath,
            () => this.openPreferences(),
            _,
        );
    }

    _removeIndicator() {
        if (this._indicator) {
            this._indicator.destroy();
            this._indicator = null;
        }
    }

    _bind() {
        if (this._bound)
            return;
        if (!this._settings.get_boolean('enabled'))
            return;
        Main.wm.addKeybinding(
            SHORTCUT_KEY,
            this._settings,
            Meta.KeyBindingFlags.NONE,
            // Not active on the lock screen.
            Shell.ActionMode.NORMAL | Shell.ActionMode.OVERVIEW,
            () => this._picker.start(),
        );
        this._bound = true;
    }

    _unbind() {
        if (!this._bound)
            return;
        Main.wm.removeKeybinding(SHORTCUT_KEY);
        this._bound = false;
    }

    // 2.1 stored the shortcut under `trigger`. Carry a customized value over
    // once, then reset the old key so this never runs again.
    _migrateShortcutKey() {
        const old = this._settings.get_user_value(OLD_SHORTCUT_KEY);
        if (old === null)
            return;
        if (this._settings.get_user_value(SHORTCUT_KEY) === null)
            this._settings.set_value(SHORTCUT_KEY, old);
        this._settings.reset(OLD_SHORTCUT_KEY);
    }

    // Use the user's `accents` override when set and well-formed, otherwise
    // the built-in table. A malformed override is reported once, not on
    // every key press.
    _loadTable() {
        const override = this._settings.get_string('accents');
        if (!override || override.trim() === '')
            return DEFAULT_ACCENTS;
        const table = parseTable(override);
        if (table)
            return table;
        if (!this._tableWarned) {
            this._tableWarned = true;
            console.warn('accent-hold: the "accents" setting is not a table of ' +
                'string arrays ({"e": ["é", "è"]}); using the built-in table');
        }
        return DEFAULT_ACCENTS;
    }
}

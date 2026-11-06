import Gio from 'gi://Gio';
import GObject from 'gi://GObject';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

// Top-bar indicator: the extension icon plus a menu with a toggle bound to the
// `enabled` setting and a shortcut to the preferences.
export const AccentHoldIndicator = GObject.registerClass(
class AccentHoldIndicator extends PanelMenu.Button {
    _init(settings, iconPath, openPreferences, gettext) {
        const _ = gettext || ((s) => s);
        super._init(0.0, _('Accent Hold'));

        this._settings = settings;
        this._openPreferences = openPreferences;

        this.add_child(new St.Icon({
            gicon: Gio.icon_new_for_string(iconPath),
            style_class: 'system-status-icon',
        }));

        this._toggle = new PopupMenu.PopupSwitchMenuItem(
            _('Enabled'), this._settings.get_boolean('enabled'));
        this._toggle.connectObject('toggled', (_item, state) => {
            if (this._settings.get_boolean('enabled') !== state)
                this._settings.set_boolean('enabled', state);
        }, this);
        this.menu.addMenuItem(this._toggle);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        const prefsItem = new PopupMenu.PopupMenuItem(_('Preferences'));
        prefsItem.connectObject('activate', () => this._openPreferences(), this);
        this.menu.addMenuItem(prefsItem);

        // Keep the toggle in sync when `enabled` changes elsewhere.
        this._settings.connectObject('changed::enabled', () => {
            this._toggle.setToggleState(this._settings.get_boolean('enabled'));
        }, this);
    }

    destroy() {
        this._settings.disconnectObject(this);
        this._settings = null;
        this._openPreferences = null;
        this._toggle = null;
        super.destroy();
    }
});

export function addIndicator(uuid, settings, iconPath, openPreferences, gettext) {
    const indicator = new AccentHoldIndicator(settings, iconPath, openPreferences, gettext);
    Main.panel.addToStatusArea(uuid, indicator);
    return indicator;
}

import GObject from 'gi://GObject';
import St from 'gi://St';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Clutter from 'gi://Clutter';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import {Extension, gettext as _} from 'resource:///org/gnome/shell/extensions/extension.js';

const PlingIndicator = GObject.registerClass(
class PlingIndicator extends PanelMenu.Button {
    _init() {
        super._init(0.0, _('Pling Server'));

        let icon = new St.Icon({
            icon_name: 'input-gaming-symbolic',
            style_class: 'system-status-icon',
        });
        this.add_child(icon);

        let headerItem = new PopupMenu.PopupMenuItem('🎮 Pling Meta Quest Streamer', {reactive: false});
        this.menu.addMenuItem(headerItem);

        this._statusItem = new PopupMenu.PopupMenuItem('🟢 Estado: Activo (Puerto 3000)', {reactive: false});
        this.menu.addMenuItem(this._statusItem);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        let guiItem = new PopupMenu.PopupMenuItem('🎛️ Ajustes y Sliders (3D, Gamma, Audio)');
        guiItem.connect('activate', () => {
            GLib.spawn_command_line_async('/usr/local/bin/pling-gui');
        });
        this.menu.addMenuItem(guiItem);

        let restartItem = new PopupMenu.PopupMenuItem('🔄 Reiniciar Servidor Pling');
        restartItem.connect('activate', () => {
            GLib.spawn_command_line_async('systemctl restart pling-server.service');
        });
        this.menu.addMenuItem(restartItem);

        let logsItem = new PopupMenu.PopupMenuItem('📋 Ver Logs de Conexión Quest');
        logsItem.connect('activate', () => {
            GLib.spawn_command_line_async('gnome-terminal -- journalctl -u pling-server.service -f');
        });
        this.menu.addMenuItem(logsItem);

        this._updateStatus();
        this._timer = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 3, () => {
            this._updateStatus();
            return GLib.SOURCE_CONTINUE;
        });
    }

    _updateStatus() {
        try {
            let [res, out, err, status] = GLib.spawn_command_line_sync('systemctl is-active pling-server.service');
            let outStr = new TextDecoder().decode(out).trim();
            if (outStr === 'active') {
                this._statusItem.label.text = '🟢 Pling: En espera / Stream Quest (Puerto 3000)';
            } else {
                this._statusItem.label.text = '🔴 Pling: Detenido';
            }
        } catch (e) {
            this._statusItem.label.text = '🎮 Pling Server';
        }
    }

    destroy() {
        if (this._timer) {
            GLib.source_remove(this._timer);
            this._timer = null;
        }
        super.destroy();
    }
});

export default class PlingExtension extends Extension {
    enable() {
        this._indicator = new PlingIndicator();
        Main.panel.addToStatusArea(this.uuid, this._indicator, 1, 'right');
        this._hidePowerModeElements();
    }

    _hidePowerModeElements() {
        try {
            let qs = Main.panel.statusArea.quickSettings;
            if (qs) {
                // Ocultar selector de perfiles de energia si GNOME Shell lo tuviera instanciado
                if (qs._powerProfilesToggle) {
                    qs._powerProfilesToggle.hide();
                    qs._powerProfilesToggle.visible = false;
                }
                if (qs._system && qs._system._powerProfilesToggle) {
                    qs._system._powerProfilesToggle.hide();
                    qs._system._powerProfilesToggle.visible = false;
                }
                if (qs.menu && qs.menu._grid) {
                    let children = qs.menu._grid.get_children();
                    for (let c of children) {
                        let name = c.constructor ? c.constructor.name : '';
                        let title = c._toggle ? c._toggle.title : '';
                        if (name.includes('PowerProfile') || title === 'Power Mode' || title === 'Modo de energía') {
                            c.hide();
                            c.visible = false;
                        }
                    }
                }
            }
        } catch (e) {
            // Ignorar si el componente no existe
        }
    }

    disable() {
        if (this._indicator) {
            this._indicator.destroy();
            this._indicator = null;
        }
    }
}

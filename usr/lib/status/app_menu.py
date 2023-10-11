#!/usr/bin/python3

from setproctitle import setproctitle

import gi
gi.require_version('CMenu', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('Gtk', '3.0')
gi.require_version('XApp', '1.0')

from gi.repository import CMenu, Gtk, XApp

from status.menu import Menu, MenuChild, MenuItem, MenuSection

APPLICATION_ID = 'org.x.menu'

class AppMenu(Menu):
    def __init__(self):
        super(AppMenu, self).__init__()

        self.tree = CMenu.Tree.new('cinnamon-applications.menu', CMenu.TreeFlags.SHOW_EMPTY)

        self.sidebar = MenuSection()


class MenuApp(Gtk.Application):
    def __init__(self):
        super(MenuApp, self).__init__(application_id=APPLICATION_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)

        self.has_activated = False

    def do_activate(self):
        if self.has_activated:
            self.window.restore()

            return

        Gtk.Application.do_activate(self)

        self.primary_menu = None

        self.status_icon = XApp.StatusIcon(name='menu')
        self.status_icon.set_icon_name('linuxmint-logo-ring-symbolic')

        self.primary_menu = AppMenu()
        # self.status_icon.set_primary_menu(self.primary_menu)

        self.context_menu = Gtk.Menu()

        self.context_menu.append(Gtk.SeparatorMenuItem())

        item = Gtk.MenuItem(label='Quit', visible=True)
        item.connect('activate', self.exit)
        self.context_menu.append(item)

        self.status_icon.set_secondary_menu(self.context_menu)
        self.status_icon.connect('button-release-event', self.on_button_release)

        self.has_activated = True

        provider = Gtk.CssProvider()
        provider.load_from_path(STYLE_SHEET_PATH)

        Gtk.StyleContext.add_provider_for_screen (Gdk.Screen.get_default(), provider, 600)

        # self.update_default_sink()

        self.hold()

    def on_button_release(self, i, x, y, button, t, pos):
        if button == 1:
            rect = Gdk.Rectangle()
            rect.x = x
            rect.y = y

            if pos == Gtk.PositionType.TOP:
                i_gravity = Gdk.Gravity.SOUTH_WEST
                m_gravity = Gdk.Gravity.NORTH_WEST
            elif pos == Gtk.PositionType.BOTTOM:
                i_gravity = Gdk.Gravity.NORTH_WEST
                m_gravity = Gdk.Gravity.SOUTH_WEST
            elif pos == Gtk.PositionType.LEFT:
                i_gravity = Gdk.Gravity.NORTH_WEST
                m_gravity = Gdk.Gravity.NORTH_EAST
            elif pos == Gtk.PositionType.RIGHT:
                i_gravity = Gdk.Gravity.NORTH_EAST
                m_gravity = Gdk.Gravity.NORTH_WEST

            self.primary_menu.show_all()
            self.primary_menu.popup_at_rect(None, rect, i_gravity, m_gravity, None)

    def exit(self, *args):
        self.quit()

if __name__ == '__main__':
    setproctitle('menu')
    app = MenuApp()
    app.run()



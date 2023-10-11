#!/usr/bin/python3

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('XApp', '1.0')

from gi.repository import Gio, Gtk, XApp

APPLICATION_ID = 'org.x.github'


class App(Gtk.Application):
    has_activated = False

    def __init__(self):
        super(App, self).__init__(application_id=APPLICATION_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)

    def do_activate(self):
        try:
            if self.has_activated:
                # self.window.restore()

                return

            self.has_activated = True

            self.status_icon = XApp.StatusIcon(name='github')
            self.status_icon.set_icon_name('web-github')

            self.menu = Gtk.Menu()

            self.menu.append(Gtk.SeparatorMenuItem())

            item = Gtk.MenuItem(label='Quit', visible=True)
            item.connect('activate', self.exit)
            self.menu.append(item)

            self.status_icon.set_primary_menu(self.menu)

            self.builder = Gtk.Builder.new_from_file('/usr/share/status/feeds.ui')
            self.window = self.builder.get_object('main_window')
            self.window.connect('delete-event', self.on_window_close)
            self.add_window(self.window)

            self.feed_stack = self.builder.get_object('feed_stack')

            self.builder.get_object('new_repo_item').connect('activate', self.new_repo)
            self.builder.get_object('manage_item').connect('activate', self.open_manager)
            self.builder.get_object('refresh_item').connect('activate', self.update)
            self.builder.get_object('close_item').connect('activate', self.on_window_close)
            self.builder.get_object('quit_item').connect('activate', self.exit)

            self.hold()

        except Exception as e:
            traceback.print_exc()
            self.quit()

    def new_repo(self, *args):
        print('new_repo')

    def open_manager(self, *args):
        print('open_manager')

    def update(self, *args):
        print('update')

    def on_window_close(self, *args):
        self.window.hide()

        return Gdk.EVENT_STOP

    def exit(self, *args):
        self.quit()

if __name__ == '__main__':
    setproctitle('github')
    app = App()
    app.run()

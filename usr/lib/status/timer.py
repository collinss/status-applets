#!/usr/bin/python3

import datetime

from setproctitle import setproctitle

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Notify', '0.7')
gi.require_version('XApp', '1.0')

from gi.repository import Gio, GLib, Gtk, Notify, XApp

APPLICATION_ID = 'org.x.timer'

Notify.init('timer')

class TimerBase(object):
    # def get_duration(self):
    #     raise NotImplementedError('function "get_duration" not implemented in subclass')

    def get_remaining(self):
        raise NotImplementedError('function "get_remaining" not implemented in subclass')

    def activate(self):
        Notify.Notification.new('timer elapsed').show()
        print('hello world')

class Alarm(TimerBase):
    def __init__(self, time):
        super(Alarm, self).__init__()
        self.time = time

        remaining = (time - datetime.datetime.now()).total_seconds()

        self.callback_id = GLib.timeout_add_seconds(remaining, self.activate)

    def get_remaining(self):
        return True

class App(Gtk.Application):
    has_activated = False

    def __init__(self):
        super(App, self).__init__(application_id=APPLICATION_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)

    def do_activate(self):
        if self.has_activated:
            # self.window.restore()

            return

        self.has_activated = True

        self.status_icon = XApp.StatusIcon(name='timer')
        self.status_icon.set_icon_name('preferences-system-time-symbolic')

        self.menu = Gtk.Menu()

        self.menu.append(Gtk.SeparatorMenuItem())

        item = Gtk.MenuItem(label='Quit', visible=True)
        item.connect('activate', self.exit)
        self.menu.append(item)

        self.status_icon.set_secondary_menu(self.menu)

        self.add_alarm()

        self.hold()

    def add_alarm(self):
        Alarm(datetime.datetime.now() + datetime.timedelta(seconds=5))

    def exit(self, *args):
        self.quit()

if __name__ == '__main__':
    setproctitle('timer')
    app = App()
    app.run()

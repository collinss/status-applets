#!/usr/bin/python3

import requests
from bs4 import BeautifulSoup as bs
from setproctitle import setproctitle

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('XApp', '1.0')

from gi.repository import Gio, Gtk, XApp

APPLICATION_ID = 'org.x.sanderson'
SCHEMA = 'org.xstatus.sanderson'

class App(Gtk.Application):
    has_activated = False

    def __init__(self):
        super(App, self).__init__(application_id=APPLICATION_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)

    def do_activate(self):
        if self.has_activated:
            # self.window.restore()

            return

        self.has_activated = True

        self.current_status = {}

        self.settings = Gio.Settings(schema_id=SCHEMA)

        self.status_icon = XApp.StatusIcon(name='sanderson')
        self.status_icon.set_icon_name('sanderson-symbolic')

        self.menu = Gtk.Menu()

        self.menu.append(Gtk.SeparatorMenuItem())

        item = Gtk.MenuItem(label='Quit', visible=True)
        item.connect('activate', self.exit)
        self.menu.append(item)

        self.status_icon.set_primary_menu(self.menu)

        self.menu.connect('popped-up', self.save)

        self.get_status()

        self.hold()

    def get_status(self):
        request = requests.get('https://www.brandonsanderson.com/')
        parser = bs(request.text, features="lxml")

        content = parser.find(id='content')
        progress_box_contents = parser.find(string='PROGRESS BARS').parent.parent.find(class_='vc_progress_bar').contents

        # for child in progress_box.contents:
        #     print(child)
        projects = self.settings.get_string('status').split(',')
        old_status = {}
        for project in projects:
            if project == '':
                continue
            [name, value] = project.split(':')
            old_status[name] = value

        has_update = False
        self.current_status = {}
        for i in range(4):
            # print('name', progress_box_contents[2*i].contents[0])
            name = progress_box_contents[2*i].contents[0]
            # print('number', progress_box_contents[2*i+1].contents[0]['data-value'])
            number = progress_box_contents[2*i+1].contents[0]['data-value']
            self.current_status[name] = number
            text = '%s - %s%%' % (name, number)
            if name not in old_status:
                has_update = True
                text += ' (new)'
            elif old_status[name] != number:
                has_update = True
                text += ' (was %s%%)' % old_status[name]
            item = Gtk.MenuItem(label=text, visible=True)
            self.menu.insert(item, i)

        if has_update:
            self.status_icon.set_icon_name('sanderson-new-symbolic')

        # self.menu.add(Gtk.Label())

        # for lines in request.readlines():
            # print (lines)

    def save(self, *args):
        print('saving')
        lst = []
        for name, number in self.current_status.items():
            lst.append('%s:%s' % (name, number))

        self.settings.set_string('status', ','.join(lst))

        self.status_icon.set_icon_name('sanderson-symbolic')

    def exit(self, *args):
        self.quit()

if __name__ == '__main__':
    setproctitle('sanderson')
    app = App()
    app.run()

#!/usr/bin/python3

import feedparser
import html
import json
import threading
import traceback
from setproctitle import setproctitle

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('XApp', '1.0')

from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Pango, XApp

APPLICATION_ID = 'org.xstatus.feeds'
SCHEMA = 'org.xstatus.feeds'
TIMEOUT = 15 * 60

class FeedItem(GObject.Object):
    @GObject.Signal(flags=GObject.SignalFlags.RUN_LAST, return_type=bool,
                    arg_types=(str,),
                    accumulator=GObject.signal_accumulator_true_handled)
    def marked_read(self, item_id):
        pass

    def __init__(self, info, unread):
        super(FeedItem, self).__init__()
        self.info = info
        self.title = info.title
        self.link = info.link
        self.item_id = info.id
        self.unread = unread
        if 'description' in info and info.description != '':
            self.description = info.description
        elif 'summary' in info and info.summary != '':
            self.description = info.summary
        else:
            self.description = None

        self.published = info.published

    def create_widget(self):
        row = Gtk.ListBoxRow()
        row.item = self

        main_box = Gtk.Box(spacing=5, margin_top=10, margin_bottom=5, margin_left=10, margin_right=10)
        row.add(main_box)

        unread_marker = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL, width_request=4)
        main_box.pack_start(unread_marker, False, False, 0)
        self.unread_marker_style_manager = XApp.StyleManager(widget=unread_marker)
        self.update_marker()

        v_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        main_box.pack_start(v_box, False, False, 0)

        title = Gtk.Label(label='<span size="larger" weight="bold">%s</span>' % html.escape(self.title), use_markup=True, ellipsize=Pango.EllipsizeMode.END, halign=Gtk.Align.START)
        v_box.pack_start(title, False, False, 0)

        published = Gtk.Label(label='<span size="smaller" style="italic">Published: %s</span>' % self.published, use_markup=True, halign=Gtk.Align.START)
        v_box.pack_start(published, False, False, 0)

        if self.description:
            description = Gtk.Label(label=self.description, wrap=True, lines=3, ellipsize=Pango.EllipsizeMode.END, justify=Gtk.Justification.FILL, halign=Gtk.Align.START)
            v_box.pack_start(description, False, False, 0)

        launch_button = Gtk.Button.new_from_icon_name('player_start', Gtk.IconSize.LARGE_TOOLBAR)
        launch_button.set_valign(Gtk.Align.CENTER)
        launch_button.connect('clicked', self.launch)
        main_box.pack_end(launch_button, False, False, 0)

        row.set_tooltip_text(html.escape(self.title))

        row.show_all()

        return row

    def launch(self, *args):
        self.mark_read()
        Gtk.show_uri(None, self.link, Gdk.CURRENT_TIME)

    def mark_read(self, *args):
        if not self.unread:
            return

        self.unread = False
        self.update_marker()
        self.emit('marked-read', self.item_id)

    def update_marker(self):
        if self.unread:
            self.unread_marker_style_manager.set_style_property('background-color', 'rgba(150, 200, 255, .75)')
        else:
            self.unread_marker_style_manager.set_style_property('background-color', 'rgba(150, 200, 255, 0)')

class Feed(GObject.Object):
    @GObject.Signal(flags=GObject.SignalFlags.RUN_LAST, return_type=bool,
                    accumulator=GObject.signal_accumulator_true_handled)
    def unread_changed(self):
        pass

    def __init__(self, settings, name, url, read_ids=[]):
        super(Feed, self).__init__()
        self.settings = settings
        self.name = name
        self.url = url
        self.read_ids = read_ids
        self.items = []

        self.has_unread = False

        self.page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        toolbar = Gtk.Toolbar()
        self.page.pack_start(toolbar, False, False, 0)

        button = Gtk.ToolButton(icon_name='mail-read-symbolic')
        toolbar.add(button)
        button.connect('clicked', self.mark_all_read)

        button = Gtk.ToolButton(icon_name='view-refresh-symbolic')
        toolbar.add(button)
        button.connect('clicked', self.check_for_updates)

        scrolled_window = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.page.pack_start(scrolled_window, True, True, 0)

        self.list_box = Gtk.ListBox(visible=True)
        self.model = Gio.ListStore(item_type=FeedItem)
        scrolled_window.add(self.list_box)

        def create_widget(item):
            widget = item.create_widget()
            item.connect('marked-read', self.on_child_marked_read)

            return widget

        self.page.show_all()

        self.list_box.bind_model(self.model, create_widget)

        # self.check_for_updates()

    def check_for_updates(self, *args):
        thread = threading.Thread(target=self._fetch_url)
        thread.start()

    def _fetch_url(self):
        a = feedparser.parse(self.url) # move this to thread
        GLib.idle_add(self._parse_url, a)

    def _parse_url(self, parser):
        self.has_unread = False
        self.items = []
        self.model.remove_all()
        for info in parser['entries']:
            is_unread = info.id not in self.read_ids
            if is_unread:
                self.has_unread = True
            item = FeedItem(info, is_unread)
            self.model.append(item)
            self.items.append(item)

        if self.has_unread:
            self.emit('unread-changed')

    def on_child_marked_read(self, i, item_id):
        read_ids = json.loads(self.settings.get_string('already-read'))
        if self.url not in read_ids:
            read_ids[self.url] = []
        read_ids[self.url].append(item_id)
        self.settings.set_string('already-read', json.dumps(read_ids))

        self.has_unread = False
        for item in self.items:
            if item.unread:
                self.has_unread = True

        self.emit('unread-changed')

    def mark_all_read(self, *args):
        for item in self.items:
            item.mark_read()

class App(Gtk.Application):
    def __init__(self):
        super(App, self).__init__(application_id=APPLICATION_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)

        self.has_activated = False
        self.feeds = []

    def do_activate(self):
        try:
            if self.has_activated:
                self.raise_window()

                return

            Gtk.Application.do_activate(self)

            self.settings = Gio.Settings(schema_id=SCHEMA)

            self.status_icon = XApp.StatusIcon(name='temps')
            self.status_icon.set_icon_name('feeds-symbolic')

            self.menu = Gtk.Menu()

            item = Gtk.MenuItem(label='Reload', visible=True)
            item.connect('activate', self.update_feeds)
            self.menu.append(item)

            self.menu.append(Gtk.SeparatorMenuItem())

            item = Gtk.MenuItem(label='Quit', visible=True)
            item.connect('activate', self.exit)
            self.menu.append(item)

            self.status_icon.set_secondary_menu(self.menu)
            self.status_icon.connect('button-press-event', self.on_button_press)

            self.builder = Gtk.Builder.new_from_file('/usr/share/status/feeds.ui')
            self.window = self.builder.get_object('main_window')
            self.window.connect('delete-event', self.on_window_close)
            self.add_window(self.window)

            self.feed_stack = self.builder.get_object('feed_stack')

            self.builder.get_object('new_feed_item').connect('activate', self.new_feed)
            self.builder.get_object('refresh_item').connect('activate', self.update_feeds)
            self.builder.get_object('close_item').connect('activate', self.on_window_close)
            self.builder.get_object('quit_item').connect('activate', self.exit)

            self.update_feeds()
            GLib.timeout_add_seconds(TIMEOUT, self.update_feeds)

            self.has_activated = True

            self.hold()

        except Exception as e:
            traceback.print_exc()
            self.quit()

    def update_feeds(self, *args):
        for feed in self.feeds:
            self.feed_stack.remove(feed.page)
        self.feeds = []
        self.feed_stack.foreach(lambda a: self.feed_stack.remove(a))

        feeds = self.settings.get_value('subscribed-feeds').unpack()
        for (name, url) in feeds:
            read_ids = json.loads(self.settings.get_string('already-read'))
            if url in read_ids:
                feed = Feed(self.settings, name, url, read_ids[url])
            else:
                feed = Feed(self.settings, name, url)
            feed.connect('unread-changed', self.on_unread_changed)
            self.feeds.append(feed)
            self.feed_stack.add_titled(feed.page, name, name)

        self.check_feeds()

    def on_button_press(self, i, x, y, button, time, p):
        if button == 1:
            if self.window.is_visible():
                self.window.hide()
            else:
                self.window.show()
                self.window.present_with_time(time)

            return Gdk.EVENT_STOP

        return Gdk.EVENT_PROPAGATE

    def on_window_close(self, *args):
        self.window.hide()

        return Gdk.EVENT_STOP

    def check_feeds(self, *args):
        print('checking')
        updates = False
        for feed in self.feeds:
            if feed.check_for_updates():
                updates = True

    def new_feed(self, *args):
        dialog = Gtk.Dialog()

        dialog = Gtk.Dialog(title='New Feed', transient_for=self.window)
        dialog.add_button('Cancel', Gtk.ResponseType.CANCEL)
        dialog.add_button('OK', Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.OK)

        content = dialog.get_content_area()
        content.props.margin_left = 20
        content.props.margin_right = 20

        content.pack_start(Gtk.Label(label='Title'), False, False, 10)
        title_entry = Gtk.Entry(activates_default=True)
        content.pack_start(title_entry, False, False, 10)

        content.pack_start(Gtk.Label(label='Url'), False, False, 10)
        url_entry = Gtk.Entry(activates_default=True)
        content.pack_start(url_entry, False, False, 10)

        content.show_all()

        if dialog.run() == Gtk.ResponseType.OK:
            title = title_entry.get_text()
            url = url_entry.get_text()

            feeds = self.settings.get_value('subscribed-feeds').unpack()
            feeds.append((title, url))
            self.settings.set_value('subscribed-feeds', GLib.Variant('a(ss)', feeds))

            self.update_feeds()

        dialog.destroy()

    def on_unread_changed(self, *args):
        unread = False
        for feed in self.feeds:
            if feed.has_unread:
                self.feed_stack.child_set(feed.page, needs_attention=True)
                unread = True
            else:
                self.feed_stack.child_set(feed.page, needs_attention=False)

        if unread:
            self.status_icon.set_icon_name('feeds-new-symbolic')
        else:
            self.status_icon.set_icon_name('feeds-symbolic')


    def exit(self, *args):
        self.quit()


if __name__ == '__main__':
    setproctitle('feeds')
    app = App()
    app.run()

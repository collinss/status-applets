#!/usr/bin/python3

import re
import subprocess
import time
from setproctitle import setproctitle

import gettext
gettext.install("sound", "/usr/share/locale")

import gi
gi.require_version('CMenu', '3.0')
gi.require_version('Cvc', '1.0')
gi.require_version('Gdk', '3.0')
gi.require_version('Gtk', '3.0')
gi.require_version('PangoCairo', '1.0')
gi.require_version('XApp', '1.0')

from gi.repository import CMenu, Cvc, Gdk, GdkPixbuf, Gio, GLib, Gtk, Pango, PangoCairo, XApp

from xapp.GSettingsWidgets import *

# from status.menu import Menu, MenuChild, MenuItem, MenuSection

APPLICATION_ID = 'org.x.sound'
STYLE_SHEET_PATH = '/usr/share/status/sound.css'

SCROLL_STEP = 5
ANIMATION_LENGTH = 50000 # in us

MPRIS_NAME_REGEX_STRING = r"^org\.mpris\.MediaPlayer2\."
MPRIS_NAME_REGEX = re.compile(MPRIS_NAME_REGEX_STRING, re.IGNORECASE)

DBUS_IFACE_NAME = 'org.freedesktop.DBus'
DBUS_PROPERTIES_IFACE_NAME = 'org.freedesktop.DBus.Properties'
MPRIS_IFACE_NAME = 'org.mpris.MediaPlayer2'
MPRIS_PLAYER_IFACE_NAME = 'org.mpris.MediaPlayer2.Player'
DBUS_PATH = '/org/freedesktop/DBus'
MPRIS_PATH = '/org/mpris/MediaPlayer2'

CINNAMON_DESKTOP_SOUND_SCHEMA = 'org.cinnamon.desktop.sound'
SCHEMA = 'org.x.sound'

def get_volume_icon(volume, is_mic=False):
    if is_mic:
        device = 'microphone-sensitivity'
    else:
        device = 'audio-volume'

    if volume == 0:
        level = 'muted'
    elif volume < 50:
        level = 'low'
    elif volume < 100:
        level = 'medium'
    else:
        level = 'high'

    return f'{device}-{level}-symbolic'

def seconds_to_time_string(seconds):
    if seconds >= 3600:
        time_string = time.strftime('%H:%M:%S', time.gmtime(seconds))
    else:
        time_string = time.strftime('%M:%S', time.gmtime(seconds))

    if time_string[0] == '0':
        return time_string[1:]
    else:
        return time_string
    # time_string = ''

    # if seconds >= 3600:
    #     time_string += str(int(seconds / 3600)) + ':'
    #     seconds = seconds % 3600

    # print(seconds / 60)
    # time_string += str(int(seconds / 60)) + ':' + str(int(seconds % 60))
    # # seconds = seconds % 60

    # # time_string += str

    # print(time_string)

    # return time_string

class VolumeSliderMenuItem(Gtk.Box, XApp.MenuChild):
    def __init__(self, stream, norm_volume, max_volume):
        super(VolumeSliderMenuItem, self).__init__()
        # print('stream', stream)
        self.stream = None

        self.norm_volume = norm_volume
        # self.max_volume = max_volume

        self.stream_volume_id = 0
        self.stream_muted_id = 0

        # box = Gtk.Box()
        # self.add(box)

        self.mute_image = Gtk.Image(icon_name='audio-volume-muted-symbolic', icon_size=Gtk.IconSize.MENU)
        self.mute_button = Gtk.Button(image=self.mute_image, relief=Gtk.ReliefStyle.NONE, sensitive=False)
        self.pack_start(self.mute_button, False, False, 0)
        self.mute_button.connect('clicked', self.toggle_mute)

        self.volume_slider_adjustment = Gtk.Adjustment(value=0, lower=0, step_increment=1, page_increment=5)
        # print(f'slider max: {self.volume_slider_adjustment.get_upper()}, norm: {self.norm_volume}, max: {self.max_volume}')
        self.volume_slider = Gtk.Scale(adjustment=self.volume_slider_adjustment, draw_value=False, sensitive=False, width_request=150, margin_end=10)
        self.pack_start(self.volume_slider, True, True, 10)
        self.slider_volume_id = self.volume_slider.get_adjustment().connect('value-changed', self.on_slider_value_changed)

        self.set_max_volume(max_volume)

        if stream:
            self.set_stream(stream)

    def set_max_volume(self, max_volume):
        # print('setting')
        self.max_volume = max_volume
        self.volume_slider.clear_marks()
        self.volume_slider_adjustment.set_upper(self.max_volume * 100 / self.norm_volume)

        if self.max_volume > self.norm_volume:
            self.volume_slider.add_mark(100, Gtk.PositionType.TOP, None)

    def toggle_mute(self, *args):
        muted = not self.stream.get_is_muted()
        self.stream.change_is_muted(muted)

    def on_slider_value_changed(self, *args):
        volume = round(self.volume_slider.get_value())

        self.stream.handler_block(self.stream_volume_id)
        self.stream.set_volume(round(volume * self.norm_volume / 100))
        self.stream.push_volume()
        self.stream.handler_unblock(self.stream_volume_id)

        self.volume_slider.set_tooltip_text(str(volume) + '%')
        self.set_mute_icon(volume)

    def set_mute_icon(self, volume):
        if self.stream.get_is_muted():
            volume = 0

        self.mute_image.props.icon_name = get_volume_icon(volume)

    def set_stream(self, stream):
        if self.stream:
            self.stream.disconnect(self.stream_volume_id)
            self.stream.disconnect(self.stream_muted_id)

        self.stream = stream

        if self.stream:
            self.mute_button.set_sensitive(True)
            self.volume_slider.set_sensitive(True)

        self.update_volume()

        self.stream_volume_id = self.stream.connect('notify::volume', self.update_volume)
        self.stream_muted_id = self.stream.connect('notify::is-muted', self.update_volume)

    def update_volume(self, *args):
        volume = round(self.stream.props.volume / self.norm_volume * 100)
        self.set_mute_icon(volume)

        self.volume_slider.get_adjustment().handler_block(self.slider_volume_id)
        self.volume_slider.set_value(volume)
        self.volume_slider.set_tooltip_text(str(volume) + '%')
        self.volume_slider.get_adjustment().handler_unblock(self.slider_volume_id)

class Seeker(Gtk.DrawingArea):
    @GObject.Signal(flags=GObject.SignalFlags.RUN_LAST, return_type=bool,
                    arg_types=(float,),
                    accumulator=GObject.signal_accumulator_true_handled)
    def seeked(self, value):
        pass

    def __init__(self, **kwargs):
        super(Seeker, self).__init__(height_request=7, name='seeker', **kwargs)

        self.fraction = 0
        self.animate_id = 0
        self.show_label = False
        self.label = ''
        self.grabbed = False
        self.button_release_id = 0
        self.motion_notify_id = 0

        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK     |
                        Gdk.EventMask.BUTTON_RELEASE_MASK   |
                        Gdk.EventMask.SCROLL_MASK           |
                        Gdk.EventMask.ENTER_NOTIFY_MASK     |
                        Gdk.EventMask.LEAVE_NOTIFY_MASK     |
                        Gdk.EventMask.POINTER_MOTION_MASK)

    def do_button_press_event(self, event):
        if event.button != 1:
            return Gdk.EVENT_PROPAGATE

        self.fraction = event.x / self.get_allocated_width()
        self.queue_draw()

        self.start_grab()

        return Gdk.EVENT_STOP

    def do_scroll_event(self, event):
        SEEK_SCROLL_STEP = 0.05
        if event.direction in (Gdk.ScrollDirection.UP, Gdk.ScrollDirection.RIGHT):
            self.fraction += SEEK_SCROLL_STEP
        else:
            self.fraction -= SEEK_SCROLL_STEP

        if self.fraction < 0:
            self.fraction == 0.0
        elif self.fraction > 1:
            self.fraction == 1.0

        self.queue_draw()
        self.emit('seeked', self.fraction)

    def do_enter_notify_event(self, *args):
        if self.animate_id:
            self.remove_tick_callback(self.animate_id)

        def on_complete():
            self.show_label = True

        self.animation_start_height = self.get_allocated_height()
        self.animate_id = self.add_tick_callback(self.animate, on_complete)
        self.start_frame_time = self.get_frame_clock().get_frame_time()
        self.animation_target_height = 16

    def do_leave_notify_event(self, *args):
        if self.animate_id:
            self.remove_tick_callback(self.animate_id)

        self.show_label = False

        self.animation_start_height = self.get_allocated_height()
        self.animate_id = self.add_tick_callback(self.animate)
        self.start_frame_time = self.get_frame_clock().get_frame_time()
        self.animation_target_height = 7

    def do_draw(self, cr):
        alloc = self.get_allocation()

        x = 0
        y = 0
        width = alloc.width
        height = alloc.height
        stop = x + width * self.fraction

        context = self.get_style_context()
        res, progress_color = context.lookup_color('selected_bg_color')
        res, trough_color = context.lookup_color('insensitive_bg_color')

        cr.set_source_rgb(progress_color.red, progress_color.green, progress_color.blue)
        cr.rectangle(x, y, stop, height)
        cr.fill()

        cr.set_source_rgb(trough_color.red, trough_color.green, trough_color.blue)
        cr.rectangle(stop, y, width - stop, height)
        cr.fill()

        if self.show_label:
            font = context.get_property('font', Gtk.StateFlags.NORMAL).copy()
            text_color = context.get_color(Gtk.StateFlags.NORMAL)

            cr.set_source_rgb(text_color.red, text_color.green, text_color.blue)

            layout = PangoCairo.create_layout(cr)
            layout.set_text(self.label, -1)
            layout.set_font_description(font)
            layout.set_alignment(Pango.Alignment.CENTER)

            w, h = layout.get_size()

            text_height = h / Pango.SCALE
            text_width = w / Pango.SCALE
            cr.move_to(int(x + (width - text_width) / 2), int(y + (height - text_height) / 2))

            PangoCairo.show_layout(cr, layout)

    def on_button_release(self, w, event):
        if event.button != 1:
            return Gdk.EVENT_PROPAGATE

        self.grabbed = False

        self.emit('seeked', self.fraction)

        self.end_grab()

    def on_motion_notify(self, w, event):
        print('motion')
        self.fraction = event.x / self.get_allocated_width()

        self.queue_draw()

    def start_grab(self):
        success = Gdk.Display.get_default().get_default_seat().grab(self.get_window(), Gdk.SeatCapabilities.ALL, True, None, None, None, None)
        if success != Gdk.GrabStatus.SUCCESS:
            return

        self.grabbed = True

        self.button_release_id = self.connect('button-release-event', self.on_button_release)
        self.motion_notify_id = self.connect('motion-notify-event', self.on_motion_notify)

    def end_grab(self):
        self.grabbed = False

        Gdk.Display.get_default().get_default_seat().ungrab()

        self.disconnect(self.button_release_id)
        self.disconnect(self.motion_notify_id)
        self.button_release_id = 0
        self.motion_notify_id = 0

    def animate(self, w, clock, on_complete=None):
        distance = self.animation_target_height - self.animation_start_height
        progress = (clock.get_frame_time() - self.start_frame_time) / ANIMATION_LENGTH

        if progress < 1:
            current_height = int(self.animation_start_height + distance * progress)
        else:
            current_height = self.animation_target_height

        self.props.height_request = current_height

        if current_height == self.animation_target_height:
            self.animate_id = 0

            if on_complete:
                on_complete()

            return GLib.SOURCE_REMOVE

        return GLib.SOURCE_CONTINUE

    def set_fraction(self, fraction):
        # todo: durring drag, don't set the fraction directly, just cache the value and set when done if the drag is interrupted
        self.fraction = fraction
        self.queue_draw()

class PlayerControls(Gtk.Box):
    time_update_id = 0
    signals = []

    def __init__(self, bus_name):
        super(PlayerControls, self).__init__(orientation=Gtk.Orientation.VERTICAL)
        self.bus_name = bus_name

        self.server_proxy = None
        self.player_proxy = None
        self.props_proxy = None
        self.art_url = None
        self.status = 'Stopped'
        self.can_raise = False
        self.can_seek = False
        self.track_length = 0
        self.track_id = ''

        Gio.DBusProxy.new_for_bus(Gio.BusType.SESSION, Gio.DBusProxyFlags.NONE, None, bus_name, MPRIS_PATH, MPRIS_IFACE_NAME, None, self.on_server_proxy_ready)
        Gio.DBusProxy.new_for_bus(Gio.BusType.SESSION, Gio.DBusProxyFlags.GET_INVALIDATED_PROPERTIES, None, bus_name, MPRIS_PATH, MPRIS_PLAYER_IFACE_NAME, None, self.on_player_proxy_ready)
        Gio.DBusProxy.new_for_bus(Gio.BusType.SESSION, Gio.DBusProxyFlags.NONE, None, bus_name, MPRIS_PATH, DBUS_PROPERTIES_IFACE_NAME, None, self.on_props_proxy_ready)

        self.top_box = Gtk.Box(margin=10)
        self.pack_start(self.top_box, False, False, 0)

        self.player_title = Gtk.Label(label='loading')
        self.top_box.pack_start(self.player_title, False, False, 0)

        self.overlay = Gtk.Overlay()
        self.pack_start(self.overlay, False, False, 0)

        self.album_art = Gtk.Image(icon_name='media-optical', pixel_size=300)
        self.overlay.add(self.album_art)

        overlay_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.END, hexpand=True, halign=Gtk.Align.FILL, name='sound-overlay')
        self.overlay.add_overlay(overlay_box)

        # Artist
        artist_box = Gtk.Box(margin_start=15, margin_top=10, spacing=5)
        overlay_box.pack_start(artist_box, False, False, 5)
        artist_icon = Gtk.Image.new_from_icon_name('system-users-symbolic', Gtk.IconSize.MENU)
        artist_box.pack_start(artist_icon, False, False, 0)
        self.artist_label = Gtk.Label(label='Unknown Artist', ellipsize=Pango.EllipsizeMode.END)
        artist_box.pack_start(self.artist_label, False, False, 0)

        # Title
        title_box = Gtk.Box(margin_start=15, spacing=5)
        overlay_box.pack_start(title_box, False, False, 5)
        title_icon = Gtk.Image.new_from_icon_name('audio-x-generic-symbolic', Gtk.IconSize.MENU)
        title_box.pack_start(title_icon, False, False, 0)
        self.title_label = Gtk.Label(label='Unknown Title', ellipsize=Pango.EllipsizeMode.END)
        title_box.pack_start(self.title_label, False, False, 0)

        # controls
        self.control_box = Gtk.Box(halign=Gtk.Align.CENTER, margin_bottom=10, spacing=5)
        overlay_box.pack_start(self.control_box, False, False, 0)

        def make_button(icon):
            image = Gtk.Image(icon_name=icon, icon_size=Gtk.IconSize.BUTTON)
            button = Gtk.Button(image=image, halign=Gtk.Align.CENTER, relief=Gtk.ReliefStyle.NONE, name='sound-control-button')
            self.control_box.pack_start(button, True, True, 0)

            return button

        self.backward_button = make_button('media-skip-backward-symbolic')
        self.backward_button.connect('clicked', lambda *a: self.player_proxy.Previous())
        self.play_button = make_button('media-playback-start-symbolic')
        self.play_button.connect('clicked', lambda *a: self.player_proxy.PlayPause())
        self.stop_button = make_button('media-playback-stop-symbolic')
        self.stop_button.connect('clicked', lambda *a: self.player_proxy.Stop())
        self.forward_button = make_button('media-skip-forward-symbolic')
        self.forward_button.connect('clicked', lambda *a: self.player_proxy.Next())

        self.progress_bar = Seeker(visible=False, no_show_all=True)
        overlay_box.pack_start(self.progress_bar, False, False, 0)
        self.progress_bar.connect('seeked', self.on_progress_seeked)

        self.show_all()

    def do_destroy(self):
        if self.time_update_id:
            GLib.source_remove(self.time_update_id)
            self.time_update_id = 0

        for (obj, signal_id) in self.signals:
            obj.disconnect(signal_id)

        self.signals.clear()

        Gtk.Box.do_destroy(self)

    def on_server_proxy_ready(self, o, res):
        self.server_proxy = Gio.DBusProxy.new_for_bus_finish(res)

        self.set_name()

        if self.server_proxy.get_cached_property('CanQuit'):
            self.add_quit_button()

        if self.server_proxy.get_cached_property('CanRaise'):
            self.add_raise_button()

        def on_props_changed(p, props, i):
            if 'Identity' in props.keys():
                self.set_name()

            if 'CanQuit' in props.keys():
                self.add_quit_button()

            if 'CanRaise' in props.keys():
                self.add_raise_button()


        signal_id = self.server_proxy.connect('g-properties-changed', on_props_changed)
        self.signals.append((self.server_proxy, signal_id))

    def on_player_proxy_ready(self, o, res):
        self.player_proxy = Gio.DBusProxy.new_for_bus_finish(res)
        if self.player_proxy.get_cached_property('CanSeek'):
            self.can_seek = self.player_proxy.get_cached_property('CanSeek').unpack()

        if self.player_proxy.get_cached_property('Metadata'):
            self.process_metadata()

        if self.player_proxy.get_cached_property('PlaybackStatus'):
            self.set_status()

        signal_id = self.player_proxy.connect('g-signal', self.on_player_signal)
        self.signals.append((self.player_proxy, signal_id))

        def on_props_changed(p, props, i):
            # print('props', props)
            # print(i)
            if 'Metadata' in props.keys():
                self.process_metadata()

            if 'PlaybackStatus' in props.keys():
                self.set_status()

            if 'Position' in props.keys():
                # print('Position changed')
                self.update_time()

            if 'CanQuit' in props.keys() and props['CanQuit'].unpack():
                self.add_quit_button()

            if 'CanRaise' in props.keys() and props['CanRaise'].unpack():
                self.add_raise_button()

            if 'CanSeek' in props.keys():
                self.can_seek = props['CanSeek']
                if self.can_seek:
                    self.progress_bar.show()
                else:
                    self.progress_bar.hide()

                self.set_status()

        signal_id = self.player_proxy.connect('g-properties-changed', on_props_changed)
        self.signals.append((self.player_proxy, signal_id))

    def on_props_proxy_ready(self, o, res):
        self.props_proxy = Gio.DBusProxy.new_for_bus_finish(res)

    def on_progress_seeked(self, w, fraction):
        self.player_proxy.SetPosition('(ox)', self.track_id, int(fraction * self.track_length))

    def set_name(self):
        self.name = None
        if self.server_proxy:
            try:
                self.name = self.server_proxy.get_cached_property('Identity').unpack()
            except Exception as e:
                pass

        # Fall back to the end of the bus name. It may be a bit wonky, but at least it gives the user some idea which player it is.
        if not self.name or self.name == '':
            self.name = ' '.join(self.bus_name.split('.')[3:])

        title = self.name
        if self.status:
            title += ' - ' + self.status

        self.player_title.set_label(title)

    def process_metadata(self):
        metadata = self.player_proxy.get_cached_property('Metadata').unpack()
        # print(metadata)
        if 'xesam:artist' in metadata:
            self.artist_label.set_label(', '.join(metadata['xesam:artist']))
        else:
            self.artist_label.set_label('Unknown Artist')

        if 'xesam:title' in metadata:
            self.title_label.set_label(metadata['xesam:title'])
        else:
            self.title_label.set_label('Unknown Title')

        if 'mpris:artUrl' in metadata:
            art_url = metadata['mpris:artUrl']

            if art_url != self.art_url:
                self.art_url = art_url

                if art_url.startswith('file://'):
                    art_file = art_url[7:]

                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(art_file, 300, 300)
                self.album_art.set_from_pixbuf(pixbuf)

        else:
            self.album_art.props.icon_name = 'media-optical'
            
        if 'mpris:length' in metadata:
            self.track_length = metadata['mpris:length']

        if 'mpris:trackid' in metadata:
            self.track_id = metadata['mpris:trackid']

        if self.can_seek and self.track_length:
            self.update_time()

    def set_status(self):
        self.status = self.player_proxy.get_cached_property('PlaybackStatus').unpack()

        if self.status == 'Playing':
            self.play_button.get_image().props.icon_name = 'media-playback-pause-symbolic'
        else:
            self.play_button.get_image().props.icon_name = 'media-playback-start-symbolic'

        if not self.can_seek or self.status == 'Stopped' or self.track_length == 0:
            # print('hiding')
            self.progress_bar.hide()
        else:
            # print('showing')
            self.progress_bar.show()
            self.update_time()

            if self.status == 'Playing':
                # print('adding timeout')
                self.time_update_id = GLib.timeout_add_seconds(1, self.update_time)

        self.set_name()

    def update_time(self):
        # print('updating', self.status)
        if self.status != 'Playing':
            return False

        args = GLib.Variant('(ss)', (MPRIS_PLAYER_IFACE_NAME, 'Position'))
        result = self.props_proxy.call_sync("Get", args, 0, -1, None).unpack()[0]
        # print('result', result)
        progress = result / self.track_length
        # progress = self.player_proxy.get_cached_property('Position').unpack() / self.track_length
        # print('fraction', progress)



        self.progress_bar.set_fraction(progress)
        self.progress_bar.label = f'{seconds_to_time_string(result / 1000000)} / {seconds_to_time_string(self.track_length/ 1000000)}'

        return True

    def add_raise_button(self):
        self.can_raise = True
        raise_button = Gtk.Button(image=Gtk.Image(icon_name='go-up-symbolic', icon_size=Gtk.IconSize.BUTTON), relief=Gtk.ReliefStyle.NONE)
        self.top_box.pack_end(raise_button, False, False, 0)
        raise_button.connect('clicked', self.raise_window)
        raise_button.show_all()

    def raise_window(self, *args):
        # if self.name.lower() == 'spotify':
        #     # launch spotify from command line since it can't always raise itself
        # else:
        self.server_proxy.Raise()

    def add_quit_button(self):
        quit_button = Gtk.Button(image=Gtk.Image(icon_name='window-close-symbolic', icon_size=Gtk.IconSize.BUTTON), relief=Gtk.ReliefStyle.NONE)
        self.top_box.pack_end(quit_button, False, False, 0)
        if self.can_raise:
            self.top_box.reorder_child(quit_button, -1)
        quit_button.connect('clicked', lambda *a: self.server_proxy.Quit())
        quit_button.show_all()

    def on_player_signal(self, p, sender, signal, params):
        if signal != 'Seeked':
            return

class PlayerLauncher(XApp.MenuItem):
    def __init__(self, app):
        super(PlayerLauncher, self).__init__(label=app.get_name())
        self.app = app

        self.set_gicon(app.get_icon())

        self.connect('activate', self.launch)

        self.show_all()

    def launch(self, *args):
        self.app.launch(None, None)

class PreferencesWindow(XApp.PreferencesWindow):
    def __init__(self):
        super(PreferencesWindow, self).__init__(skip_taskbar_hint=False, title=_("Preferences"))

        content = self.get_content_area()

        # menu
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add_page(page, 'menu', _("Menu"))

        page.pack_start(GSettingsSwitch(_("Control players"), SCHEMA, 'control-players'), False, False, 0)
        page.pack_start(GSettingsSwitch(_("Show loop and shuffle controls"), SCHEMA, 'show-loop-shuffle', dep_key=f'{SCHEMA}/control-players'), False, False, 0)
        page.pack_start(GSettingsSwitch(_("Show menu"), SCHEMA, 'show-menu'), False, False, 0)

        # panel
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add_page(page, 'panel', _("Panel"))

        page.pack_start(GSettingsSwitch(_("Show song information on the panel"), SCHEMA, 'show-track', dep_key=f'{SCHEMA}/control-players'), False, False, 0)
        page.pack_start(GSettingsSpinButton(_("Limit song information to"), SCHEMA, 'truncate-text', default=30, min=5, max=512, step=1, units=_("characters"), dep_key=f'{SCHEMA}/show-track'), False, False, 0)
        options = [
            ('mute', _("Toggle Mute")),
            ('out_mute', _("Toggle Mute output")),
            ('in_mute', _("Toggle Mute input")),
            ('player', _("Toggle Play / Pause"))
        ]
        page.pack_start(GSettingsComboBox(_("Action on middle click"), SCHEMA, 'middle-click-action', options=options), False, False, 0)
        page.pack_start(GSettingsSwitch(_("Use horizontal scrolling to move between tracks"), SCHEMA, 'horizontal-scroll', dep_key=f'{SCHEMA}/control-players'), False, False, 0)
        page.pack_start(GSettingsSwitch(_("Show album art as icon"), SCHEMA, 'show-album-icon', dep_key=f'{SCHEMA}/control-players'), False, False, 0)
        page.pack_start(GSettingsSwitch(_("Hide system tray icons for compatible players"), SCHEMA, 'hide-systray'), False, False, 0)

        # tooltip
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add_page(page, 'tooltip', _("Tooltip"))

        page.pack_start(GSettingsSwitch(_("Show volume in tooltip"), SCHEMA, 'tooltip-show-volume'), False, False, 0)
        page.pack_start(GSettingsSwitch(_("Show player in tooltip"), SCHEMA, 'tooltip-show-player'), False, False, 0)
        page.pack_start(GSettingsSwitch(_("Show song artist and title in tooltip"), SCHEMA, 'tooltip-show-artist-title'), False, False, 0)

class SoundMenu(XApp.Menu):
    def __init__(self, controller, cd_sound_settings, app):
        super(SoundMenu, self).__init__()
        self.controller = controller
        self.cd_sound_settings = cd_sound_settings
        self.app = app

        self.players = {}

        self.cd_sound_settings.connect('changed::maximum-volume', self.update_max_volume)

        self.norm_volume = self.controller.get_vol_max_norm()
        self.max_volume = self.cd_sound_settings.get_int('maximum-volume') * self.norm_volume / 100
        
        self.launch_item = XApp.MenuItem(label=_("Launch player"))
        self.append(self.launch_item)

        self.launcher_section = XApp.MenuSection()
        self.append(self.launcher_section)
        self.launch_item.props.submenu = self.launcher_section

        self.player_stack = Gtk.Stack()
        self.append(self.player_stack)

        self.append(XApp.MenuSeparator())

        self.output_volume_slider = VolumeSliderMenuItem(stream=self.controller.get_default_sink(), norm_volume=self.norm_volume, max_volume=self.max_volume)
        self.append(self.output_volume_slider)

        self.append(XApp.MenuSeparator())

        settings_menu_item = XApp.MenuItem(label=_("Sound Settings"))
        settings_menu_item.set_icon_name ('cs-sound')
        self.append(settings_menu_item)
        settings_menu_item.connect('activate', self.launch_settings)

        self.show_all()
        
        self.tree = CMenu.Tree.new('cinnamon-applications.menu', CMenu.TreeFlags.SHOW_EMPTY)
        self.tree.load_sync()
        self.load_player_launchers()
        
        Gio.DBusProxy.new_for_bus(Gio.BusType.SESSION, Gio.DBusProxyFlags.NONE, None, DBUS_IFACE_NAME, DBUS_PATH, DBUS_IFACE_NAME, None, self.on_proxy_ready)

    def on_proxy_ready(self, o, res):
        self.proxy = Gio.DBusProxy.new_for_bus_finish(res)
        self.proxy.connect('g-signal', self.on_dbus_signal)

        # print(self.proxy.ListNames())

        for name in self.proxy.ListNames():
            # print(name, MPRIS_NAME_REGEX.match(name))
            if MPRIS_NAME_REGEX.match(name):
                self.add_player(name)
                # print('match!', name)

    def on_dbus_signal(self, proxy, sender_name, signal_name, params):
        if signal_name != 'NameOwnerChanged':
            return

        name, old_owner, new_owner = params.unpack()
        if MPRIS_NAME_REGEX.match(name):
            # print(old_owner, '-', new_owner)
            if not old_owner and new_owner:
                self.add_player(name)
            elif old_owner and not new_owner:
                self.remove_player(name)
            # else:
            #     self.change_player_owner(name, old_owner, new_owner)

    def add_player(self, name):
        if name in self.players:
            return

        if len(self.players) == 0:
            self.app.update_active_player(True)

        player = PlayerControls(name)
        self.players[name] = player
        self.player_stack.add_named(player, name)
        player.show_all()

    def remove_player(self, name):
        if name in self.players:
            self.players[name].destroy()
            del self.players[name]

            if len(self.players) == 0:
                self.app.update_active_player(False)

            # print(self.player_stack.get_children())

            self.queue_resize()

    # def change_player_owner(self, name, old_owner, new_owner):
    #     if name in self.players:
    #         self.players[name].bus_name = new_owner
    #     else:
    #         self.add_player(name)

    def set_output_stream(self, stream):
        self.output_volume_slider.set_stream(stream)
        
    def load_player_launchers(self):
        root_dir = self.tree.get_root_directory()
        
        tree_iter = root_dir.iter()
        while True:
            item_type = tree_iter.next()
            if item_type == CMenu.TreeItemType.INVALID:
                return

            elif item_type != CMenu.TreeItemType.DIRECTORY:
                continue

            directory = tree_iter.get_directory()
            if directory.get_menu_id() == 'Multimedia':
                dir_iter = directory.iter()
                while True:
                    item_type = dir_iter.next()

                    if item_type == CMenu.TreeItemType.INVALID:
                        return

                    if item_type != CMenu.TreeItemType.ENTRY:
                        continue

                    app = dir_iter.get_entry().get_app_info()
                    categories = app.get_categories()[:-1].split(';')
                    if 'Player' in categories:
                        self.launcher_section.append(PlayerLauncher(app))
                        # print(app.get_name())
                    # print('   ', categories)


    def update_max_volume(self, *args):
        self.max_volume = self.cd_sound_settings.get_int('maximum-volume') * self.norm_volume / 100

        self.output_volume_slider.set_max_volume(self.max_volume)

    def launch_settings(self, *args):
        # print('launching')
        subprocess.Popen(['cinnamon-settings', 'sound'])

class Sound(Gtk.Application):
    def __init__(self):
        super(Sound, self).__init__(application_id=APPLICATION_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)

        self.has_activated = False

    def do_activate(self):
        if self.has_activated:
            self.window.restore()

            return

        Gtk.Application.do_activate(self)

        self.primary_menu = None
        self.active_player = False

        self.cd_sound_settings = Gio.Settings(schema_id=CINNAMON_DESKTOP_SOUND_SCHEMA)

        self.status_icon = XApp.StatusIcon(name='sound')
        self.status_icon.set_icon_name('audio-x-generic-symbolic')

        self.mixer_init()

        self.primary_menu = SoundMenu(self.controller, self.cd_sound_settings, self)
        # self.status_icon.set_primary_menu(self.primary_menu)

        self.context_menu = Gtk.Menu()

        self.context_menu.append(Gtk.SeparatorMenuItem())

        item = Gtk.MenuItem(label='Quit', visible=True)
        item.connect('activate', self.exit)
        self.context_menu.append(item)

        self.status_icon.set_secondary_menu(self.context_menu)
        self.status_icon.connect('scroll-event', self.on_status_icon_scroll)
        self.status_icon.connect('button-press-event', self.on_button_press)
        self.status_icon.connect('button-release-event', self.on_button_release)

        self.has_activated = True

        provider = Gtk.CssProvider()
        provider.load_from_path(STYLE_SHEET_PATH)

        Gtk.StyleContext.add_provider_for_screen (Gdk.Screen.get_default(), provider, 600)

        # self.update_default_sink()

        self.hold()

    def on_status_icon_scroll(self, i, amount, direction, time):
        if amount == 0:
            return

        volume = self.output_stream.props.volume

        max_volume = self.cd_sound_settings.get_int('maximum-volume') / 100 * self.norm_volume

        if direction == XApp.ScrollDirection.UP:
            volume += SCROLL_STEP / 100 * self.norm_volume
        elif direction == XApp.ScrollDirection.DOWN:
            volume -= SCROLL_STEP / 100 * self.norm_volume

        if volume < 0:
            volume = 0
        elif volume > max_volume:
            volume = max_volume

        self.output_stream.set_volume(volume)
        self.output_stream.push_volume()

    def on_button_press(self, i, x, y, button, t, pos):
        if button == 2:
            muted = self.output_stream.get_is_muted()
            self.output_stream.change_is_muted(not muted)

    def on_button_release(self, i, x, y, button, t, pos):
        if button == 1:
            rect = Gdk.Rectangle()
            rect.x = x
            rect.y = y
            rect.height = 0
            rect.width = 0

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
            self.primary_menu.popup_at_rect(rect, i_gravity, m_gravity, None)

    def mixer_init(self):
        self.controller = Cvc.MixerControl(name='cinnamon')
        self.controller.open()

        self.controller.connect('state-changed', self.set_channel_map)
        self.controller.connect('output-added', self.device_added, 'output')
        self.controller.connect('input-added', self.device_added, 'input')
        self.controller.connect('output-removed', self.device_removed, 'output')
        self.controller.connect('input-removed', self.device_removed, 'input')
        self.controller.connect('active-output-update', self.active_output_update)
        self.controller.connect('active-input-update', self.active_input_update)
        self.controller.connect('default-sink-changed', self.update_default_sink)
        self.controller.connect('default-source-changed', self.default_source_changed)
        self.controller.connect('stream-added', self.stream_added)
        self.controller.connect('stream-removed', self.stream_removed)

        self.norm_volume = self.controller.get_vol_max_norm()

    def update_volume(self, *args):
        if self.output_stream.get_is_muted():
            volume = 0
        else:
            volume = int(round(self.output_stream.props.volume / self.norm_volume * 100))

        if not self.active_player:
            self.status_icon.set_icon_name(get_volume_icon(volume))

        self.status_icon.set_tooltip_text('Volume: %d%%' % volume)

    def set_channel_map(self, *args):
        pass

    def device_added(self, *args):
        pass

    def device_removed(self, *args):
        pass

    def active_output_update(self, *args):
        pass

    def active_input_update(self, *args):
        pass

    def update_default_sink(self, *args):
        # print('default sink changed')
        self.output_stream = self.controller.get_default_sink()

        if self.primary_menu:
            self.primary_menu.set_output_stream(self.output_stream)

        self.mutedHandlerId = self.output_stream.connect("notify::is-muted", self.update_volume)
        self.volumeHandlerId = self.output_stream.connect("notify::volume", self.update_volume)
        self.update_volume()

    def default_source_changed(self, *args):
        pass

    def stream_added(self, *args):
        pass

    def stream_removed(self, *args):
        pass

    def update_active_player(self, active_player):
        self.active_player = active_player
        if active_player:
            self.status_icon.set_icon_name('audio-x-generic-symbolic')
        else:
            self.update_volume()

    def exit(self, *args):
        self.quit()

if __name__ == '__main__':
    setproctitle('sound')
    app = Sound()
    app.run()

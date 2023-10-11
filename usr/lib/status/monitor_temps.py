#!/usr/bin/python3

import cairo
import math
import subprocess
import sys

from random import random
from setproctitle import setproctitle

import gi
gi.require_version('cairo', '1.0')
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('PangoCairo', '1.0')
gi.require_version('XApp', '1.0')

from gi.repository import cairo, Gdk, Gio, GLib, Gtk, Pango, PangoCairo, XApp

from matplotlib.backends.backend_gtk3agg import FigureCanvasGTK3Agg as Canvas
from matplotlib.figure import Figure
import numpy as np

APPLICATION_ID = 'org.x.temps'
REFRESH_INTERVAL = 2

STYLE_SHEET_PATH = '/usr/share/status/monitor_temps.css'

CSS_DATA = b"""
levelbar block.filled {
    background-color: red;
    border-style: solid;
    border-color: black;
}

levelbar block.crit {
    background-color: yellow;
    border-style: solid;
    border-color: black;
}

levelbar block.warn {
    background-color: green;
    border-style: solid;
    border-color: black;
}
"""

COLOR_MAP = {
    'cpu_max': [1, 0, 0],
    'cpu_ave': [0, 1, 0],
    'gpu': [0, 0, 1]
}

class GenericItem(Gtk.Box):
    def __init__(self, orientation=Gtk.Orientation.VERTICAL, **kwargs):
        super(GenericItem, self).__init__(orientation=orientation, margin=10, spacing=10, hexpand=True, name='mt_item')
        self.kwargs = kwargs
        

class Meter(GenericItem):
    def __init__(self, title='', points=[20, 100], unit='°C'):
        super(Meter, self).__init__(height_request=250)
        self.points = points
        self.unit = unit

        # self.style_manager = XApp.StyleManager(widget=self)
        # self.style_manager.set_style_property('border', 'white solid 1px')
        # self.style_manager.set_style_property('padding', '10px')

        self.current_value_label = Gtk.Label()
        self.pack_start(self.current_value_label, False, False, 0)

        graph_box = Gtk.Box(halign=Gtk.Align.CENTER)
        self.pack_start(graph_box, True, True, 0)

        self.level_bar = Gtk.LevelBar(min_value=points[0], max_value=points[-1], inverted=True, orientation=Gtk.Orientation.VERTICAL, width_request=15, height_request=200, halign=Gtk.Align.CENTER, margin_bottom=4, margin_top=4)
        graph_box.pack_start(self.level_bar, False, False, 0)

        self.drawing_area = Gtk.DrawingArea(width_request=50)
        graph_box.pack_start(self.drawing_area, False, False, 0)

        self.pack_start(Gtk.Label(label=title), False, False, 0)

        if len(points) > 2:
            self.level_bar.add_offset_value('warn', points[1])
        if len(points) > 3:
            self.level_bar.add_offset_value('crit', points[2])

        self.drawing_area.connect('draw', self.draw_scale)

        self.show_all()

    def draw_scale(self, widget, cr):
        height = widget.get_allocated_height()
        inner_height = height - 16
        width = widget.get_allocated_width()

        cr.set_source_rgb(1,1,1)
        cr.set_line_width(1)

        val_min = self.points[0]
        val_max = self.points[-1]
        val_range = val_max - val_min

        for tick in self.points:
            scaled_tick = height - ((tick - val_min) / val_range * inner_height + 8)
            cr.move_to(2, scaled_tick)
            cr.line_to(12, scaled_tick)
            cr.stroke()

            layout = PangoCairo.create_layout(cr)
            layout.set_font_description(Pango.FontDescription.from_string('arial 10'))
            layout.set_text(str(tick))
            cr.move_to(17, int(scaled_tick - layout.get_pixel_size()[1] / 2))
            PangoCairo.show_layout(cr, layout)

    def set_value(self, value):
        self.level_bar.set_value(value)
        self.current_value_label.set_label(f'{value:.0f}{self.unit}')

class Level(GenericItem):
    def __init__(self, title='', unit='', max_value=100):
        super(Level, self).__init__(orientation=Gtk.Orientation.VERTICAL)
        self.title = title
        self.unit = unit
        self.max_value = max_value

        self.pack_start(Gtk.Label(label=title), False, False, 0)

        value_box = Gtk.Box()
        self.pack_start(value_box, False, False, 0)

        self.value_widget = Gtk.Label(name='digital-display-value')
        value_box.pack_start(self.value_widget, False, False, 0)

        value_box.pack_start(Gtk.Label(label=unit, name='digital-display-units'), False, False, 0)

        self.level_bar = Gtk.LevelBar(min_value=0, max_value=1, height_request=15)
        self.pack_end(self.level_bar, False, False, 0)

        self.show_all()

    def set_value(self, value, max_value=0):
        if max_value != 0:
            self.max_value = max_value

        self.value_widget.set_label(f'{value} / {self.max_value} {self.unit}')
        self.level_bar.set_value(value/self.max_value)

class SpeedMeter(GenericItem):
    def __init__(self, title='', unit='', max_value=1):
        super(SpeedMeter, self).__init__()
        self.unit = unit
        self.max_value = max_value
        self.value = 0
        
        self.pack_start(Gtk.Label(label=title), False, False, 0)
        
        self.drawing_area = Gtk.DrawingArea(width_request=150, height_request=150)
        self.pack_start(self.drawing_area, False, False, 0)
        self.drawing_area.connect('draw', self.draw_meter)
        
        self.show_all()
        
    def draw_meter(self, widget, cr):
        height = widget.get_allocated_height()
        width = widget.get_allocated_width()
        percent = self.value / self.max_value
        radius = min(height, width * 0.9) * 0.45
        center_x = width / 2
        center_y = height * .55
        angle1 = math.pi * .75
        angle2 = math.pi * (1.5 * percent + .75)
        angle3 = math.pi * .25
        end_cap = 1 / radius
        # print(end_cap)

        # print(height, width, radius, center_x, center_y, angle1, angle3)
        # cr.set_line_cap(cairo.LineCap.ROUND)

        # outer frame
        cr.set_line_width(16)
        cr.set_source_rgb(.16, .16, .16)
        cr.arc(center_x, center_y, radius, angle1-(end_cap*3), angle3+(end_cap*3))
        cr.stroke()

        # trough
        cr.set_line_width(10)
        cr.set_source_rgba(.25,.25,.25, 1)
        cr.arc(center_x, center_y, radius, angle1, angle3)
        cr.stroke()

        # level frame
        # cr.set_line_width(10)
        cr.set_source_rgba(0, 0, 0, 1)
        cr.arc(center_x, center_y, radius, angle1-end_cap, angle2+end_cap)
        cr.stroke()

        # level bar
        cr.set_line_width(8)
        cr.set_source_rgb(1, 0, 0)
        cr.arc(center_x, center_y, radius, angle1, angle2)
        cr.stroke()

        cr.set_source_rgb(1, 1, 1)
        layout = PangoCairo.create_layout(cr)
        layout.set_font_description(Pango.FontDescription.from_string('arial 14'))
        layout.set_text(str(int(self.value)))
        value_text_width, value_text_height = layout.get_size()
        value_text_x = (width - value_text_width / Pango.SCALE) / 2
        value_text_y = (height / 2) - (value_text_height / Pango.SCALE)

        # print(value_text_width, height)
        cr.move_to(value_text_x, value_text_y)
        PangoCairo.show_layout(cr, layout)

        layout = PangoCairo.create_layout(cr)
        layout.set_font_description(Pango.FontDescription.from_string('arial 10'))
        layout.set_text(str(self.unit))
        unit_text_width, unit_text_height = layout.get_size()
        unit_text_x = (width - unit_text_width / Pango.SCALE) / 2
        unit_text_y = height / 2

        # print(unit_text_width, height)
        cr.move_to(unit_text_x, unit_text_y)
        PangoCairo.show_layout(cr, layout)

    def set_value(self, value):
        self.value = value
        self.drawing_area.queue_draw()

class DigitalDisplay(Gtk.Box):
    def __init__(self, title='', unit=''):
        super(DigitalDisplay, self).__init__(orientation=Gtk.Orientation.VERTICAL)
        self.unit = unit

        self.pack_start(Gtk.Label(label=title), False, False, 0)

        value_box = Gtk.Box()
        self.pack_start(value_box, False, False, 0)

        self.current_value_label = Gtk.Label(name='digital-display-value')
        value_box.pack_start(self.current_value_label, False, False, 0)

        value_box.pack_start(Gtk.Label(label=unit, valign=Gtk.Align.END, name='digital-display-units'), False, False, 0)

        self.show_all()

    def set_value(self, value):
        self.current_value_label.set_label(f'{value:.0f}')

class GraphWindow(Gtk.Window):
    def __init__(self, data=None):
        super(GraphWindow, self).__init__(default_height=500, default_width=500)
        self.data = data

        # self.drawing_area = Gtk.DrawingArea()
        # self.add(self.drawing_area)
        # self.drawing_area.connect('draw', self.on_draw)
        self.figure = Figure()
        self.axis = self.figure.add_subplot(111)

        self.canvas = Canvas(self.figure)
        self.add(self.canvas)

        if data:
            self.update_data(data)

        self.connect('delete-event', self.on_window_close)

        self.show_all()

    # def on_draw(self, widget, cr):
    #     left_margin = 30
    #     bottom_margin = 30
    #     top_margin = 10
    #     right_margin = 10
    #     temp_range = 100.0 - 20.0

    #     height = widget.get_allocated_height()
    #     width = widget.get_allocated_width()
    #     inner_height = height - top_margin - bottom_margin
    #     inner_width = width - right_margin - left_margin

    #     cr.set_source_rgb(0, 0, 0)
    #     cr.rectangle(0, 0, width, height)
    #     cr.stroke()

    #     cr.set_source_rgb(1, 1, 1)
    #     cr.set_line_width(1)

    #     cr.move_to(left_margin, top_margin)
    #     cr.line_to(left_margin, height - bottom_margin)

    #     cr.line_to(width - right_margin, height - bottom_margin)
    #     cr.stroke()
        
    #     for temp_id, values in self.data.items():
    #         color = COLOR_MAP[temp_id]
    #         cr.set_source_rgb(color[0], color[1], color[2])
    #         if len (values) > inner_width:
    #             start = len(values) - inner_width
    #             n = inner_width
    #         else:
    #             start = 0
    #             n = len(values)

    #         for i in range(n):
    #             temp = values[-(i+start)]
    #             x = width - right_margin - i
    #             y = height - bottom_margin - int(temp / temp_range * inner_height)
    #             cr.line_to(x, y)

    #         cr.stroke()
    #         cr.new_path()

    def update_data(self, data):
        self.data = data
        self.axis.clear()
        for temp_id, values in data.items():
            # print(f'temp_id: {temp_id}')
            time_array = np.arange(0, len(values), 1)
            # print(f'values: {values}')
            # print(f'time_array: {time_array}')
            data_array = np.asarray(values)
            # print(f'data_array: {data_array}')
            self.axis.plot(time_array, data_array, label=temp_id)

        self.axis.legend()
        # self.drawing_area.queue_draw()
        self.canvas.draw()

    def on_window_close(self, *args):
        self.hide()
        return Gdk.EVENT_STOP

class Monitor(Gtk.Application):
    def __init__(self):
        super(Monitor, self).__init__(application_id=APPLICATION_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        # super(Monitor, self).__init__(application_id=APPLICATION_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)

        self.has_activated = False

        self.graph = None

        self.data = {'cpu_max': [], 'cpu_ave': [], 'gpu': []}

    def do_activate(self):
        # try:
        print('activating')
        if self.has_activated:
            self.raise_window()

            return

        Gtk.Application.do_activate(self)
        Gtk.Settings.get_default().set_property("gtk-application-prefer-dark-theme", True)

        self.status_icon = XApp.StatusIcon(name='temps')
        self.status_icon.set_icon_name('temp-symbolic')

        self.menu = Gtk.Menu()

        self.menu.append(Gtk.SeparatorMenuItem())

        item = Gtk.MenuItem(label='Quit', visible=True)
        item.connect('activate', self.exit)
        self.menu.append(item)

        self.status_icon.set_secondary_menu(self.menu)
        self.status_icon.connect('button-press-event', self.on_button_press)

        self.builder = Gtk.Builder.new_from_file('/usr/share/status/monitor_temps.ui')
        self.window = self.builder.get_object('main_window')
        self.window.connect('delete-event', self.on_window_close)
        self.add_window(self.window)

        self.builder.get_object('graph').connect('clicked', self.open_graph)

        # add meters
        flow_box = self.builder.get_object('flow_box')

        self.cpu_ave = Meter(title='CPU (core ave)', points=[20, 86, 100, 112])
        flow_box.add(self.cpu_ave)

        self.cpu_max = Meter(title='CPU (pkg)', points=[20, 86, 100, 112])
        flow_box.add(self.cpu_max)

        self.gpu_temp = Meter(title='GPU', points=[20, 75, 100, 112])
        flow_box.add(self.gpu_temp)

        self.vram = Level(title='Video memory', unit='MiB')
        flow_box.add(self.vram)

        self.sysfan1 = SpeedMeter(title='Case Fan 1', unit='RPM', max_value=5000)
        flow_box.add(self.sysfan1)

        self.sysfan2 = SpeedMeter(title='Case Fan 2', unit='RPM', max_value=5000)
        flow_box.add(self.sysfan2)

        self.cpufan = SpeedMeter(title='CPU Fan', unit='RPM', max_value=5000)
        flow_box.add(self.cpufan)

        # self.test = SpeedMeter()
        # flow_box.add(self.test)

        GLib.timeout_add_seconds(REFRESH_INTERVAL, self.refresh)
        self.refresh()

        provider = Gtk.CssProvider()
        provider.load_from_data(CSS_DATA)

        Gtk.StyleContext.add_provider_for_screen (Gdk.Screen.get_default(), provider, 800)

        # self.raise_window()

        self.has_activated = True

        provider = Gtk.CssProvider()
        provider.load_from_path(STYLE_SHEET_PATH)

        Gtk.StyleContext.add_provider_for_screen (Gdk.Screen.get_default(), provider, 600)

        self.hold()

        # except Exception as e:
        #     print(e)
        #     self.quit()

    def do_command_line(self, cl):
        print(cl.get_arguments())
        print('hello world')
        return -1

    def open_graph(self, *args):
        if not self.graph:
            self.graph = GraphWindow(self.data)
        else:
            self.graph.show()

    def raise_window(self, *args):
        self.window.show()
        # self.window.stick()
        # self.window.set_keep_above(True)
        workarea = self.window.get_window().get_display().get_monitor(1).get_workarea()
        (w, h) = self.window.get_size()
        self.window.move(workarea.x + workarea.width - w, workarea.y + workarea.height - h)
        # self.window.present_with_time(Gtk.get_current_event_time())

    def on_button_press(self, i, x, y, button, t, p):
        if button == 1:
            if self.window.is_visible():
                self.window.hide()
            else:
                self.raise_window()

            return Gdk.EVENT_STOP

        return Gdk.EVENT_PROPAGATE

    def on_window_close(self, *args):
        self.window.hide()

        return Gdk.EVENT_STOP

    def refresh(self, *args):
        raw_info = subprocess.check_output('sensors', text=True)

        entries = raw_info.split('\n')

        core_temps = []
        for entry in entries:
            if entry[:13] == 'Package id 0:':
                cpu_max = float(entry[15:entry.find('°C')])
                self.cpu_max.set_value(cpu_max)
                self.data['cpu_max'].append(cpu_max)
            elif entry[:5] == 'Core ':
                core_temps.append(float(entry[16:entry.find('°C')]))
            elif entry[:3] == 'fan':
                if entry[3] == '2':
                    self.cpufan.set_value(float(entry[16:entry.find(' RPM')]))
                if entry[3] == '3':
                    self.sysfan1.set_value(float(entry[16:entry.find(' RPM')]))
                if entry[3] == '4':
                    self.sysfan2.set_value(float(entry[16:entry.find(' RPM')]))

        cpu_ave = sum(core_temps)/len(core_temps)
        self.cpu_ave.set_value(cpu_ave)
        self.data['cpu_ave'].append(cpu_ave)

        raw_info = subprocess.check_output('nvidia-smi', text=True)
        gpu_temp_line = raw_info.split('\n')[8]
        gpu_fan = int(gpu_temp_line[1:gpu_temp_line.find('%')])
        gpu_temp = float(gpu_temp_line[6:gpu_temp_line.find('C')])
        gpu_mem_use = int(gpu_temp_line[34:gpu_temp_line.find('MiB')])
        gpu_mem_max = int(gpu_temp_line[46:gpu_temp_line.find('MiB', 46)])

        self.gpu_temp.set_value(gpu_temp)
        self.data['gpu'].append(gpu_temp)
        self.vram.set_value(gpu_mem_use, gpu_mem_max)

        if self.graph:
            self.graph.update_data(self.data)

        return True

    def exit(self, *args):
        self.quit()

if __name__ == '__main__':
    setproctitle('monitor_temps')
    app = Monitor()
    # print(sys.argv)
    app.run(sys.argv)

#!/usr/bin/python3

import math

from gi.repository import Gdk, GLib, GObject, Gtk, XApp

def get_device_from_event(event):
    return Gdk.Display.get_default().get_default_seat()

class MenuBase(Gtk.Container):
    @GObject.Signal(flags=GObject.SignalFlags.RUN_LAST, return_type=bool,
                    arg_types=(Gtk.Widget,),
                    accumulator=GObject.signal_accumulator_true_handled)
    def child_activated(self, widget):
        pass

    def __init__(self, **kwargs):
        super(MenuBase, self).__init__(visible=True, **kwargs)

        self.children = []

        self.set_has_window(False)

    def do_forall(self, include_internals, callback, *callback_data):
        for item in self.children:
            callback(item, *callback_data)

    def do_add(self, widget):
        self.append(widget)

    def do_remove(self, widget):
        # print('removing widget')
        if widget not in self.children:
            return

        self.children.remove(widget)
        widget.unparent()

    def do_get_preferred_height(self):
        min_height = 0
        nat_height = 0
        for child in self.children:
            if not child.get_visible():
                # print('hidden - skipping')
                continue

            (child_min, child_nat) = child.get_preferred_height()
            min_height += child_min
            nat_height += child_nat

        min_height = max(min_height, 10)
        nat_height = max(nat_height, 10)

        return (min_height, nat_height)

    def do_get_preferred_width(self):
        min_width = 10
        nat_width = 10
        for child in self.children:
            if not child.props.visible:
                # print('hidden - skipping')
                continue

            (child_min, child_nat) = child.get_preferred_width()
            min_width = max(min_width, child_min)
            nat_width = max(nat_width, child_nat)

        return (min_width, nat_width)

    def do_size_allocate(self, allocation):
        Gtk.Container.do_size_allocate(self, allocation)

        curr_y = allocation.y
        for child in self.children:
            child_height = child.get_preferred_height()[1]
            child_alloc = Gdk.Rectangle()
            child_alloc.x = allocation.x
            child_alloc.y = curr_y
            child_alloc.height = child_height
            child_alloc.width = allocation.width
            curr_y += child_height
            child.size_allocate(child_alloc)

    def do_draw(self, cr):
        width = self.get_allocated_width()
        height = self.get_allocated_height()
        context = self.get_style_context()

        Gtk.render_background(context, cr, 0, 0, width, height)
        Gtk.render_frame(context, cr, 0, 0, width, height)

        Gtk.Container.do_draw(self, cr)

        return False

    def on_activate(self, *args):
        self.emit('child-activated', self)

    def menu_item_from_widget(self, widget):
        if isinstance(widget, MenuChild):
            return widget
        else:
            child = _MenuChildWrapper()
            child.add(widget)
            return child

    def _add_child_internal(self, child):
        child.set_parent(self)

        if isinstance(child, MenuItem):
            child.connect('activate', self.on_activate)

        if isinstance(child, MenuBase):
            child.connect('child-activated', self.on_activate)

    def append(self, widget):
        menu_item = self.menu_item_from_widget(widget)
        self.children.append(menu_item)
        self._add_child_internal(menu_item)

    def prepend(self, widget):
        menu_item = self.menu_item_from_widget(widget)
        self.children.prepend(menu_item)
        self._add_child_internal(menu_item)

    def insert(self, widget, pos):
        menu_item = self.menu_item_from_widget(widget)
        self.children.insert(menu_item, pos)
        self._add_child_internal(menu_item)

class Menu(MenuBase):
    def __init__(self, **kwargs):
        super(Menu, self).__init__(**kwargs)

        self.key_press_id = 0
        self.button_press_id = 0
        self.rect = None
        self.source_anchor = None
        self.menu_anchor = None

        self.window = Gtk.Window(type_hint=Gdk.WindowTypeHint.POPUP_MENU, type=Gtk.WindowType.POPUP, vexpand=False)
        self.window.connect('check-resize', self.on_resize)
        # self.window.get_style_context().add_class('xapp-menu-popup')
        # self.window.get_style_context().add_class('csd')
        # self.window.get_style_context().add_class('xapp-status-icon-menu-window')
        self.window.add(self)

        # provider = Gtk.CssProvider()
        # provider.load_from_path('/usr/share/status/menu.css')
        # Gtk.StyleContext.add_provider_for_screen (Gdk.Screen.get_default(), provider, 600)
        # self.window.get_style_context().add_class('xapp-menu')

        self.transfer_window = None

        # self.window.show()
        # self.window.hide()

    def on_key_press(self, w, event):
        if event.keyval == Gdk.KEY_Escape:
            self.popdown()

    def on_button_release(self, w, event):
        # print(Gtk.get_event_widget(event))
        allocation = self.window.get_allocation()
        if event.x < 0 or event.y < 0 or event.x > allocation.width or event.y > allocation.height:
            self.popdown()

    def on_resize(self, *args):
        # print('resizing')
        # print(self.get_preferred_height())
        # def get_child_height(child):
        #     # print(child, child.get_preferred_height())
        #     if isinstance(child, Gtk.Container):
        #         child.forall(get_child_height)

        # get_child_height(self)

        self.window.resize(1, 1)
        self.position_window()

    def on_activate(self, *args):
        MenuBase.on_activate(self, *args)

        self.popdown()

    def position_window(self):
        x = self.rect.x
        y = self.rect.y

        if self.source_anchor == Gdk.Gravity.EAST or self.source_anchor == Gdk.Gravity.NORTH_EAST or self.source_anchor == Gdk.Gravity.SOUTH_EAST:
            x += self.rect.width
        # elif self.source_anchor == Gdk.Gravity.EAST or self.source_anchor == Gdk.Gravity.NORTH_EAST or self.source_anchor == Gdk.Gravity.SOUTH_EAST:
        #     x += math.floor(self.rect.width)

        if self.source_anchor == Gdk.Gravity.SOUTH or self.source_anchor == Gdk.Gravity.SOUTH_WEST or self.source_anchor == Gdk.Gravity.SOUTH_EAST:
            y += self.rect.height

        # if menu_anchor == Gdk.Gravity.EAST or menu_anchor == Gdk.Gravity.NORTH_EAST or menu_anchor == Gdk.Gravity.SOUTH_EAST:
        #     x -= menu_width

        # if menu_anchor == Gdk.Gravity.SOUTH or menu_anchor == Gdk.Gravity.SOUTH_WEST or menu_anchor == Gdk.Gravity.SOUTH_EAST:
        #     y -= menu_height

        if not self.window.get_realized():
            # print('realizing')
            self.window.realize()
        nat_size = self.window.get_preferred_size()[1]
        # print(nat_size.height, nat_size.width)

        monitor_rect = Gdk.Display.get_default().get_monitor_at_point(x, y).get_workarea()

        if x + nat_size.width > monitor_rect.x + monitor_rect.width:
            x = monitor_rect.x + monitor_rect.width - nat_size.width

        if y + nat_size.height > monitor_rect.y + monitor_rect.height:
            y = monitor_rect.y + monitor_rect.height - nat_size.height

        # print('x', x, nat_size.width, monitor_rect.x, monitor_rect.width)

        self.window.set_gravity(self.menu_anchor)
        self.window.move(x, y)


        # gdk_window = self.window.get_window()
        # if not self.window.props.transient_for:
        #     attributes = Gdk.WindowAttr()
        #     attributes.window_type = Gdk.WindowType.CHILD;
        #     attributes.x = rect.x
        #     attributes.y = rect.y
        #     attributes.width = rect.width
        #     attributes.height = rect.height

        #     gdk_window.set_transient_for(Gdk.Window.new(None, attributes, Gdk.WindowAttributesType.X | Gdk.WindowAttributesType.Y))

        # gdk_window.move_to_rect(rect, source_anchor, menu_anchor, Gdk.AnchorHints.SLIDE | Gdk.AnchorHints.RESIZE, 0, 0)
        # print(x, y)
        # GLib.idle_add(self._popup)

    def _popup(self):
        # print('hello')
        # self.window.show()
        # print('world')
        # def show_window(seat, window, data):
        #     window.show()

        # print(self.window.get_window())

        if False:
            # print('grabbing window')
            success = Gdk.Display.get_default().get_default_seat().grab(self.window.get_window(), Gdk.SeatCapabilities.ALL, True, None, None, None, None)
            # print(success)

        # if success == Gdk.GrabStatus.ALREADY_GRABBED:
        else:
            # print('grabbing transfer window')
            if not self.transfer_window:
                # print('creating transfer window')
                attributes = Gdk.WindowAttr()
                attributes.x = -100
                attributes.y = -100
                attributes.width = 10
                attributes.height = 10
                attributes.window_type = Gdk.WindowType.TEMP
                attributes.wclass = Gdk.WindowWindowClass.INPUT_ONLY
                attributes.override_redirect = True
                attributes.event_mask = 0

                mask = Gdk.WindowAttributesType.X | Gdk.WindowAttributesType.Y | Gdk.WindowAttributesType.NOREDIR

                parent = self.window.get_screen().get_root_window()
                self.transfer_window = Gdk.Window.new(parent, attributes, mask)
                self.window.register_window(self.transfer_window)
                self.transfer_window.show()

            success = Gdk.Display.get_default().get_default_seat().grab(self.transfer_window, Gdk.SeatCapabilities.ALL, True, None, None, None, None)
            # print(success)

            # self.transfer_window.connect('key-press-event', self.on_key_press)
            # self.transfer_window.connect('button-press-event', self.on_button_press)
        if not self.key_press_id:
            self.key_press_id = self.window.connect('key-press-event', self.on_key_press)
        if not self.button_press_id:
            self.button_press_id = self.window.connect('button-release-event', self.on_button_release)

        self.window.show()

    def popdown(self):
        # print('ungrabbing')
        if self.key_press_id:
            self.window.disconnect(self.key_press_id)
            self.key_press_id = 0

        if self.button_press_id:
            self.window.disconnect(self.button_press_id)
            self.button_press_id = 0

        Gdk.Display.get_default().get_default_seat().ungrab()

        self.window.hide()

        self.rect = None
        self.source_anchor = None
        self.menu_anchor = None

    def popup_at_rect(self, rect, source_anchor, menu_anchor, event=None):
        self.rect = rect
        self.source_anchor = source_anchor
        self.menu_anchor = menu_anchor

        self.position_window()

        self._popup()

    def popup_at_widget(self, widget, widget_anchor, menu_anchor, event=None):
        # widget.get_window()
        rel_alloc = widget.get_allocation()
        # print('size', *widget.get_toplevel().get_position())
        # print(rel_alloc.x + widget.get_toplevel().get_position()[0])
        (x_offset, y_offset) = widget.get_toplevel().get_position()
        rel_alloc.x += x_offset
        rel_alloc.y += y_offset

        self.popup_at_rect(widget.get_window(), rel_alloc, widget_anchor, menu_anchor, event=None)

    def popup_at_pointer(self, event):
        window = event.get_window()
        device = get_device_from_event(event)
        pos_rect = Gdk.Rectangle()
        (pos_rect.x, pos_rect.y, m) = window.get_device_position(device)
        self.popup_at_rect(window, pos_rect, Gdk.Gravity.SOUTH_EAST, Gdk.Gravity.NORTH_WEST, event)

# interface
class MenuChild(object):
    @GObject.Signal(flags=GObject.SignalFlags.RUN_LAST, return_type=bool,
                    arg_types=(Gtk.Widget,),
                    accumulator=GObject.signal_accumulator_true_handled)
    def selection_changed(self, widget):
        pass

    def __init__(self, content=None, activatable=False, **kwargs):
        super(MenuChild, self).__init__(**kwargs)
        self.content = content
        self.activatable = activatable

        # self.connect('enter-notify-event', self.on_enter)
        # self.connect('leave-notify-event', self.on_leave)

        # if content:
        #     self.add(content)

    # override this function if you want child widgets to be keyboard navigable
    def on_selected(self, *args):
        pass

    # override this function if you want child widgets to be keyboard navigable
    def on_selection_changed(self, *args):
        pass

class _MenuChildWrapper(MenuChild, Gtk.Bin):
    def __init__(self, child=None, **kwargs):
        super(_MenuChildWrapper, self).__init__(**kwargs)

        if child:
            self.add(child)

class _Placeholder(Gtk.Bin):
    def __init__(self):
        super(_Placeholder, self).__init__()

class MenuItem(MenuChild, Gtk.Bin):
    _submenu = None

    @GObject.Signal(flags=GObject.SignalFlags.RUN_LAST, return_type=bool,
                    accumulator=GObject.signal_accumulator_true_handled)
    def activate(self):
        pass

    @GObject.Property(type=MenuBase, default=None)
    def submenu(self):
        return self._submenu

    @submenu.setter
    def submenu(self, submenu):
        self.set_submenu(submenu)

    @GObject.Property(type=str, default=None)
    def label(self):
        return self.get_label()

    @label.setter
    def label(self, label):
        self.set_label(label)

    def __init__(self, label='', icon_name=None, gicon=None, **kwargs):
        super(MenuItem, self).__init__(activatable=True, **kwargs)

        self.icon_name = None
        self.gicon = None
        self.event_window = None
        self.submenu_shown = False
        self.arrow = None

        self.get_style_context().add_class('xapp-menu-item')

        self.set_has_window(False)

        self.content_box = Gtk.Box(margin=10, hexpand=True, halign=Gtk.Align.FILL, spacing=7)
        self.add(self.content_box)

        self.left_content = _Placeholder()
        self.content_box.pack_start(self.left_content, False, False, 0)

        self._label = Gtk.Label(label=label)
        self.content_box.pack_start(self._label, False, False, 0)
        self.connect('button-release-event', self.on_button_release)

        if icon_name:
            self.set_icon_name(icon_name)
        elif gicon:
            self.set_gicon(gicon)

    def do_realize(self):
        Gtk.Bin.do_realize(self)
        if not self.activatable:
            return

        parent_window = self.get_parent_window()
        self.set_window(parent_window)

        allocation = self.get_allocation()
        attributes = Gdk.WindowAttr()
        attributes.window_type = Gdk.WindowType.CHILD
        attributes.x = allocation.x
        attributes.y = allocation.y
        attributes.width = allocation.width
        attributes.height = allocation.height
        attributes.wclass = Gdk.WindowWindowClass.INPUT_ONLY
        attributes.event_mask = self.get_events() | Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK | Gdk.EventMask.TOUCH_MASK | Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK | Gdk.EventMask.POINTER_MOTION_MASK

        attributes_mask = Gdk.WindowAttributesType.X | Gdk.WindowAttributesType.Y

        self.event_window = Gdk.Window.new(parent_window, attributes, attributes_mask)
        self.register_window(self.event_window)

    def do_unrealize(self):
        Gtk.Bin.do_unrealize(self)
        if not self.activatable:
            return

        self.unregister_window(self.event_window)
        self.event_window.destroy()
        self.event_window = None

    def do_map(self):
        Gtk.Bin.do_map(self)
        if not self.activatable:
            return

        self.event_window.show()

    def do_unmap(self):
        Gtk.Bin.do_unmap(self)
        if not self.activatable:
            return

        self.event_window.hide()

    def do_size_allocate(self, allocation):
        Gtk.Bin.do_size_allocate(self, allocation)
        if not self.activatable:
            return

        if self.event_window:
            self.event_window.move_resize(allocation.x, allocation.y, allocation.width, allocation.height)

    def do_draw(self, cr):
        width = self.get_allocated_width()
        height = self.get_allocated_height()
        context = self.get_style_context()

        Gtk.render_background(context, cr, 0, 0, width, height)
        Gtk.render_frame(context, cr, 0, 0, width, height)

        Gtk.Bin.do_draw(self, cr)

        return False

    def do_enter_notify_event(self, event):
        self.set_state_flags(Gtk.StateFlags.PRELIGHT, False)

        return False

    def do_leave_notify_event(self, event):
        self.unset_state_flags(Gtk.StateFlags.PRELIGHT)

        return False

    def do_unmap_event(self, event):
        Gtk.Bin.do_unmap_event(self, event)

        if self._submenu is not None:
            self._submenu.hide()
            self.arrow.props.icon_name = 'pan-end-symbolic'
            self.submenu_shown = False

    def set_label(self, label):
        self._label.set_label(label)

    def get_label(self, label):
        return self._label.get_label()

    def set_icon_name(self, icon_name):
        if self.icon_name:
            self.image.set_from_icon_name(icon_name, Gtk.IconSize.MENU)
        else:
            self.image = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
            self.left_content.add(self.image)

        self.icon_name = icon_name

    def set_gicon(self, gicon):
        if self.gicon:
            self.image.set_from_gicon(gicon, Gtk.IconSize.MENU)
        else:
            self.image = Gtk.Image.new_from_gicon(gicon, Gtk.IconSize.MENU)
            self.left_content.add(self.image)

        self.gicon = gicon

    def set_submenu(self, submenu):
        self._submenu = submenu

        if submenu is not None:
            self.arrow = Gtk.Image(icon_name='pan-end-symbolic', pixel_size=16)
            self.content_box.pack_end(self.arrow, False, False, 0)
        elif self.arrow is not None:
            self.arrow.destroy()
            self.arrow = None

        if isinstance(submenu, MenuSection):
            submenu.get_style_context().add_class('xapp-menu-submenu-section')
            submenu.set_no_show_all(True)
            submenu.hide()

            submenu.connect('unmap', self.hide_submenu)

    def hide_submenu(self, *args):
        self._submenu.hide()
        self.submenu_shown = False
        self.arrow.props.icon_name = 'pan-end-symbolic'

    def on_button_release(self, *args):
        # print('released')
        self.maybe_activate()

    def maybe_activate(self):
        if isinstance(self._submenu, MenuSection):
            if self.submenu_shown:
                self._submenu.hide()
                self.arrow.props.icon_name = 'pan-end-symbolic'
                self.submenu_shown = False
            else:
                self._submenu.show()
                self.arrow.props.icon_name = 'pan-down-symbolic'
                self.submenu_shown = True
        elif not self._submenu:
            self.emit('activate')

    # selection stuff
    # keyboard navigation?

class MenuSeparator(MenuChild, Gtk.Widget):
    def __init__(self):
        super(MenuSeparator, self).__init__(activatable=False)

class MenuSection(MenuChild, MenuBase):
    def __init__(self, **kwargs):
        super(MenuSection, self).__init__(**kwargs)
        
        # self.child_menu = MenuBase()
        
        # self.add(self.child_menu)

class MenuPane(MenuChild, Gtk.Box):
    def __init__(self):
        super(MenuPane, self).__init__()
        
        self.panes = []
        
    def add_pane(self):
        pane = MenuSection()
        self.panes.append(pane)
        self.pack_start(pane, True, True, 0)
        
        return pane

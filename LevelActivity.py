# LevelActivity.py
# Copyright (C) 2012  Aneesh Dogra <lionaneesh@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import gi
gi.require_version('Gtk', '3.0')

from gi.repository import Gtk
from gi.repository import GLib
from sugar3.activity.widgets import StopButton
from sugar3.activity.widgets import ActivityToolbarButton
from sugar3.activity import activity
from sugar3.graphics.toolbarbox import ToolbarBox

from math import pi, sqrt
from gettext import gettext as _
from collections import deque

from collabwrapper import CollabWrapper

ACCELEROMETER_DEVICE = '/sys/devices/platform/lis3lv02d/position'
# ACCELEROMETER_DEVICE = 'a.txt'


class MyCanvas(Gtk.DrawingArea):
    ''' Create a GTK+ widget on which we will draw '''

    def __init__(self, me):
        self.me = me
        Gtk.DrawingArea.__init__(self)
        self.connect('draw', self._draw_cb)
        self.radius = 0
        self.x = 0
        self.y = 0
        self.center = (0, 0)
        self.prev = deque([])
        self.ball_radius = 20

    def _draw_cb(self, drawing_area, cr):
        width = drawing_area.get_allocated_width()
        height = drawing_area.get_allocated_height()
        self.center = (width / 2, height / 2)
        self.radius = min(width / 2, height / 2) - self.ball_radius - 20
        cr.set_line_width(2)

        # display background
        cr.set_source_rgb(1, 1, 1)
        cr.rectangle(0, 0, width, height)
        cr.fill()

        # target background
        cr.set_source_rgb(0.9450, 0.9450, 0.9450)
        cr.arc(self.center[0], self.center[1], self.radius, 0, 2 * pi)
        cr.fill()

        # target rings, inner to outer
        cr.set_source_rgb(0, 0, 0)
        cr.arc(self.center[0], self.center[1], self.ball_radius + 2, 0, 2 * pi)
        cr.stroke()

        cr.arc(self.center[0], self.center[1], self.radius / 3, 0, 2 * pi)
        cr.stroke()

        cr.arc(self.center[0], self.center[1], self.radius * 2 / 3, 0, 2 * pi)
        cr.stroke()

        cr.arc(self.center[0], self.center[1], self.radius, 0, 2 * pi)
        cr.stroke()

        # axes
        cr.move_to(self.center[0] - self.radius, self.center[1])
        cr.line_to(self.center[0] + self.radius, self.center[1])
        cr.stroke()

        cr.move_to(self.center[0], self.center[1] - self.radius)
        cr.line_to(self.center[0], self.center[1] + self.radius)
        cr.stroke()

        # our buddies balls
        for buddy, xy in self.me.buddies.iteritems():
            (x, y) = xy
            cr.set_source_rgb(0.25, 0.25, 0.25)  # 25% gray
            cr.arc(x, y, self.ball_radius, 0, 2 * pi)
            cr.stroke()

        # our own ball
        cr.set_source_rgb(0, 0, 0)  # black
        cr.arc(self.x, self.y, self.ball_radius, 0, 2 * pi)
        cr.fill()

        # the text
        cr.set_source_rgb(0, 0, 0)  # black
        cr.move_to(width - 100, height - 80)
        cr.set_font_size(20)

        # TRANS: x is for x-axis
        cr.show_text(_("x: %.2f") % (self.x - width / 2,))

        cr.move_to(width - 99, height - 60)
        cr.set_font_size(20)

        # TRANS: y is for y-axis
        cr.show_text(_("y: %.2f") % (self.y - height / 2,))

    def motion_cb(self, x, y):
        if len(self.prev) >= 2:
            self.x = self.prev[-2][0] * 0.25 + self.prev[-1][0] * 0.5 + \
                self.radius * x * 0.25
            self.y = self.prev[-2][1] * 0.25 + self.prev[-1][1] * 0.5 + \
                self.radius * y * 0.25
            self.prev.popleft()
            self.prev.append([self.x, self.y])
        else:
            self.x = self.radius * x
            self.y = self.radius * y
            self.prev.append([self.x, self.y])

        if self.x and self.y:
            r = sqrt((self.x * self.x) + (self.y * self.y))
            r1 = min(r, self.radius)
            scale = r1 / r
            self.x *= scale
            self.y *= scale

        self.x += self.center[0]
        self.y += self.center[1]

        self.queue_draw()


class LevelActivity(activity.Activity):
    def __init__(self, handle):
        "The entry point to the Activity"
        activity.Activity.__init__(self, handle)

        self.buddies = {}

        toolbar_box = ToolbarBox()

        activity_button = ActivityToolbarButton(self)
        toolbar_box.toolbar.insert(activity_button, 0)

        separator = Gtk.SeparatorToolItem()
        separator.props.draw = False
        separator.set_expand(True)
        toolbar_box.toolbar.insert(separator, -1)

        stop_button = StopButton(self)
        toolbar_box.toolbar.insert(stop_button, -1)

        self.set_toolbar_box(toolbar_box)
        toolbar_box.show_all()

        # Draw the canvas
        canvas = MyCanvas(self)
        self.set_canvas(canvas)
        canvas.show()

        self._collab = CollabWrapper(self)
        self._collab.message.connect(self.__message_cb)
        self._collab.buddy_left.connect(self.__buddy_left_cb)
        self._collab.setup()

        self._fuse = 1
        self._timeout = GLib.timeout_add(100, self._timeout_cb, canvas)

    def _timeout_cb(self, canvas):
        fh = open(ACCELEROMETER_DEVICE)
        string = fh.read()
        xyz = string[1:-2].split(',')
        try:
            x = float(xyz[0]) / (64 * 18)
            y = float(xyz[1]) / (64 * 18)
            fh.close()
            canvas.motion_cb(x, y)
        except:
            return True

        self._fuse -= 1
        if self._fuse == 0:
            self._collab.post({'action': '%d,%d' % (canvas.x, canvas.y)})
            self._fuse = 5

        return True

    def close(self):
        GLib.source_remove(self._timeout)
        activity.Activity.close(self)

    def get_data(self):
        return None

    def set_data(self, data):
        pass

    def __message_cb(self, collab, buddy, msg):
        action = msg.get('action')
        if ',' in action:
            x, y = action.split(',')
            self.buddies[buddy.props.key] = (int(x), int(y))

    def __buddy_left_cb(self, collab, buddy):
        del self.buddies[buddy.props.key]

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

from gi.repository import Gtk
from gi.repository import GObject
from sugar3.activity import widgets
from sugar3.activity.widgets import StopButton
from sugar3.activity import activity
from math import pi, sqrt
from gettext import gettext as _
from collections import deque

ACCELEROMETER_DEVICE = '/sys/devices/platform/lis3lv02d/position'
#ACCELEROMETER_DEVICE = 'a.txt'

def read_accelerometer(canvas):
    fh = open(ACCELEROMETER_DEVICE)
    string = fh.read()
    xyz = string[1:-2].split(',')
    try:
        x = float(xyz[0]) / (64 * 18)
        y = float(xyz[1]) / (64 * 18)
        fh.close()
        canvas.motion_cb(x, y)
    except:
        pass
    GObject.timeout_add(100, read_accelerometer, canvas)

class MyCanvas(Gtk.DrawingArea):
    ''' Create a GTK+ widget on which we will draw using Cairo '''

    def __init__(self):
        Gtk.DrawingArea.__init__(self)
        self._draw_ruler = False
        self._object = None
        self.connect('draw', self._draw_cb)
        self._dpi = 96
        self.cr = None
        self.width = 0
        self.height = 0
        self.radius = 0
        self.x = 0
        self.y = 0
        self.center = (0, 0)
        self.prev = deque([])
        self.ball_radius = 20

    def _draw_cb(self, drawing_area, cr):
        self.center = (self.width / 2, self.height / 2)
        self.radius = min(self.width / 2, self.height / 2) - \
                      self.ball_radius - 20
        self.cr = cr
        cr.set_line_width(2)
        self.width = drawing_area.get_allocated_width()
        self.height = drawing_area.get_allocated_height()

        cr.set_source_rgb(1, 1, 1)
        cr.rectangle(0, 0, self.width, self.height)
        cr.fill()


        cr.set_source_rgb(0.9450, 0.9450, 0.9450)
        cr.arc(self.center[0], self.center[1],
               self.radius, 0,
               2 * pi)
        cr.fill()


        cr.set_source_rgb(0, 0, 0)
        cr.arc(self.center[0], self.center[1],
               self.ball_radius + 2, 0,
               2 * pi)
        cr.stroke()

        cr.arc(self.center[0], self.center[1],
               self.radius / 3, 0,
               2 * pi)
        cr.stroke()

        cr.arc(self.center[0], self.center[1],
               self.radius * 2 / 3, 0,
               2 * pi)
        cr.stroke()

        cr.arc(self.center[0], self.center[1],
               self.radius, 0,
               2 * pi)
        cr.stroke()

        cr.move_to(self.center[0] - self.radius, self.center[1])
        cr.line_to(self.center[0] + self.radius, self.center[1])
        cr.stroke()

        cr.move_to(self.center[0], self.center[1] - self.radius)
        cr.line_to(self.center[0], self.center[1] + self.radius)
        cr.stroke()

        self.update_ball_and_text()

    def update_ball_and_text(self):
        # Build the ball
        self.cr.set_source_rgb(0.3012, 0.6, 1) # blue
        self.cr.arc(self.x, self.y, self.ball_radius, 0, 2 * pi)
        self.cr.fill()

        # Now update the text

        # 1. Clear Text
        self.cr.set_source_rgb(1, 1, 1) # white
        self.cr.rectangle(self.width - 110, self.height - 110,
                          self.width, self.height)
        self.cr.fill()

        # 2. Update Text
        self.cr.set_source_rgb(0, 0, 0) # black
        self.cr.move_to(self.width - 100, self.height - 80)
        self.cr.set_font_size(20)

        # TRANS: X is for X axis
        self.cr.show_text(_("X: %.2f") % (self.x - self.width / 2,))

        self.cr.move_to(self.width - 99, self.height - 60)
        self.cr.set_font_size(20)

        # TRANS: Y is for Y axis
        self.cr.show_text(_("Y: %.2f") % (self.y - self.height / 2,))


    def motion_cb(self, x, y):
        if len(self.prev) >= 2:
            self.x = self.prev[-2][0] * 0.25 +  self.prev[-1][0] * 0.5 + \
                     self.radius * x * 0.25
            self.y = self.prev[-2][1] * 0.25 +  self.prev[-1][1] * 0.5 + \
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

        toolbox = widgets.ActivityToolbar(self)
        toolbox.share.props.visible = False

        stop_button = StopButton(self)
        stop_button.show()
        toolbox.insert(stop_button, -1)

        self.set_toolbar_box(toolbox)
        toolbox.show()

        # Draw the canvas
        self._canvas = MyCanvas()
        self.set_canvas(self._canvas)
        self._canvas.show()

        GObject.timeout_add(100, read_accelerometer, self._canvas)

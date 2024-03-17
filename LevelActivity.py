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
from sugar3.activity.widgets import ActivityButton, TitleEntry, \
     DescriptionItem, ShareButton, StopButton
from sugar3.activity import activity
from sugar3.graphics.toolbarbox import ToolbarBox
from sugar3.graphics.alert import Alert
from sugar3.graphics.icon import Icon

from math import pi, sqrt, atan2, degrees
from gettext import gettext as _
from collections import deque

from collabwrapper import CollabWrapper
import socket
import select

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

        # do not draw our own ball and text if we have no data
        if not self.me.accelerometer:
            return

        # our own ball
        cr.set_source_rgb(0, 0, 0)  # black
        cr.arc(self.x, self.y, self.ball_radius, 0, 2 * pi)
        cr.fill()

        # calculate angle to horizontal
        angle = degrees(atan2(self.y - self.center[1], self.x - self.center[0]))
        if angle < 0:
            angle += 360

        # the text
        cr.set_source_rgb(0, 0, 0)  # black
        cr.move_to(width - 100, height - 80)
        cr.set_font_size(20)

        cr.show_text(_("Angle: %.2f") % angle)

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


class Udp():
    addr = '224.0.0.1'
    port = 4628
    size = 32

    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.socket.bind(('', self.port))

    def put(self, data):
        self.socket.sendto(data, (self.addr, self.port))

    def get(self):
        r, w, e = select.select([self.socket], [], [], 0)
        if self.socket in r:
            (data, address) = self.socket.recvfrom(self.size)
            return (data, address[0])
        return None


class LevelActivity(activity.Activity):
    def __init__(self, handle):
        "The entry point to the Activity"
        activity.Activity.__init__(self, handle)
        self._timeout = None

        self.accelerometer = False
        try:
            open(ACCELEROMETER_DEVICE).close()
            self.accelerometer = True
        except:
            pass

        if not self.accelerometer and not self.shared_activity:
            return self._incompatible()

        self.buddies = {}

        canvas = MyCanvas(self)
        self.set_canvas(canvas)
        canvas.show()

        toolbar_box = ToolbarBox()
        self.set_toolbar_box(toolbar_box)

        toolbar_box.toolbar.insert(ActivityButton(self), 0)
        toolbar_box.toolbar.insert(TitleEntry(self), -1)
        toolbar_box.toolbar.insert(DescriptionItem(self), -1)
        toolbar_box.toolbar.insert(ShareButton(self), -1)

        separator = Gtk.SeparatorToolItem()
        separator.props.draw = False
        separator.set_expand(True)
        toolbar_box.toolbar.insert(separator, -1)
        toolbar_box.toolbar.insert(StopButton(self), -1)
        toolbar_box.show_all()

        self._udp = Udp()
        self.hosts = {}

        self._collab = CollabWrapper(self)
        self._collab.message.connect(self.__message_cb)
        self._collab.buddy_joined.connect(self.__buddy_joined_cb)
        self._collab.buddy_left.connect(self.__buddy_left_cb)
        self._collab.setup()

        self._fuse = 1
        self._timeout = GLib.timeout_add(100, self._timeout_cb, canvas)

    def _timeout_cb(self, canvas):
        if self.accelerometer:
            fh = open(ACCELEROMETER_DEVICE)
            xyz = fh.read()[1:-2].split(',')
            fh.close()
            x = float(xyz[0]) / (64 * 18)
            y = float(xyz[1]) / (64 * 18)
            canvas.motion_cb(x, y)
            canvas.queue_draw()

        self._fuse -= 1
        if self._fuse == 0:
            if self.accelerometer:
                self._collab.post({'action': '%d,%d' % (canvas.x, canvas.y)})
            self._fuse = 10

        if not self.shared_activity:
            return True

        if self.accelerometer:
            self._udp.put('%d,%d' % (canvas.x, canvas.y))

        data = self._udp.get()
        while data:
            (data, ip4_address) = data
            if ip4_address in self.hosts:
                key = self.hosts[ip4_address]
            else:
                key = ip4_address
                self.hosts[key] = ip4_address  # temporary

            (x, y) = data.split(',')
            self.buddies[key] = (int(x), int(y))
            if not self.accelerometer:
                self.get_canvas().queue_draw()
            data = self._udp.get()

        return True

    def close(self):
        if self._timeout:
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
            if not self.accelerometer:
                self.get_canvas().queue_draw()

    def __buddy_joined_cb(self, collab, buddy):
        if buddy.props.ip4_address in self.hosts:
            del self.buddies[self.hosts[buddy.props.ip4_address]]  # temporary
        self.hosts[buddy.props.ip4_address] = buddy.props.key

    def __buddy_left_cb(self, collab, buddy):
        if buddy.props.key in self.buddies:
            del self.buddies[buddy.props.key]
        if buddy.props.ip4_address in self.hosts:
            del self.hosts[buddy.props.ip4_address]

    def _incompatible(self):
        ''' Display abbreviated activity user interface with alert '''
        toolbox = ToolbarBox()
        stop = StopButton(self)
        toolbox.toolbar.add(stop)
        self.set_toolbar_box(toolbox)

        title = _('Activity not compatible with this system.')
        msg = _('Please erase the activity.')
        alert = Alert(title=title, msg=msg)
        alert.add_button(0, 'Stop', Icon(icon_name='activity-stop'))
        self.add_alert(alert)

        label = Gtk.Label(_('You do not have an accelerometer.'))
        self.set_canvas(label)

        alert.connect('response', self.__incompatible_response_cb)
        stop.connect('clicked', self.__incompatible_stop_clicked_cb,
                     alert)

        self.show_all()

    def __incompatible_stop_clicked_cb(self, button, alert):
        self.remove_alert(alert)

    def __incompatible_response_cb(self, alert, response):
        self.remove_alert(alert)
        self.close()

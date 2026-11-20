"""The HUD's windows: one per section, frameless, transparent and always on top, and the
small panel that shows in move mode.

Locked, a section lets every click through and shows only its content. In move mode it
gets a tint, can be dragged, and resized at its corner, which scales its content. A text
section's box fits closely round its text, so its name shows only when the pointer rests
on it; the others show their name. The panel says what to do, shows or hides sections, and locks or quits.
"""

import dataclasses
import functools
import logging
import math
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import ClassVar

from PySide6.QtCore import QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontInfo, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStyle,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from turbohud.core.hud import (
    BANNER_SHADE,
    FONT_SIZES,
    MARGIN,
    SPACINGS,
    WINNER_BLACK_FROM,
    WINNER_FLAG_FROM,
    WINNER_PICTURE,
    WINNER_SIZE,
    Sectors,
    base_size,
    beside,
    centred_text,
    content_shift,
    content_size,
    drawn_scale,
    end_room,
    fitting_scale,
    font_for_height,
    font_scale,
    group_tint_boxes,
    has_tint,
    help_lines,
    hud_lines,
    is_text_section,
    level_bar,
    panel_categories,
    pedal_bars,
    pedal_space,
    place_text,
    resize_edges,
    resized,
    sector_bars,
    steady_rows,
    text_box,
    text_can_centre,
    tight_height,
)
from turbohud.core.leader import NEW_LEADER, WINNER
from turbohud.core.race import (
    RADAR_FULL,
    Blip,
    DeltaBarView,
    RadarView,
    radar_arrow,
    radar_car_size,
    radar_edge_blips,
    rev_lights,
)
from turbohud.core.settings import GROUPS
from turbohud.core.trackmap import MapDot, TrackMapView, map_transform, outline_from_path, road_width
from turbohud.hud.painter import (
    AHEAD_COLOR,
    BEHIND_COLOR,
    DRAFT_COLOR,
    LIFT_COLOR,
    cap_height,
    draw_bars,
    draw_delta_bar,
    draw_hud,
    draw_level,
    draw_sectors,
    measures,
    text_ink,
    text_width,
    using,
)
from turbohud.overlay.layouts_window import STATUS_COLOUR, LayoutsWindow

TINT = (23, 56, 97, 153)  # move mode's background: red, green, blue, opacity (0-255)
# Move mode's place label (SectionWindow.show_place): shown this long after the last move, this
# size, on this background.
PLACE_LABEL_MS = 2000
PLACE_LABEL_PX = 12
PLACE_LABEL_BACK = (12, 16, 24, 240)  # nearly solid: the section's large sample text is under it
BORDER = (120, 170, 230)
LABEL_COLOR = (200, 220, 245)
MIN_WIDTH = 40
MIN_HEIGHT = 10  # a text section's box: any shorter and there is nothing left to grab
BLUE_FLAG = (0, 0, 128)  # navy
BLUE_FLAG_EDGE = (0, 0, 64)  # its outline, a darker blue
BLUE_FLAG_EDGE_WIDTH = 2
CHECKER_ROWS = 4  # the race winner's checkered flag: squares down each end of the banner
CHECKER_LIGHT, CHECKER_DARK = '#f2f2f2', '#111111'
BLUE_FRAME_EDGE = 3  # the blue frame's top and bottom on the yellow box, in pixels at scale 1
BACKDROP = (0, 0, 0, 40)  # the light tint behind a section's text (option), RGBA
BLUE_SAMPLE = 0.6  # the bar's opacity in move mode, to place it
DELTA_BAR_SAMPLE = DeltaBarView(0.4, -1.0, '\u22120.40')  # the delta bar in move mode: ahead, gaining
LEVEL_SAMPLE = (0.7, 'ahead')  # a level bar in move mode, to place the section
SECTORS_SAMPLE = Sectors(('#c77dff', '#5ee07a', None))  # the sector bars in move mode
REVS_SAMPLE = Sectors(rev_lights(0.75))  # the gear's rev lights in move mode
PANEL_LINES_WIDTH = 50  # the move-mode panel's line spacing boxes: three digits and the arrows
PANEL_COMBO_WIDTH = 56  # the move-mode panel's group lists: wide enough for '-' and A to G
PANEL_SMALL_BUTTON = 32  # its one-character buttons (centre, match a group, delete a preset)
PANEL_FONT_WIDTH = 96  # its font lists: a font's name, cut where longer (the list opens wider)
PANEL_FONT_OPEN = 220  # an open font list: wide enough for most fonts' names in full
PANEL_TABS_ROOM = 8  # room between the help text and the tabs
PANEL_TAB_LINE, PANEL_TAB_GAP = 2, 4  # the line below the tabs, and the room between it and the rows
PANEL_TAB_TEXT = '#0f1e37'  # the open tab's name: the panel's dark blue, on the border's light blue
FONT_GLOBAL = 'global'  # a section's font list: the global font (FONT_GLOBAL_KEY its item's data)
FONT_GLOBAL_KEY = '\x00global'  # not a font's name: Qt keeps no None as an item's data
SYSTEM_FONT = 'System font'


def family_of(data):
    """A font list item's family as the app takes it: None for global, else the family."""
    return None if data == FONT_GLOBAL_KEY else data


def fill_fonts(box, families, chosen, with_global=False):
    """Fill the font list `box`: global first (`with_global`, a section's list), the system font,
    then `families` ({family: file name}); `chosen` picked (None global, '' the system font), a
    chosen family no longer there listed as missing. Says nothing while it fills."""
    box.blockSignals(True)
    box.clear()
    if with_global:
        box.addItem(FONT_GLOBAL, FONT_GLOBAL_KEY)
    box.addItem(SYSTEM_FONT, '')
    for family, file in families.items():
        box.addItem(family, family)
        box.setItemData(box.count() - 1, file, Qt.ToolTipRole)
    if chosen and chosen not in families:
        box.addItem(f'{chosen} (missing)', chosen)
    wanted = FONT_GLOBAL_KEY if chosen is None and with_global else chosen
    box.setCurrentIndex(max(box.findData(wanted), 0))
    box.blockSignals(False)


# Its word buttons (All, None, Save, Load, Delete) are at least this wide, and wider where the
# system's buttons need it for the word: with a fixed width macOS cut "None" and "Delete" short.
PANEL_WORD_BUTTON = 54
PANEL_HEADING = '#9fb8d8'  # the panel's small headings: the columns and the kinds of section
PANEL_EMPTY = '#5d7799'  # the dot where a section has no such option
# The panel's text is at most this many pixels: the Mac's own size. Linux desktops use about
# 15 px (Adwaita Sans 11 pt), which made the panel 866 px tall with a row per section.
PANEL_FONT_PX = 13
# The panel fits the screen it opens on (reported on 2026-11-13: 991 px tall on the Mac, more than a
# small Mac laptop's screen): it keeps this much room above and below, and where it would not fit,
# the rows of sections scroll, never fewer than PANEL_LEAST_ROWS px of them shown.
PANEL_SCREEN_ROOM = 16
PANEL_LEAST_ROWS = 160
RADAR_ARROW_PEN = (0, 0, 0, 220), 2.0  # the outline of an arrow at the radar's edge (radar_arrow)
RADAR_CLASS_WARNING = 2.5  # a car of another class: the width of its red or yellow warning outline
RADAR_CAR_AT = 0.5  # the local car's height in the radar, from the top: the middle
CONE_STEPS = 8  # points along a slipstream cone's far edge
CONE_OUT, CONE_IN = 30, 80  # a slipstream cone's opacity (0-255): elsewhere, local car in it
RADAR_EDGE = (120, 130, 150, 200)
RADAR_LINES = (120, 130, 150, 90)
RADAR_ME = '#f2f2f2'
RADAR_OTHER = '#8c95a3'  # a car near but not counting (far to the side, or further away)
RADAR_ARROW_OTHER = '#d3d9e2'  # such a car's arrow at the edge: lighter, to be seen (2026-11-12)
# In move mode: one car beside, one closing in behind, one ahead.
RADAR_SAMPLE = (
    Blip(-1.0, 3.0, 0.0, 0.0),
    Blip(-9.5, -1.0, 0.1, 0.3),
    Blip(11.0, 0.5, -0.05, None, False),
)
MAP_BACK = (10, 14, 22, 110)  # behind the track map, RGBA
MAP_ROAD = (205, 212, 224, 210)
MAP_ROAD_EDGE = (0, 0, 0, 170)
MAP_START = '#ffffff'
MAP_PADDING = 0.08  # room round the track, as a share of the map
MAP_DOT = 0.026  # a car's dot radius, as a share of the map
MAP_COLORS = {
    'me': '#ffffff',
    'leader': '#ffc61a',  # gold
    'ahead': BEHIND_COLOR,  # red, as a gap ahead in the player list
    'behind': AHEAD_COLOR,  # green, as a gap behind
    'backmarker': '#5b8cff',  # bluish: about to be lapped
    'other': '#8c95a3',
    'car': '#e6ebf2',  # a spectator's map: every car
}
MAP_SIZES = {
    'me': 0.9,  # a little smaller than the cars around: over one, its ring shows inside that car's dot (the user)
    'leader': 1.0,
    'ahead': 1.0,
    'behind': 1.0,
    'backmarker': 0.65,
    'other': 0.55,
    'car': 0.8,
}
MAP_OTHER_ALPHA = 150  # the other cars are faint
MAP_PIT_OPACITY = 0.4  # a car in the pits is dimmed
MAP_RING = 0.4  # the local player's ring: its width, as a share of its radius
MAP_YELLOW = '#ffd400'  # the ring around a car the yellow flag is out for (race.YELLOW_COLOR)
MAP_OWN_YELLOW = 3.0  # the width of the yellow ring round the player's own dot when it caused a flag
MAP_YELLOW_ROAD_ALPHA = 220  # a sector under a yellow flag, over the road


@functools.cache  # the same one each time, so the map's road layer is kept (SectionWindow._road_layer)
def _sample_map():
    """A track map to place the section in move mode: an oval with a car of each kind."""

    def at(step):
        turn = 2 * math.pi * step / 40
        return (100 * math.cos(turn), 60 * math.sin(turn))

    outline = outline_from_path([at(step) for step in range(40)], True, (at(0), (0.0, 1.0)))

    roles = (('leader', 30), ('backmarker', 9), ('ahead', 13), ('behind', 2), ('me', 6))
    return TrackMapView(outline, tuple(MapDot(at(step), role) for role, step in roles))


log = logging.getLogger(__name__)


def window_flags():
    flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
    if sys.platform != 'darwin':
        flags |= Qt.Tool  # no taskbar button; on the Mac a tool window hides when inactive
    return flags


def _set_input(widget, native, transparent):
    """Make a shown window click-through or not. True if it was done in place; False if
    the flag change hid the window (then it must be shown again)."""
    if getattr(native, 'input_in_place', False) and widget.windowHandle() is not None:
        # Wayland: change it on the shown window. Re-creating it would make the desktop
        # treat it as a new window (Hyprland would tile it again).
        widget.windowHandle().setFlag(Qt.WindowTransparentForInput, transparent)
        return True
    widget.setWindowFlag(Qt.WindowTransparentForInput, transparent)
    return False


# The edges resize_edges names, as Qt has them, and the cursor for each edge or corner.
RESIZE_FLAGS = {
    'left': Qt.LeftEdge,
    'right': Qt.RightEdge,
    'top': Qt.TopEdge,
    'bottom': Qt.BottomEdge,
}
RESIZE_CURSORS = {
    frozenset({'left'}): Qt.SizeHorCursor,
    frozenset({'right'}): Qt.SizeHorCursor,
    frozenset({'top'}): Qt.SizeVerCursor,
    frozenset({'bottom'}): Qt.SizeVerCursor,
    frozenset({'top', 'left'}): Qt.SizeFDiagCursor,
    frozenset({'bottom', 'right'}): Qt.SizeFDiagCursor,
    frozenset({'top', 'right'}): Qt.SizeBDiagCursor,
    frozenset({'bottom', 'left'}): Qt.SizeBDiagCursor,
}


# The user's picture for the race winner's banner (hud.WINNER_PICTURE), next to the code as move mode's preview
# race is, also in the built app.
WINNER_PATH = Path(__file__).resolve().parents[2] / 'assets' / 'resources' / WINNER_PICTURE


@functools.cache
def winner_picture(path=WINNER_PATH):
    """The winner's banner picture, or None where it cannot be read."""
    image = QImage(str(path))
    return None if image.isNull() else image


@functools.lru_cache(maxsize=4)
def winner_banner(width, height, flag_width, ratio=1.0):
    """The race winner's banner `width` x `height` (logical pixels, at `ratio` device pixels each), made
    once per size: the picture's black stretched to all but `flag_width` at the right end, where its flag
    part keeps its shape; inside rounded corners as the other banners. None without the picture."""
    picture = winner_picture()
    if picture is None or width <= 0 or height <= 0:
        return None
    made = QImage(round(width * ratio), round(height * ratio), QImage.Format_ARGB32_Premultiplied)
    made.setDevicePixelRatio(ratio)
    made.fill(Qt.transparent)
    painter = QPainter(made)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    box = QPainterPath()
    box.addRoundedRect(QRectF(0, 0, width, height), 6, 6)
    painter.setClipPath(box)
    full_width, full_height = WINNER_SIZE
    split = width - flag_width
    painter.drawImage(
        QRectF(0, 0, split, height),
        picture,
        QRectF(WINNER_BLACK_FROM, 0, WINNER_FLAG_FROM - WINNER_BLACK_FROM, full_height),
    )
    painter.drawImage(
        QRectF(split, 0, flag_width, height),
        picture,
        QRectF(WINNER_FLAG_FROM, 0, full_width - WINNER_FLAG_FROM, full_height),
    )
    painter.end()
    return made


class SectionWindow(QWidget):
    drawing_time = 0.0  # seconds all sections have spent drawing, for the log
    drawing_by: ClassVar[
        dict
    ] = {}  # section name -> seconds it spent drawing since taken (take_drawing_by), for the log
    text_resized = Signal(str)  # a text section's name, resized by hand: its text size or width changed
    clicked = Signal(str)  # the section's name, clicked in move mode: the arrow keys nudge it

    def __init__(self, native, theme, section):
        super().__init__(None, window_flags())
        self.native = native
        self.theme = theme
        self.section = section
        self.rows = []
        self.pedals = None  # (throttle, brake), 0 to 1, for a section with pedal bars
        self.opacity = None  # the blue flag's opacity, 0 to 1; None: not shown
        self.radar = None  # the radar's turbohud.core.race.RadarView; None: not shown
        self.trackmap = None  # the track map's turbohud.core.trackmap.TrackMapView; None: not shown
        self.level = None  # (0 to 1, colour) for a section with a level bar
        self.backdrop = False  # its tint (its own option): behind the text while locked, the map's square
        self.locked = True
        self.wanted = True  # the player wants it shown
        self.group = ''  # sections of the same group move together (move mode)
        self.text_centred = False  # its text in the middle of its box (an option)
        self.delta_view = None  # the delta bar's content (a DeltaBarView)
        self.banner = None  # the race leader banner's core.leader.Banner while it shows
        self.preview_winner = False  # move mode shows the race winner's banner (the panel's 🏁)
        self.radar_cone = True  # the radar's sample in move mode shows slipstream cones (an option)
        self.sector_bars = True  # a section with sector bars shows them (an option)
        # A text section's text size in pixels (core.hud.font_scale): the app sets it, and its box
        # follows (text_box). None: the box sets the size, as before text sizes.
        self.font = None
        self.text = is_text_section(section)  # sized by a text size, not by its box
        self.resizable = True  # at its edges in move mode: a text section by its text size (_resize_text)
        self.own_font = None  # a text section's own text size; None: the global one (the app sets it)
        # A text section's own font family ('' the system's); None: the global one (the app sets it).
        self.own_family = None
        self.selected = False  # clicked last in move mode: the arrow keys nudge it
        # Move mode: where it is and its size while moved, resized or nudged, and a moment after
        # (place_text; asked for by the user on 2026-11-16). '' when not shown.
        self.place_label = ''
        self.screens = None  # the screens (x, y, width, height) its place is counted on; the app sets them
        self._place_seen = None  # its place when Qt last said it moved (_moved)
        # On the design screen: (frame, scale), so its place is shown on the designed size (place_text).
        self.design = None
        # Until then (time.monotonic) TurboHUD moves it (a preset, Undo, the design screen): no label.
        self._quiet_until = 0.0
        self._place_timer = QTimer(self)
        self._place_timer.setSingleShot(True)
        self._place_timer.setInterval(PLACE_LABEL_MS)
        self._place_timer.timeout.connect(self.hide_place)
        # While locked, a HudCanvas may draw this section with every other in one window per
        # screen, and this window stays hidden: 17 windows above the game cost it frames.
        self.canvas = None
        # Its group's one tint is behind it (GroupTints, a window of its own on Windows): no tint
        # of its own then.
        self.under_group_tint = False
        # The track map's square, road and start line, drawn once into an image and kept while
        # the track, the size, the tint and the road's colour stay: (what it was drawn for, image).
        self._road_layer = None
        self.road_draws = 0  # times that image was drawn, for tests
        self.setWindowTitle(f'TurboHUD - {section.label}')
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWindowFlag(Qt.WindowTransparentForInput, True)
        width, height = base_size(section, theme.scale, text_width)
        if not section.bar:
            height = tight_height(section, theme.scale, text_ink)
        # No room for its name in the box (move mode): its name and what it shows.
        self.setToolTip(f'{section.label}: {section.tip}' if section.tip else section.label)
        self.base = (width, height)
        # Resized at any edge or corner in move mode (resize_edges), by the desktop where it can:
        # Qt's size grip pointed and pulled the wrong way at times (reported by the user on 2026-11-13).
        self._resizing = None  # (edges, where the drag began on the screen, the box then): resized here
        self.setMouseTracking(True)  # the cursor shows the edge under it
        lowest = round(self.base[1] * 0.3)
        if self.text:
            self.setMinimumSize(1, 1)  # its box follows its text size, however small
        else:
            self.setMinimumSize(MIN_WIDTH, lowest if section.bar else max(lowest, MIN_HEIGHT))

    @property
    def measure(self):
        """text_width in this section's font, for turbohud.core.hud's `measure`."""
        return measures(self.own_family)[0]

    @property
    def ink(self):
        """text_ink in this section's font, for turbohud.core.hud's `ink`."""
        return measures(self.own_family)[1]

    def placement(self):
        # On Wayland only the desktop knows where the window is; ask it where possible.
        native = getattr(self.native, 'placement', None)
        return (native and native(self)) or (self.x(), self.y(), self.width(), self.height())

    def show_place(self, place=None):
        """Move mode: show where it is (`place`, else where Qt has it) and its size for a moment."""
        if self.locked or not self.wanted or self.screens is None or time.monotonic() < self._quiet_until:
            return
        text = place_text(place or self.geometry().getRect(), self.screens, self.design)
        if text != self.place_label:
            self.place_label = text
            self.update()
        self._place_timer.start()  # gone PLACE_LABEL_MS after the last move

    def hide_place(self):
        if self.place_label:
            self.place_label = ''
            self.update()

    def quiet_place(self, until):
        """TurboHUD moves it now, not the player (a preset, Undo or Redo, the design screen): no label
        until `until` (time.monotonic), as the moves may still be arriving (Wayland lags)."""
        self._quiet_until = until
        self.hide_place()

    def _follows_live(self):
        """Whether Qt knows where it is while it moves (not on Wayland, where the app asks the desktop)."""
        return getattr(self.native, 'placement', None) is None

    def _moved(self):
        """Its place changed for Qt: shown in move mode. Only a real change: a window made again
        as move mode begins reports its place once more without moving."""
        place = self.geometry().getRect()
        if place == self._place_seen:
            return
        self._place_seen = place
        if not self.locked and self._follows_live():
            self.show_place(place)

    def moveEvent(self, event):
        super().moveEvent(event)
        self._moved()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._moved()

    def show_on_top(self):
        if self.on_canvas:
            self.hide()  # the canvas draws it
            return
        self.show()
        log.info('%s: %s', self.section.name, self.native.raise_window(self))

    @property
    def on_canvas(self):
        """Whether the canvas draws this section now, not its own window: while locked."""
        return self.canvas is not None and self.locked

    def update(self, *args):
        """Draw the section again: on the canvas while it draws it, else on this window."""
        if self.on_canvas:
            self.canvas.redraw(self)
        else:
            super().update(*args)

    def show_content(
        self,
        rows,
        pedals=None,
        opacity=None,
        radar=None,
        trackmap=None,
        level=None,
        delta_view=None,
        banner=None,
    ):
        """Take the latest content; True if it differs from what is shown, so the
        section needs drawing again. A hidden section keeps the content but needs no
        drawing: showing it draws what it has. Locking, showing, the theme and the tint
        ask for a redraw themselves."""
        content = (rows, pedals, opacity, radar, trackmap, level, delta_view, banner)
        shown = (
            self.rows,
            self.pedals,
            self.opacity,
            self.radar,
            self.trackmap,
            self.level,
            self.delta_view,
            self.banner,
        )
        if content == shown:
            return False
        (
            self.rows,
            self.pedals,
            self.opacity,
            self.radar,
            self.trackmap,
            self.level,
            self.delta_view,
            self.banner,
        ) = content
        return self.wanted

    def set_locked(self, locked):
        if locked == self.locked:
            return
        self.locked = locked
        if locked:
            self.place_label = ''  # move mode's place is not shown over the race
        if not self.wanted:
            return  # hidden: stays click-through and empty in both modes
        in_place = _set_input(self, self.native, locked)
        movable = getattr(self.native, 'set_movable', None)
        if movable is not None:
            movable(self, not locked)
        self.setCursor(Qt.ArrowCursor if locked else Qt.OpenHandCursor)
        if not in_place or self.canvas is not None:
            self.show_on_top()  # changing a window flag hides the window; the canvas hides it
        self.update()

    def set_wanted(self, wanted):
        """Show or hide the section (the panel's tick boxes). A hidden section keeps its
        window, draws nothing and lets every click through: showing it again then needs
        no new window, which a desktop could place anywhere, or make fullscreen over a
        fullscreen game. A system whose Native says `hides_windows` takes the window off
        the screen instead, so that nothing of it stays above the game."""
        if wanted == self.wanted:
            return
        self.wanted = wanted
        in_place = _set_input(self, self.native, self.locked or not wanted)
        movable = getattr(self.native, 'set_movable', None)
        if movable is not None:
            movable(self, wanted and not self.locked)
        if not wanted and getattr(self.native, 'hides_windows', False):
            self.hide()
            if self.on_canvas:
                self.canvas.redraw(self)  # its place on the canvas is cleared
            return
        if not in_place:
            self.show_on_top()
        self.update()

    def _edges_at(self, event):
        """The edges under the pointer that resize this section (resize_edges); () where none."""
        if self.locked or not self.resizable:
            return ()
        point = event.position()
        return resize_edges(point.x(), point.y(), self.width(), self.height())

    def mousePressEvent(self, event):
        if self.locked or event.button() != Qt.LeftButton:
            return
        self.clicked.emit(self.section.name)
        self.activateWindow()  # the keyboard to TurboHUD: the arrow keys nudge it
        self.show_place(self.placement())  # where it is, before it moves
        edges = self._edges_at(event)
        if not edges:
            self.windowHandle().startSystemMove()
            return
        if self.text:
            # Height sets its text size, width adds room: followed here, to size the text live.
            self._resizing = (edges, event.globalPosition(), self.geometry().getRect())
            return
        flags = Qt.Edges()
        for name in edges:
            flags |= RESIZE_FLAGS[name]
        if not self.windowHandle().startSystemResize(flags):
            # The desktop cannot (macOS): resize it here, following the pointer.
            self._resizing = (edges, event.globalPosition(), self.geometry().getRect())

    def mouseMoveEvent(self, event):
        if self._resizing is not None and self.text:
            edges, start, box = self._resizing
            moved = event.globalPosition() - start
            self._resize_text(edges, box, round(moved.x()), round(moved.y()))
            return
        if self._resizing is not None:
            edges, start, box = self._resizing
            moved = event.globalPosition() - start
            least = (self.minimumWidth(), self.minimumHeight())
            self.setGeometry(*resized(box, edges, round(moved.x()), round(moved.y()), least))
            return
        if not self.locked:
            self.setCursor(RESIZE_CURSORS.get(frozenset(self._edges_at(event)), Qt.OpenHandCursor))

    def mouseReleaseEvent(self, _event):
        if self._resizing is not None and self.text:
            self.text_resized.emit(self.section.name)
        self._resizing = None

    def _resize_text(self, edges, box, dx, dy):
        """A text section dragged at `edges` by (dx, dy) from `box` (asked for by the user on
        2026-11-13): a corner sets its text size (font_for_height; the box tight round it in
        height), an edge adds room: the top or bottom edge height (longer pedal bars beside the
        speed, the text centred and the same size), the left or right edge width, never less
        than the text needs. The opposite edges stay put."""
        x, y, width, height = resized(box, edges, dx, dy, (1, 1))
        corner = len(edges) == 2
        if corner:
            font = font_for_height(self.section, height, self.ink)
            if font != self.font:
                self.font = self.own_font = font
        fitted = text_box(
            self.section, (x, y, width, height), self.font, self.measure, self.ink, keep_height=not corner
        )
        if 'top' in edges:  # the bottom edge stays put
            fitted = (fitted[0], box[1] + box[3] - fitted[3], *fitted[2:])
        if 'left' in edges:  # the right edge stays put
            fitted = (box[0] + box[2] - fitted[2], fitted[1], *fitted[2:])
        self.setGeometry(*fitted)
        self.update()

    def _paint_corner(self, painter):
        """Move mode: two short lines in the bottom right corner of a resizable section,
        where it can be resized (and at every edge)."""
        painter.save()
        painter.setPen(QPen(QColor(*BORDER), 2))
        right, bottom = self.width() - 4, self.height() - 4
        for step in (6, 11):
            painter.drawLine(QPointF(right - step, bottom), QPointF(right, bottom - step))
        painter.restore()

    def paintEvent(self, _event):
        began = time.perf_counter()
        painter = QPainter(self)
        self.draw(painter, not self.under_group_tint)
        self.drew(time.perf_counter() - began)
        if not self.locked and self.wanted and self.resizable:
            self._paint_corner(painter)
        if not self.locked and self.wanted and self.selected:
            # The section the arrow keys nudge: a frame in the highlight colour.
            painter.setPen(QPen(QColor(LIFT_COLOR), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 8, 8)
        if not self.locked and self.wanted and self.place_label:
            self._paint_place(painter)
        painter.end()
        SectionWindow.drawing_time += time.perf_counter() - began

    def _paint_place(self, painter):
        """Move mode: the place label (show_place) in a small dark box at the top left, over the
        section's sample text, readable over any game."""
        painter.save()
        font = painter.font()
        font.setPixelSize(PLACE_LABEL_PX)
        font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        box = QRectF(4, 4, metrics.horizontalAdvance(self.place_label) + 12, metrics.height() + 6)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(*PLACE_LABEL_BACK))
        painter.drawRoundedRect(box, 4, 4)
        painter.setPen(QColor(LIFT_COLOR))
        painter.drawText(box, Qt.AlignCenter, self.place_label)
        painter.restore()

    def drew(self, seconds):
        """Count `seconds` of drawing for this section (the log's costliest sections)."""
        name = self.section.name
        SectionWindow.drawing_by[name] = SectionWindow.drawing_by.get(name, 0.0) + seconds

    @staticmethod
    def take_drawing_by():
        """{section name: seconds drawing} since the last call, and start again."""
        taken, SectionWindow.drawing_by = SectionWindow.drawing_by, {}
        return taken

    def tints_itself(self):
        """Whether it draws the light tint behind its text now (locked, its tint on, text to
        show): what a group's one tint stands in for on the HUD canvas."""
        section = self.section
        if section.drawing or section.bar or section.background:
            return False
        return self.wanted and self.locked and self.backdrop and bool(self.rows)

    def draw(self, painter, own_tint=True, faded=True):
        """Draw the section into `painter`, its top-left corner at (0, 0) and as large as
        this window: on the window itself, or on a HudCanvas that holds every section.
        `own_tint` False: no tint of its own, as its group's one tint is behind it.
        `faded` False: the race leader banner at full strength (_paint_faded fades it).
        In its own font where it has one (own_family)."""
        if not self.wanted:
            return
        with using(self.own_family):
            self._draw(painter, own_tint, faded)

    def _draw(self, painter, own_tint, faded):
        """draw, in the section's font."""
        if faded and self._fading():
            self._paint_faded(painter, own_tint)
            return
        painter.setRenderHint(QPainter.Antialiasing)
        if self.section.drawing == 'radar':
            self._paint_radar(painter)
            return
        if self.section.drawing == 'map':
            self._paint_map(painter)
            return
        if self.section.drawing == 'delta':
            self._paint_delta(painter)
            return
        if self.section.bar:
            self._paint_bar(painter)
            return
        rows = self.rows
        if not self.locked:
            painter.setPen(QPen(QColor(*BORDER), 2))
            painter.setBrush(QColor(*TINT))
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 8, 8)
            rows = rows or list(self.section.samples[0])  # something to place, also before a race
        painter.save()  # the race leader banner fades as a whole: restored at the end
        winner = False
        if self.section.banner and self.locked and self.banner is not None:
            winner = self.banner.winner
        elif self.section.banner and not self.locked and self.preview_winner:
            # Move mode, with the panel's 🏁 on: the winner's banner, to see and place it (2026-11-17).
            winner = True
            rows = [replace(row, text=row.text.replace(NEW_LEADER, WINNER, 1)) for row in rows]
        # After the text: the winner's checkered flag. Only with the flag: kept for every banner, it
        # put a new leader's text that far left of the middle (reported by the user on 2026-11-17).
        inset = end_room(self.section, self.height()) if winner else 0
        bars = pedal_space(self.theme.scale) if self.section.pedals else 0
        if self.font is not None:
            # Its text size, whatever the box (text_box fits it); only a live text wider than the box
            # is drawn smaller, to fit.
            scale = fitting_scale(
                rows,
                font_scale(self.font),
                self.width() - 2 * inset,
                text_width,
                self.section.spacing,
                self.section.pedals,
            )
        else:
            scale = drawn_scale(
                self.section,
                (self.width(), self.height()),
                rows,
                self.base[1],
                self.theme.scale,
                text_ink,
                text_width,
            )
        left = 0
        down = content_shift(self.section, self.height(), scale, text_ink)
        if self.section.background and rows:  # its own colour, also in move mode, to see it
            if self.section.banner and winner and self._paint_winner(painter, inset):
                pass  # the user's picture: black, the checkered flag at the right end
            elif self.section.banner:
                self._paint_shade(painter)
                if winner:
                    self._paint_checkers(painter, inset)  # where the picture is missing
            else:
                self._paint_backdrop(painter, self.section.background)
            if self.opacity is not None and not self.section.banner:
                self._paint_blue_frame(painter, scale)  # the blue flag too (turbohud.core.flagstack)
        elif self.locked and self.backdrop and rows and own_tint:
            self._paint_backdrop(painter)
        if self.section.pedals and rows:  # no bars without a speed (menu, no game)
            throttle, brake = self.pedals or (None, None)
            draw_bars(painter, pedal_bars(self.width(), self.height(), scale, throttle, brake))
            # The bars keep to the window's edges however small the text gets.
            left, centred_down = centred_text(
                (self.width(), self.height()),
                rows,
                scale,
                text_width,
                cap_height,
                pedal_space(scale) // 2,
                self.section.spacing,
            )
            if not self.section.level:  # with the rev lights below, those are centred with the text
                down = centred_down
        painter.translate(0, down)
        centre = self.text_centred and text_can_centre(self.section)
        theme = self.theme
        if self.section.background and rows:
            # On a solid box the text needs no dark edge: on the yellow flag it smudged the letters.
            theme = dataclasses.replace(theme, outline_color='#00000000')
        # The usual content's columns are made room for too, so they stay put (draw_hud).
        spacing = self.section.spacing
        reserve = hud_lines(steady_rows(self.section.samples[0]), scale, spacing) if self.rows else ()
        if self.section.pedals:
            # Between the pedal bars every line in the middle of the box, each measured with its digits
            # as zeros: the gear above the speed, and the speed in its slot, stay put (asked for by the
            # user on 2026-11-13).
            left, centre = 0, True
        draw_hud(
            painter,
            hud_lines(rows, scale, spacing),
            theme,
            scale,
            left,
            self.width() - left - inset,
            centre,
            reserve,
            snug=self.section.snug,
        )
        if self.section.level and rows:
            sample = (
                SECTORS_SAMPLE
                if self.section.sectors
                else REVS_SAMPLE
                if self.section.name == 'speed'
                else LEVEL_SAMPLE
            )
            level = self.level or (None if self.locked else sample)
            if self.section.sectors and not self.sector_bars:
                level = None  # turned off: the room stays, so the text keeps its size
            if level is not None:
                content_height = content_size(rows, scale, text_width, self.section.spacing)[1]
                # Between the pedal bars where the section has them (the speed's rev lights).
                inner = pedal_space(scale) // 2 if self.section.pedals else 0
                painter.translate(inner, 0)
                if isinstance(level, Sectors):
                    count = len(level.colours)
                    bars = sector_bars(self.width() - 2 * inner, content_height, scale, count)
                    draw_sectors(painter, bars, level.colours)
                else:
                    draw_level(painter, level_bar(self.width() - 2 * inner, content_height, scale, *level))
                painter.translate(-inner, 0)
        painter.translate(0, -down)
        painter.restore()

    def _fading(self):
        """Whether the race leader banner shows part faded in or out now."""
        return self.section.banner and self.locked and self.banner is not None and self.banner.opacity < 1.0

    def _paint_faded(self, painter, own_tint):
        """The race leader banner as it fades: drawn whole at full strength, then laid on at its
        opacity as one picture. Faded piece by piece, the game showed through its box and the
        box through its letters and flags, which looked off colour (reported by the user on
        2026-11-18)."""
        opacity = min(max(self.banner.opacity, 0.0), 1.0)
        if opacity <= 0.0 or self.width() <= 0 or self.height() <= 0:
            return
        ratio = self.devicePixelRatioF()
        whole = QImage(
            round(self.width() * ratio), round(self.height() * ratio), QImage.Format_ARGB32_Premultiplied
        )
        whole.setDevicePixelRatio(ratio)
        whole.fill(Qt.transparent)
        inner = QPainter(whole)
        self.draw(inner, own_tint, faded=False)
        inner.end()
        painter.save()
        painter.setOpacity(painter.opacity() * opacity)
        painter.drawImage(QRectF(0, 0, self.width(), self.height()), whole)
        painter.restore()

    def _paint_backdrop(self, painter, color=None):
        """The light tint behind a section's text, filling the section's whole box: one that
        followed the text left part of a box bare, such as the player list's below its last
        driver (reported by the user on 2026-11-14). `color` ('#rrggbb'): a solid box of that
        colour instead (Section.background): a box that followed the text changed its size
        with each incident (the yellow flag, reported by the user on 2026-11-11). Either way
        its size is the one given it in move mode, and the text keeps its size in it."""
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(color) if color else QColor(*BACKDROP))
        painter.drawRoundedRect(QRectF(self.rect()), 6, 6)

    def _paint_shade(self, painter):
        """The race leader banner's box, shaded from grey at the left to black at the right
        (BANNER_SHADE), where the name goes."""
        shade = QLinearGradient(0, 0, self.width(), 0)
        shade.setColorAt(0.0, QColor(BANNER_SHADE[0]))
        shade.setColorAt(1.0, QColor(BANNER_SHADE[1]))
        painter.setPen(Qt.NoPen)
        painter.setBrush(shade)
        painter.drawRoundedRect(QRectF(self.rect()), 6, 6)

    def _paint_winner(self, painter, flag_width):
        """The race winner's banner from the user's picture (WINNER_PICTURE), the flag part
        `flag_width` wide at the right end; False where the picture cannot be read."""
        ratio = self.devicePixelRatioF()
        made = winner_banner(self.width(), self.height(), round(flag_width), ratio)
        if made is None:
            return False
        painter.drawImage(QRectF(self.rect()), made)
        return True

    def _paint_checkers(self, painter, width):
        """The race winner's checkered flag at the right end of the banner's box, `width` pixels
        wide: CHECKER_ROWS squares down, inside the box's rounded corners."""
        height = self.height()
        if width <= 0 or height <= 0:
            return
        size = height / CHECKER_ROWS
        painter.save()
        box = QPainterPath()
        box.addRoundedRect(QRectF(self.rect()), 6, 6)
        painter.setClipPath(box)
        painter.setPen(Qt.NoPen)
        left = self.width() - width
        painter.setBrush(QColor(CHECKER_LIGHT))
        painter.drawRect(QRectF(left, 0, width, height))
        painter.setBrush(QColor(CHECKER_DARK))
        for column in range(math.ceil(width / size)):
            for row in range(CHECKER_ROWS):
                if (row + column) % 2:
                    x = left + column * size
                    painter.drawRect(QRectF(x, row * size, min(size, left + width - x), size))
        painter.restore()

    def _paint_blue_frame(self, painter, scale):
        """The blue flag as a frame round this section's box, at the flag's fade: wide at the
        sides, in the margin before the text, and thin at the top and bottom, where the text
        reaches nearly to the edge of a tight box (a frame as wide all round hid the heading)."""
        alpha = round(255 * min(max(self.opacity, 0.0), 1.0))
        colour = QColor(*BLUE_FLAG)
        colour.setAlpha(alpha)
        side = max(4, round(MARGIN * scale) - 3)
        edge = max(3, round(BLUE_FRAME_EDGE * scale))
        width, height = self.width(), self.height()
        painter.save()
        painter.setPen(Qt.NoPen)
        painter.setBrush(colour)
        for rect in (
            QRectF(0, 0, side, height),
            QRectF(width - side, 0, side, height),
            QRectF(side, 0, width - 2 * side, edge),
            QRectF(side, height - edge, width - 2 * side, edge),
        ):
            painter.drawRect(rect)
        painter.restore()

    def _paint_radar(self, painter):
        """The proximity radar: the local car in the middle heading up, the others
        where they are around it; red when beside or within RADAR_FULL behind, yellow
        when closing in behind, grey elsewhere. The whole radar fades with its opacity.
        In move mode a sample, with a border and its name."""
        view = self.radar
        if not self.locked and view is None:
            view = RadarView(BLUE_SAMPLE, RADAR_SAMPLE, cone=(30, 20))
            if not self.radar_cone:  # the sample as the race will show it
                blips = tuple(replace(blip, in_cone=None) for blip in RADAR_SAMPLE)
                view = RadarView(BLUE_SAMPLE, blips)
        if view is None:
            return
        size = min(self.width(), self.height())
        box = QRectF((self.width() - size) / 2, (self.height() - size) / 2, size, size).adjusted(1, 1, -1, -1)
        painter.setOpacity(min(max(view.opacity, 0.0), 1.0))
        painter.setBrush(Qt.NoBrush)  # no fill: the road shows through
        if not self.locked:  # to place it; in a race an outline only gets in the way of the view
            painter.setPen(QPen(QColor(*RADAR_EDGE), 1.5))
            painter.drawRoundedRect(box, 10, 10)
        # The local car sits in the middle: cars ahead count as well as those behind.
        # view.view reaches from it to the top and the bottom edge.
        centre = QPointF(box.center().x(), box.top() + box.height() * RADAR_CAR_AT)
        per_unit = box.height() * (1 - RADAR_CAR_AT) / view.view
        w, h = radar_car_size(per_unit, box.width())
        painter.setPen(QPen(QColor(*RADAR_LINES), 1))
        painter.drawLine(QPointF(centre.x(), box.top() + 6), QPointF(centre.x(), box.bottom() - 6))
        painter.drawLine(QPointF(box.left() + 6, centre.y()), QPointF(box.right() - 6, centre.y()))
        painter.setClipRect(box)

        def car(ahead, side, angle, color):
            painter.save()
            painter.translate(centre.x() + side * per_unit, centre.y() - ahead * per_unit)
            painter.rotate(math.degrees(angle))
            painter.setPen(QPen(QColor(0, 0, 0, 160), 1))
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(QRectF(-w / 2, -h / 2, w, h), w / 4, w / 4)
            painter.restore()

        def cone(blip):
            """The slipstream behind a car ahead: from its tail, the event's reach long
            and its angle to each side; brighter when the local car is in it."""
            reach, spread = view.cone
            painter.save()
            painter.translate(centre.x() + blip.side * per_unit, centre.y() - blip.ahead * per_unit)
            painter.rotate(math.degrees(blip.angle))
            tail, radius = h / 2, reach * per_unit
            points = [QPointF(0, tail)]
            for step in range(CONE_STEPS + 1):
                turn = math.radians(-spread + 2 * spread * step / CONE_STEPS)
                points.append(QPointF(radius * math.sin(turn), tail + radius * math.cos(turn)))
            color = QColor(DRAFT_COLOR)
            color.setAlpha(CONE_IN if blip.in_cone else CONE_OUT)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawPolygon(QPolygonF(points))
            painter.restore()

        if view.cone is not None:
            for blip in view.blips:
                if blip.in_cone is not None:
                    cone(blip)

        def blip_color(blip):
            if blip.seconds is not None and blip.seconds <= RADAR_FULL:
                return BEHIND_COLOR
            if blip.seconds is not None and blip.seconds <= view.within:
                return LIFT_COLOR
            return RADAR_OTHER

        def edge(blip, color):
            """A car past the bottom edge (behind; radar_edge_blips): an arrow pointing its
            way, fainter the further off it is."""
            points, opacity = radar_arrow(
                centre.x() + blip.side * per_unit,
                blip.ahead > 0,
                (box.left(), box.top(), box.right(), box.bottom()),
                w,
                blip.seconds,
                view.within,
            )
            painter.save()
            painter.setOpacity(painter.opacity() * opacity)
            pen = QPen(QColor(*RADAR_ARROW_PEN[0]), RADAR_ARROW_PEN[1])
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(QColor(color))
            painter.drawPolygon(QPolygonF([QPointF(*point) for point in points]))
            painter.restore()

        for blip in view.blips:
            if abs(blip.ahead) > view.view:
                continue  # an arrow at the edge, drawn last (edge)
            color = blip_color(blip)
            if blip.class_color is None:
                car(blip.ahead, blip.side, blip.angle, color)
            else:
                # Another class: filled in its class's colour, the warning (red, yellow) as its outline.
                car(blip.ahead, blip.side, blip.angle, blip.class_color)
                if color != RADAR_OTHER:
                    painter.save()
                    painter.translate(centre.x() + blip.side * per_unit, centre.y() - blip.ahead * per_unit)
                    painter.rotate(math.degrees(blip.angle))
                    painter.setPen(QPen(QColor(color), RADAR_CLASS_WARNING))
                    painter.setBrush(Qt.NoBrush)
                    pad = RADAR_CLASS_WARNING / 2
                    painter.drawRoundedRect(
                        QRectF(-w / 2 - pad, -h / 2 - pad, w + 2 * pad, h + 2 * pad), w / 4, w / 4
                    )
                    painter.restore()
            if blip.in_cone:  # the car being drafted: a cyan outline
                painter.save()
                painter.translate(centre.x() + blip.side * per_unit, centre.y() - blip.ahead * per_unit)
                painter.rotate(math.degrees(blip.angle))
                painter.setPen(QPen(QColor(DRAFT_COLOR), 2))
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(QRectF(-w / 2 - 1, -h / 2 - 1, w + 2, h + 2), w / 4, w / 4)
                painter.restore()
        car(0.0, 0.0, 0.0, RADAR_ME)
        painter.setClipping(False)
        for blip in radar_edge_blips(view):  # behind, beyond the radar's reach: an arrow at its edge
            color = blip.class_color or blip_color(blip)  # another class: its colour
            edge(blip, RADAR_ARROW_OTHER if color == RADAR_OTHER else color)
        painter.setOpacity(1.0)
        if not self.locked:
            painter.setPen(QPen(QColor(*BORDER), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 8, 8)
            painter.setPen(QColor(*LABEL_COLOR))
            font = painter.font()
            font.setPixelSize(11)
            painter.setFont(font)
            painter.drawText(
                self.rect().adjusted(6, 0, -20, -3), Qt.AlignBottom | Qt.AlignLeft, self.section.label
            )

    def _paint_map(self, painter):
        """The track map: the road seen from above in a square, its start line, and
        the cars as dots (see turbohud.core.trackmap). In move mode a sample oval, with
        a border and its name."""
        view = self.trackmap
        if not self.locked and view is None:
            view = _sample_map()
        if view is not None:
            size = min(self.width(), self.height())
            left, top = (self.width() - size) / 2, (self.height() - size) / 2
            box = QRectF(left, top, size, size).adjusted(1, 1, -1, -1)
            outline = view.outline
            scale, x_off, y_off = map_transform(outline.bounds, (size, size), size * MAP_PADDING)

            def at(point):
                return QPointF(left + x_off + point[0] * scale, top + y_off - point[1] * scale)

            painter.drawImage(QPointF(0, 0), self._road_image(painter, view, box, at, scale, size))
            if view.yellow:  # a sector under a yellow flag: its road in yellow, over the usual one
                road = road_width(size)
                yellow = QColor(MAP_YELLOW)
                yellow.setAlpha(MAP_YELLOW_ROAD_ALPHA)
                painter.setPen(QPen(yellow, road, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                painter.setBrush(Qt.NoBrush)
                for part in view.yellow:
                    path = QPainterPath(at(part[0]))
                    for point in part[1:]:
                        path.lineTo(at(point))
                    painter.drawPath(path)
            radius = max(2.5, size * MAP_DOT)
            painter.setClipRect(box)  # a car off the learnt track (a road from the grid) stays inside
            for dot in view.dots:
                painter.setOpacity(MAP_PIT_OPACITY if dot.in_pit else 1.0)
                color = QColor(MAP_COLORS[dot.role])
                if dot.role == 'other':
                    color.setAlpha(MAP_OTHER_ALPHA)
                r = radius * MAP_SIZES[dot.role]
                if (
                    dot.yellow and dot.role == 'me'
                ):  # the player's own flag: an outline, never covering a car below
                    ring = max(1.5, r * MAP_RING)
                    painter.setBrush(Qt.NoBrush)
                    painter.setPen(QPen(QColor(MAP_YELLOW), MAP_OWN_YELLOW))
                    painter.drawEllipse(
                        at(dot.position), r + ring / 2 + MAP_OWN_YELLOW / 2, r + ring / 2 + MAP_OWN_YELLOW / 2
                    )
                elif dot.yellow:  # the yellow flag is out for it: a yellow ring, outside any other
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QColor(MAP_YELLOW))
                    painter.drawEllipse(at(dot.position), r + 5, r + 5)
                if dot.ahead_too:  # the leader is also the next car ahead: a red ring
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QColor(MAP_COLORS['ahead']))
                    painter.drawEllipse(at(dot.position), r + 3, r + 3)
                if dot.role == 'me':
                    # A ring, open in the middle: a car under it still shows.
                    ring = max(1.5, r * MAP_RING)
                    painter.setBrush(Qt.NoBrush)
                    painter.setPen(QPen(QColor(0, 0, 0, 200), ring + 2))
                    painter.drawEllipse(at(dot.position), r, r)
                    painter.setPen(QPen(color, ring))
                    painter.drawEllipse(at(dot.position), r, r)
                    continue
                painter.setPen(QPen(QColor(0, 0, 0, 200), 1.5))
                painter.setBrush(color)
                painter.drawEllipse(at(dot.position), r, r)
            painter.setClipping(False)
            painter.setOpacity(1.0)
        if not self.locked:
            painter.setPen(QPen(QColor(*BORDER), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 8, 8)
            painter.setPen(QColor(*LABEL_COLOR))
            font = painter.font()
            font.setPixelSize(11)
            painter.setFont(font)
            painter.drawText(
                self.rect().adjusted(6, 0, -20, -3), Qt.AlignBottom | Qt.AlignLeft, self.section.label
            )

    def _road_image(self, painter, view, box, at, scale, size):
        """The map's square (with its tint), road and start line as an image as large as
        this window, drawn again only when what it shows changes: stroking a learnt track
        of a thousand points or more took a few ms at every frame."""
        ratio = painter.device().devicePixelRatioF() if painter.device() else 1.0
        key = (self.width(), self.height(), ratio, self.backdrop, view.road)
        if self._road_layer is not None:
            outline, was, image = self._road_layer
            if outline is view.outline and was == key:
                return image
        image = QImage(
            max(1, round(self.width() * ratio)),
            max(1, round(self.height() * ratio)),
            QImage.Format_ARGB32_Premultiplied,
        )
        image.setDevicePixelRatio(ratio)
        image.fill(Qt.transparent)
        layer = QPainter(image)
        layer.setRenderHint(QPainter.Antialiasing)
        self._paint_road(layer, view, box, at, scale, size)
        layer.end()
        self._road_layer = (view.outline, key, image)
        self.road_draws += 1
        return image

    def _paint_road(self, painter, view, box, at, scale, size):
        """The map's square (with its Tint option), the road and the start line."""
        if self.backdrop:  # its Tint option, also in move mode, to see what it does
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(*MAP_BACK))
            painter.drawRoundedRect(box, 10, 10)
        outline = view.outline
        path = QPainterPath(at(outline.points[0]))
        for point in outline.points[1:]:
            path.lineTo(at(point))
        if outline.closed:
            path.closeSubpath()
        road = road_width(size)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(*MAP_ROAD_EDGE), road + 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(path)
        colour = QColor(view.road) if view.road else QColor(*MAP_ROAD)  # a fast lap's colour, for a moment
        colour.setAlpha(MAP_ROAD[3])
        painter.setPen(QPen(colour, road, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(path)
        if outline.start is not None:
            # The start line: across the road, a little wider than it.
            (sx, sz), (fx, fz) = outline.start
            reach = (road * 0.8 + 2) / scale
            ux, uz = -fz * reach, fx * reach  # across the direction of travel
            painter.setPen(QPen(QColor(MAP_START), max(2.0, road / 3), Qt.SolidLine, Qt.FlatCap))
            painter.drawLine(at((sx - ux, sz - uz)), at((sx + ux, sz + uz)))

    def _paint_delta(self, painter):
        """The delta bar. In move mode a sample, with a border and its name."""
        view = self.delta_view
        if not self.locked and view is None:
            view = DELTA_BAR_SAMPLE
        if view is None:
            return
        draw_delta_bar(painter, self.width(), self.height(), view.fill, view.trend, view.text, self.theme)
        if not self.locked:
            painter.setPen(QPen(QColor(*BORDER), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 4, 4)
            painter.setPen(QColor(*LABEL_COLOR))
            font = painter.font()
            font.setPixelSize(11)
            painter.setFont(font)
            painter.drawText(
                self.rect().adjusted(6, 0, -20, 0), Qt.AlignVCenter | Qt.AlignLeft, self.section.label
            )

    def _paint_bar(self, painter):
        """A plain bar filling the window (the blue flag), at its opacity; in move mode
        with a border and its name, so it can be placed while no flag is out."""
        opacity = self.opacity if self.locked else max(self.opacity or 0.0, BLUE_SAMPLE)
        if opacity is None:
            return
        alpha = round(255 * min(max(opacity, 0.0), 1.0))
        edge = BLUE_FLAG_EDGE_WIDTH
        rect = QRectF(self.rect()).adjusted(edge / 2, edge / 2, -edge / 2, -edge / 2)
        radius = min(rect.height() / 2, 4)
        # A horizontal flag: navy with a darker blue outline; in move mode the move
        # mode's light border instead, like the other sections.
        painter.setPen(
            QPen(QColor(*BORDER), 2) if not self.locked else QPen(QColor(*BLUE_FLAG_EDGE, alpha), edge)
        )
        painter.setBrush(QColor(*BLUE_FLAG, alpha))
        painter.drawRoundedRect(rect, radius, radius)
        if not self.locked:
            painter.setPen(QColor(*LABEL_COLOR))
            font = painter.font()
            font.setPixelSize(11)
            painter.setFont(font)
            painter.drawText(
                self.rect().adjusted(6, 0, -20, 0), Qt.AlignVCenter | Qt.AlignLeft, self.section.label
            )


class HudCanvas(QWidget):
    """One see-through, click-through window over a whole screen that draws every shown
    section at its place, while locked. Each section in its own window cost the game
    frames: on a Mac 120 FPS fell to 85 with 17 windows, and stayed at 115 with the same
    boxes in one window (experiments/window_count_probe.py, 2026-11-09). The sections'
    own windows stay hidden then and keep their places; in move mode they come back."""

    def __init__(self, native, place, windows):
        super().__init__(None, window_flags())
        self.native = native
        self.windows = windows  # every SectionWindow, in drawing order
        self.drawn = {}  # section name -> QRect (screen) it was last asked to be drawn in
        # One tint behind each group's tinted sections (the option, on by default; 2026-11-15).
        self.group_tint = False
        self.group_boxes = {}  # group -> its tint's QRect (screen), as last drawn
        self.setWindowTitle('TurboHUD')
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWindowFlag(Qt.WindowTransparentForInput, True)
        self.setGeometry(*place)

    def redraw(self, window):
        """Draw `window`'s section again, where it is and where it was (it may have moved). A
        group's tint is drawn again whole only where it changed (a section moved, emptied, its
        tint switched): a section's new text alone is drawn on the tint as it is."""
        now = QRect(window.x(), window.y(), window.width(), window.height())
        before = self.drawn.get(window.section.name)
        self.drawn[window.section.name] = now
        rects = [before, now]
        boxes = self._group_boxes()
        if boxes != self.group_boxes:
            changed = {g for g in {*boxes, *self.group_boxes} if boxes.get(g) != self.group_boxes.get(g)}
            rects += [self.group_boxes.get(g) for g in changed] + [boxes.get(g) for g in changed]
            self.group_boxes = boxes
        for rect in rects:
            if rect is None:
                continue
            local = rect.translated(-self.x(), -self.y()).adjusted(-2, -2, 2, 2).intersected(self.rect())
            if not local.isEmpty():
                QWidget.update(self, local)

    def _group_boxes(self):
        """{group: QRect (screen)} of one tint round each group's tinted sections; {} with the
        option off."""
        if not self.group_tint:
            return {}
        members = [(w.group, (w.x(), w.y(), w.width(), w.height())) for w in self.windows if w.tints_itself()]
        return {group: QRect(*box) for group, box in group_tint_boxes(members).items()}

    def set_group_tint(self, on):
        self.group_tint = on
        self.group_boxes = self._group_boxes()
        self.update()

    def show_on_top(self):
        self.show()
        log.info('canvas: %s', self.native.raise_window(self))

    def paintEvent(self, event):
        began = time.perf_counter()
        painter = QPainter(self)
        # Only the changed sections' own rectangles, not the one rectangle round them all
        # (event.rect()): with the lap times on one side of the screen and the player list on
        # the other, that was most of the screen, every section in it drawn again each frame
        # (the tester's stutter, 2026-11-12: drawing 20 to 24% of the time).
        area = event.region()
        painter.setCompositionMode(QPainter.CompositionMode_Clear)  # what was there goes
        for rect in area:
            painter.fillRect(rect, Qt.transparent)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        boxes = self._group_boxes()
        if boxes:
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(*BACKDROP))
            for rect in boxes.values():
                local = QRectF(rect.translated(-self.x(), -self.y()))
                if area.intersects(local.toAlignedRect()):
                    painter.drawRoundedRect(local, 6, 6)  # as a section's own (_paint_backdrop)
            painter.restore()
        for window in self.windows:
            if not window.wanted:
                continue
            place = QRect(window.x() - self.x(), window.y() - self.y(), window.width(), window.height())
            if not area.intersects(place):
                continue
            painter.save()
            painter.translate(place.topLeft())
            painter.setClipRect(QRect(0, 0, place.width(), place.height()))
            drawing = time.perf_counter()
            window.draw(painter, not (window.group in boxes and window.tints_itself()))
            window.drew(time.perf_counter() - drawing)
            painter.restore()
        painter.end()
        SectionWindow.drawing_time += time.perf_counter() - began


class HudCanvases:
    """A HudCanvas for each screen, as one: a section is drawn on every screen it reaches."""

    def __init__(self, native, screens, windows):
        self.canvases = [HudCanvas(native, screen, windows) for screen in screens]

    def redraw(self, window):
        for canvas in self.canvases:
            canvas.redraw(window)

    def set_group_tint(self, on):
        for canvas in self.canvases:
            canvas.set_group_tint(on)

    def set_shown(self, shown):
        for canvas in self.canvases:
            if shown:
                canvas.show_on_top()
            else:
                canvas.hide()


class GroupTintWindow(QWidget):
    """One group's tint while locked, behind its sections with their tint on and the room between
    them: see-through and click-through, a window of its own below them. Where a window per
    section cannot draw in the gaps between them (Windows); the Mac draws it on its HUD canvas."""

    on_canvas = False

    def __init__(self, native, group):
        super().__init__(None, window_flags())
        self.native = native
        self.setWindowTitle(f'TurboHUD - Group Tint {group}')
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWindowFlag(Qt.WindowTransparentForInput, True)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(*BACKDROP))
        painter.drawRoundedRect(QRectF(self.rect()), 6, 6)  # as a section's own (_paint_backdrop)
        painter.end()


class GroupTints:
    """One tint for each group where every section has its own window (Windows; asked for by the
    user on 2026-11-16, after one window per screen there cost the compositor three times the GPU):
    a small GroupTintWindow behind each group's tinted sections, the box round them as on the Mac
    (core.hud.group_tint_boxes), and those sections without a tint of their own. Shown only while
    locked; a tint window is moved and placed below its sections again only when its box changes,
    so a section's new text costs it nothing."""

    def __init__(self, native, windows):
        self.native = native
        self.windows = windows  # every SectionWindow
        self.on = False
        self.tints = {}  # group -> its GroupTintWindow, made the first time it is needed
        self.boxes = {}  # group -> (x, y, width, height) its tint is shown at now

    def set_on(self, on):
        self.on = on
        self.refresh()

    def refresh(self):
        """Bring the tints in line with the sections: where they are, which have their tint on and
        text to show, and whether locked. Cheap when nothing changed (each frame while locked)."""
        tinted = [w for w in self.windows if w.tints_itself()] if self.on else []
        boxes = group_tint_boxes([(w.group, tuple(w.placement())) for w in tinted])
        for window in self.windows:
            under = window in tinted and window.group in boxes
            if under != window.under_group_tint:
                window.under_group_tint = under
                window.update()
        if boxes == self.boxes:
            return
        for group, tint in self.tints.items():
            if group not in boxes:
                tint.hide()
        for group, box in boxes.items():
            tint = self.tints.get(group)
            if tint is None:
                tint = self.tints[group] = GroupTintWindow(self.native, group)
            elif self.boxes.get(group) == box and tint.isVisible():
                continue
            tint.setGeometry(*box)
            tint.show()
            # Below every shown section, as on the Mac's canvas: a section of another group over its box
            # is not shaded by it.
            shown = [w for w in self.windows if w.isVisible()]
            log.info('group %s tint at %s: %s', group, box, self.native.place_below(tint, shown))
        self.boxes = boxes

    def close(self):
        for tint in self.tints.values():
            tint.close()


class DesignFrame(QWidget):
    """The design screen's frame (move mode): the area that stands for another screen size, with
    its name above it. Clicks go through it to the sections, which are arranged inside it."""

    on_canvas = False  # never drawn on the HUD canvas: its own window, in move mode only

    def __init__(self, native):
        super().__init__(None, window_flags())
        self.native = native
        self.label = ''
        self.setWindowTitle('TurboHUD - Design Screen')
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWindowFlag(Qt.WindowTransparentForInput, True)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(LIFT_COLOR), 2, Qt.DashLine))
        painter.setBrush(QColor(255, 225, 77, 18))
        painter.drawRect(QRectF(self.rect()).adjusted(1, 1, -1, -1))
        painter.setPen(QColor(LIFT_COLOR))
        painter.drawText(QRectF(self.rect()).adjusted(8, 6, -8, -6), Qt.AlignTop | Qt.AlignRight, self.label)
        painter.end()


GRID_STEP = 20  # move mode's grid: a line every this many pixels
GRID_MAJOR = 5  # every fifth line (100 px) stronger
GRID_COLORS = {
    'minor': (255, 255, 255, 22),
    'major': (255, 255, 255, 55),
    'centre': (255, 225, 77, 110),  # the screen's middle, in the highlight colour (LIFT_COLOR)
}


def grid_lines(length, step=GRID_STEP, major=GRID_MAJOR):
    """[(position, kind)] of the grid's lines across `length` pixels, from 0: kind 'minor',
    every `major`-th one 'major', and the line through the middle 'centre' (asked for by the
    user on 2026-11-14, to line the sections up in move mode)."""
    middle = length // 2
    lines = [
        (at, 'major' if (at // step) % major == 0 else 'minor')
        for at in range(step, length, step)
        if at != middle
    ]
    return sorted(lines + [(middle, 'centre')])


class GridWindow(QWidget):
    """Move mode's grid over the main screen, beneath the sections: see-through and click-through,
    so the sections are dragged over it as before; a window of its own, never on the HUD canvas."""

    on_canvas = False

    def __init__(self, native):
        super().__init__(None, window_flags())
        self.native = native
        self.setWindowTitle('TurboHUD - Grid')  # Hyprland finds each window by its title
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWindowFlag(Qt.WindowTransparentForInput, True)

    def paintEvent(self, _event):
        painter = QPainter(self)
        width, height = self.width(), self.height()
        for kind in ('minor', 'major', 'centre'):  # the stronger lines over the fainter ones
            painter.setPen(QPen(QColor(*GRID_COLORS[kind]), 1))
            for at, line in grid_lines(width):
                if line == kind:
                    painter.drawLine(QPointF(at + 0.5, 0), QPointF(at + 0.5, height))
            for at, line in grid_lines(height):
                if line == kind:
                    painter.drawLine(QPointF(0, at + 0.5), QPointF(width, at + 0.5))
        painter.end()


class MovePanel(QWidget):
    """Shown in move mode: what to do, then per section a tick box to show it, its group,
    centring and its text options; matching a group, the presets, Undo, Lock, Settings and
    Quit. Sections in the same group move together. Options for the whole HUD are in the
    settings window, to keep this panel small."""

    lock_requested = Signal()
    quit_requested = Signal()
    settings_requested = Signal()
    wanted_changed = Signal(str, bool)  # section name, shown
    all_wanted = Signal(bool)  # every section shown (Select all) or hidden (Deselect all)
    group_changed = Signal(str, str)  # section name, group ('' for none)
    align_requested = Signal(str, bool, bool)  # section name, centre across, centre down
    preset_save_requested = Signal(int)  # the preset's number
    preset_load_requested = Signal(int)
    preset_delete_requested = Signal(int)
    preset_renamed = Signal(int, str)  # the preset's number, its name
    auto_preset_changed = Signal(str, int)  # an event mode, the preset loaded as one begins (0: none)
    match_requested = Signal(str)  # the group
    undo_requested = Signal()
    redo_requested = Signal()  # forward again after Undo (asked for by the user on 2026-11-13)
    screen_default_requested = Signal()  # the shipped layout for this screen
    export_requested = Signal()  # the layout to a file, to share
    import_requested = Signal()  # a layout from a file, fitted to this screen
    design_requested = Signal(int, int)  # the design screen for this size (width, height)
    design_save_requested = Signal()
    design_cancel_requested = Signal()
    relearn_requested = Signal()  # forget the current track's map and learn it again
    tint_changed = Signal(str, bool)  # section name, a tint behind its text
    text_centred_changed = Signal(str, bool)  # section name, its text in the middle of its box
    winner_preview_changed = Signal(bool)  # the race leader banner's 🏁: the winner's banner in move mode
    font_size_changed = Signal(str, int)  # section name, its own text size in pixels; 0: the global one
    global_font_changed = Signal(int)  # the global text size in pixels
    all_global_requested = Signal()  # every text section follows the global text size
    # A section's own font (asked for by the user on 2026-11-20): its name and the family, '' the
    # system font, None the global one.
    family_changed = Signal(str, object)
    global_family_changed = Signal(str)  # the global font: a family, '' the system's
    all_global_family_requested = Signal()  # every text section in the global font
    spacing_changed = Signal(str, int)  # section name, its line spacing in percent of the usual

    focusable = True  # it takes clicks on its tick boxes and buttons

    def __init__(
        self,
        native,
        sections,
        shortcuts,
        commands=False,
        saved_presets=(),
        lock_key='Ctrl+Shift+L',
        preset_names=None,
        auto_presets=None,
    ):
        super().__init__(None, window_flags())
        self.native = native
        self.setWindowTitle('TurboHUD - Move Mode')
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setStyleSheet('QLabel, QCheckBox { color: white; }' + self._font_cap())
        column = QVBoxLayout(self)
        column.setContentsMargins(14, 8, 14, 8)
        column.setSpacing(3)  # tight, with a row per section
        column.addWidget(QLabel('<b>TurboHUD - Move Mode</b>'))
        for line in help_lines(shortcuts, commands, lock_key):
            column.addWidget(QLabel(line))
        self.boxes = {}  # the General tab's Show ticks
        self.text_boxes = {}  # the Text tab's, always the same as the General tab's
        self.groups = {}
        self.centres = {}
        self.winner_preview = None  # the race leader banner's 🏁 switch, once its row is made
        self.tints = {}
        self.font_sizes = {}
        self.spacings = {}
        self.families = {}  # section name -> its font list
        self._fonts = ({}, '')  # the fonts offered and the global one (set_fonts)
        # Two tabs with the same rows of sections (asked for by the user on 2026-11-20): General, with
        # where each goes and how it looks, and Text, with its text size, line spacing and font. The
        # rows of each scroll where the screen is too short for them all (fit_height).
        general = self._rows_grid(
            (
                (1, 1, 'Group', 'Sections in the same group move together'),
                (2, 2, 'Centre', 'Centre the section across (↔) or down (↕) the screen'),
                (
                    4,
                    1,
                    'Tint',
                    'A light tint behind the text while locked; on the track map, its dark square',
                ),
            ),
            sections,
            self._section_row,
            self.boxes,
        )
        text = self._rows_grid(
            (
                (1, 1, 'Mid text', 'Put the text in the middle of the box, not at its left'),
                (
                    2,
                    1,
                    'Size px',
                    'Its text size in pixels, or the global one; flags, tire rings and bars go with it',
                ),
                (3, 1, 'Lines %', 'The room between its rows, in percent of the usual'),
                (4, 1, 'Font', 'Its own font, or the global one (Global font, below)'),
            ),
            sections,
            self._text_row,
            self.text_boxes,
        )
        self.rows, self.rows_area = self._scrolling(general)
        self.text_rows, self.text_area = self._scrolling(text)
        self.tabs = QTabWidget()
        self.tabs.tabBar().setDrawBase(False)  # the style's own line: the pane's (below) instead
        self.tabs.addTab(self.rows_area, 'General')
        self.tabs.addTab(self.text_area, 'Text')
        self.tabs.setTabToolTip(0, 'Show, group, centre and tint each section')
        self.tabs.setTabToolTip(1, 'Where the text sits, its size, line spacing and font, for each section')
        # Tabs that read as tabs, apart from the help text above them (reported by the user on
        # 2026-11-20: plain words, they were easy to miss): bold, boxed, the open one filled, on a line
        # that joins it to its rows.
        edge = f'rgb{BORDER}'
        self.tabs.setStyleSheet(
            f'QTabWidget::pane {{ border: none; border-top: {PANEL_TAB_LINE}px solid {edge};'
            f' background: transparent; padding-top: {PANEL_TAB_GAP}px; }}'
            f' QTabBar::tab {{ color: {PANEL_HEADING}; background: rgba(120, 170, 230, 35);'
            f' border: 1px solid {edge}; border-bottom: none; border-top-left-radius: 5px;'
            ' border-top-right-radius: 5px; padding: 5px 22px; margin-right: 4px; font-weight: bold; }'
            f' QTabBar::tab:selected {{ color: {PANEL_TAB_TEXT}; background: {edge}; }}'
            ' QTabBar::tab:!selected:hover { color: white; background: rgba(120, 170, 230, 80); }'
        )
        column.addSpacing(PANEL_TABS_ROOM)
        column.addWidget(self.tabs)
        self._finish(column, sections)
        self.fit_height(None)
        # The presets, layout files and the design screen: a window of their own (asked for by the
        # user on 2026-11-15), its signals passed on as the panel's.
        self.layouts = LayoutsWindow(
            native, window_flags(), shortcuts, saved_presets, preset_names, auto_presets
        )
        for name in (
            'preset_save_requested',
            'preset_load_requested',
            'preset_delete_requested',
            'preset_renamed',
            'auto_preset_changed',
            'screen_default_requested',
            'export_requested',
            'import_requested',
            'design_requested',
            'design_save_requested',
            'design_cancel_requested',
        ):
            getattr(self.layouts, name).connect(getattr(self, name))

    def _font_cap(self):
        """A style rule holding the text at PANEL_FONT_PX where the system's is larger, so the
        panel is the same on Linux as on the Mac. In the style sheet, as Linux gives buttons and
        lists their own font, which a font set on the panel does not reach."""
        if QFontInfo(self.font()).pixelSize() > PANEL_FONT_PX:
            return f' * {{ font-size: {PANEL_FONT_PX}px; }}'
        return ''

    @staticmethod
    def _heading(text, tip):
        label = QLabel(f'<small><b>{text}</b></small>')
        label.setStyleSheet(f'color: {PANEL_HEADING};')
        if tip:
            label.setToolTip(tip)
        return label

    @staticmethod
    def _empty():
        """A faint dot where a section has no such option."""
        dot = QLabel('·')
        dot.setStyleSheet(f'color: {PANEL_EMPTY};')
        dot.setToolTip('Not for this section')
        return dot

    def _set_all(self, wanted):
        """Select all / Deselect all: every tick box in both tabs, and one request for the lot."""
        for box in (*self.boxes.values(), *self.text_boxes.values()):
            box.blockSignals(True)
            box.setChecked(wanted)
            box.blockSignals(False)
        self.all_wanted.emit(wanted)

    def _rows_grid(self, headings, sections, make_row, boxes):
        """A tab's grid: Show with All and None, then `headings` ((column, span, text, tip), ...)
        over their columns, then a row per section under its kind (`make_row(grid, row,
        section)`), each starting with its Show tick, kept in `boxes`."""
        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(0)
        grid.setContentsMargins(0, 0, 0, 0)  # in its own widget (_scrolling): no extra room round it
        show = QHBoxLayout()
        show.setSpacing(4)
        show.addWidget(self._heading('Show', 'Tick to show the section'))
        for text, wanted, tip in (
            ('All', True, 'Show every section (one step for Undo)'),
            ('None', False, 'Hide every section (one step for Undo)'),
        ):
            button = QPushButton(text)
            button.setMinimumWidth(PANEL_WORD_BUTTON)
            button.setToolTip(tip)
            button.clicked.connect(lambda _checked=False, w=wanted: self._set_all(w))
            show.addWidget(button)
        show.addStretch()
        grid.addLayout(show, 0, 0)
        last = max(column_ + span for column_, span, _text, _tip in headings)
        for column_, span, text, tip in headings:
            grid.addWidget(self._heading(text, tip), 0, column_, 1, span, Qt.AlignHCenter | Qt.AlignBottom)
        row = 0
        for heading, listed in panel_categories(sections):
            if heading:
                row += 1
                label = self._heading(heading.upper(), '')
                label.setContentsMargins(0, 3, 0, 0)
                grid.addWidget(label, row, 0, 1, last)
            for section in listed:
                row += 1
                grid.addWidget(self._show_box(section, boxes), row, 0)
                make_row(grid, row, section)
        grid.setColumnStretch(last, 1)
        return grid

    @staticmethod
    def _scrolling(grid):
        """(the rows, the area they scroll in) for a tab's `grid`."""
        rows = QWidget()
        rows.setLayout(grid)
        area = QScrollArea()
        area.setWidget(rows)
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        area.setStyleSheet('QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }')
        area.viewport().setAutoFillBackground(False)
        return rows, area

    def _show_box(self, section, boxes):
        """A section's Show tick in one tab, in `boxes`; ticked or not, the other tab's follows."""
        box = QCheckBox(section.label)
        box.setToolTip(section.tip or f'Show {section.label.lower()}')
        box.toggled.connect(lambda checked, name=section.name: self._shown(name, checked))
        boxes[section.name] = box
        return box

    def _shown(self, name, checked):
        """A Show tick changed in one tab: the other tab's the same, and one request."""
        for boxes in (self.boxes, self.text_boxes):
            box = boxes.get(name)
            if box is not None and box.isChecked() != checked:
                box.blockSignals(True)
                box.setChecked(checked)
                box.blockSignals(False)
        self.wanted_changed.emit(name, checked)

    def _section_row(self, grid, row, section):
        """The General tab's columns for `section`: its group, centring and tint."""
        group = QComboBox()
        group.addItems(['-', *GROUPS])
        group.setToolTip('Sections in the same group move together')
        group.setFixedWidth(PANEL_COMBO_WIDTH)
        group.currentTextChanged.connect(
            lambda text, name=section.name: self.group_changed.emit(name, '' if text == '-' else text)
        )
        group.currentTextChanged.connect(lambda _text: self._update_matches())
        grid.addWidget(group, row, 1)
        self.groups[section.name] = group
        for column_, (text, tip, across, down) in enumerate(
            (
                ('↔', 'Centre across the screen', True, False),
                ('↕', 'Centre down the screen', False, True),
            ),
            start=2,
        ):
            button = QPushButton(text)
            button.setToolTip(tip)
            button.setFixedWidth(PANEL_SMALL_BUTTON)
            button.clicked.connect(
                lambda _checked=False, name=section.name, a=across, d=down: self.align_requested.emit(
                    name, a, d
                )
            )
            grid.addWidget(button, row, column_)
        if has_tint(section):
            tint = QCheckBox()
            tint.setToolTip(
                'The dark square behind the track map'
                if section.drawing
                else 'A light tint behind the text of this section while locked'
            )
            tint.toggled.connect(lambda checked, name=section.name: self.tint_changed.emit(name, checked))
            grid.addWidget(tint, row, 4, Qt.AlignHCenter)
            self.tints[section.name] = tint
        else:
            grid.addWidget(self._empty(), row, 4, Qt.AlignHCenter)

    def _text_row(self, grid, row, section):
        """The Text tab's columns for `section`: its text in the middle, size, line spacing, font."""
        if text_can_centre(section):
            centre = QCheckBox()
            centre.setToolTip('Put the text in the middle of the box, not at its left')
            centre.toggled.connect(
                lambda checked, name=section.name: self.text_centred_changed.emit(name, checked)
            )
            grid.addWidget(centre, row, 1, Qt.AlignHCenter)
            self.centres[section.name] = centre
        elif section.banner and section.end:
            # Its text is always in the middle, so this column has the switch between a new leader's
            # banner and the winner's, to see both in move mode (asked for by the user on 2026-11-17).
            winner = QPushButton('🏁')
            winner.setCheckable(True)
            winner.setFixedWidth(PANEL_SMALL_BUTTON)
            winner.setToolTip("Show the race winner's banner here instead of a new leader's")
            winner.toggled.connect(self.winner_preview_changed)
            grid.addWidget(winner, row, 1, Qt.AlignHCenter)
            self.winner_preview = winner
        else:
            grid.addWidget(self._empty(), row, 1, Qt.AlignHCenter)
        if is_text_section(section):
            size = self._size_box(f'The text size of {section.label.lower()}: its own, or the global one')
            size.setMinimum(FONT_SIZES[0] - 1)
            size.setSpecialValueText('global')  # the lowest step: it follows the global size
            size.valueChanged.connect(
                lambda px, name=section.name: self.font_size_changed.emit(
                    name, 0 if px < FONT_SIZES[0] else px
                )
            )
            grid.addWidget(size, row, 2)
            self.font_sizes[section.name] = size
        else:
            grid.addWidget(self._empty(), row, 2, Qt.AlignHCenter)
        if is_text_section(section) and len(section.samples[0]) > 1:
            lines = QSpinBox()
            low, high, step = SPACINGS
            lines.setRange(round(low * 100), round(high * 100))
            lines.setSingleStep(round(step * 100))
            lines.setValue(100)
            lines.setKeyboardTracking(False)
            lines.setFixedWidth(PANEL_LINES_WIDTH)
            lines.setToolTip(f'The room between the rows of {section.label.lower()}, in percent of the usual')
            lines.valueChanged.connect(lambda pct, name=section.name: self.spacing_changed.emit(name, pct))
            grid.addWidget(lines, row, 3)
            self.spacings[section.name] = lines
        else:
            grid.addWidget(self._empty(), row, 3, Qt.AlignHCenter)
        if is_text_section(section):
            family = QComboBox()
            family.setFixedWidth(PANEL_FONT_WIDTH)
            family.view().setMinimumWidth(PANEL_FONT_OPEN)
            family.setToolTip(f'The font of {section.label.lower()}: its own, or the global one')
            fill_fonts(family, {}, None, True)
            family.currentIndexChanged.connect(
                lambda index, name=section.name, box=family: self.family_changed.emit(
                    name, family_of(box.itemData(index))
                )
            )
            grid.addWidget(family, row, 4)
            self.families[section.name] = family
        else:
            grid.addWidget(self._empty(), row, 4, Qt.AlignHCenter)

    @staticmethod
    def _size_box(tip):
        """A text size in pixels (FONT_SIZES)."""
        box = QSpinBox()
        box.setRange(*FONT_SIZES)
        box.setKeyboardTracking(False)  # the size typed, not each digit on the way
        box.setToolTip(tip)
        return box

    def _finish(self, column, sections):
        """Below the sections: matching a group, the global text size, and the buttons."""
        self.text_sections = [section.name for section in sections if not section.drawing]
        self.matches = {}
        matches = QHBoxLayout()
        matches.addWidget(QLabel('Same text size and width, group:'))
        for name in GROUPS:
            match = QPushButton(name)
            match.setFixedWidth(PANEL_SMALL_BUTTON)
            match.setToolTip(
                f'Give the text sections in group {name} the largest text size among them and one '
                'width. Save a preset first to be able to go back.'
            )
            match.clicked.connect(lambda _checked=False, group=name: self.match_requested.emit(group))
            matches.addWidget(match)
            self.matches[name] = match
        matches.addStretch()
        column.addLayout(matches)
        self._update_matches()
        every = QHBoxLayout()
        every.addWidget(QLabel('Global text size (px):'))
        self.global_size = self._size_box('The text size of every section set to global')
        self.global_size.valueChanged.connect(self.global_font_changed)
        every.addWidget(self.global_size)
        follow = QPushButton('All global')
        follow.setToolTip('Every text section follows the global text size (one step for Undo)')
        follow.clicked.connect(self.all_global_requested)
        every.addWidget(follow)
        every.addStretch()
        column.addLayout(every)
        # The global font, as in the settings window (Look > Font): every section on global is in it.
        typeface = QHBoxLayout()
        typeface.addWidget(QLabel('Global font:'))
        self.global_family = QComboBox()
        self.global_family.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.global_family.setToolTip(
            'The font of every section set to global, as Settings > Look > Font; a preset keeps it'
        )
        fill_fonts(self.global_family, {}, '')
        self.global_family.currentIndexChanged.connect(
            lambda index: self.global_family_changed.emit(self.global_family.itemData(index))
        )
        typeface.addWidget(self.global_family)
        every_font = QPushButton('All global')
        every_font.setToolTip('Every text section in the global font (one step for Undo)')
        every_font.clicked.connect(self.all_global_family_requested)
        typeface.addWidget(every_font)
        typeface.addStretch()
        column.addLayout(typeface)
        row = QHBoxLayout()
        self.undo = QPushButton('Undo')
        self.undo.setToolTip('Go back one change to the layout, as often as there are changes')
        self.undo.setEnabled(False)
        self.undo.clicked.connect(self.undo_requested)
        row.addWidget(self.undo)
        self.redo = QPushButton('Redo')
        self.redo.setToolTip('Go forward again to the change Undo went back from')
        self.redo.setEnabled(False)
        self.redo.clicked.connect(self.redo_requested)
        row.addWidget(self.redo)
        self.relearn = None  # only with a track map
        if any(section.drawing == 'map' for section in sections):
            self.relearn = QPushButton('Relearn map')
            self.relearn.setToolTip(
                'Forget the map of the track being raced (also the saved one);\n'
                'the next clean lap any car drives draws it again'
            )
            self.relearn.setEnabled(False)
            self.relearn.clicked.connect(self.relearn_requested)
            row.addWidget(self.relearn)
        layouts = QPushButton('Layouts…')
        layouts.setToolTip(
            'The presets and their names, which loads for each kind of event, layout files, Design'
        )
        layouts.clicked.connect(self.open_layouts)
        row.addWidget(layouts)
        # The preset in use (asked for by the user on 2026-11-19): set_current_preset.
        self.current_preset = QLabel('Preset: none')
        # In the presets' electric blue and bold, to stand out (asked for by the user on 2026-11-19).
        self.current_preset.setStyleSheet(f'color: {STATUS_COLOUR}; font-weight: bold;')
        self.current_preset.setToolTip(
            'The preset the layout is in now; (changed): moved on from the one loaded or saved last'
        )
        lock = QPushButton('Lock')
        settings = QPushButton('Settings…')
        settings.setToolTip('Colours, sizes, warning times and the options for the whole HUD')
        quit_ = QPushButton('Quit TurboHUD')
        lock.clicked.connect(self.lock_requested)
        settings.clicked.connect(self.settings_requested)
        quit_.clicked.connect(self.quit_requested)
        row.addWidget(lock)
        row.addWidget(settings)
        row.addWidget(quit_)
        row.addStretch()
        column.addWidget(self.current_preset)  # a line of its own: a long name would widen the row
        column.addLayout(row)

    def fit_height(self, available):
        """Make the panel at most `available` px tall (a screen's usable height; None: no limit),
        with room to spare: the rows of sections scroll where they do not all fit, the rest of
        the panel (help, presets, Lock, Quit) always shown."""
        # Both tabs as tall and as wide as the larger: switching tabs moves nothing below them.
        areas = ((self.rows, self.rows_area), (self.text_rows, self.text_area))
        full = max(rows.sizeHint().height() for rows, _area in areas)
        # The tab bar, and the line below it with its room (the pane's style): the rows come after them.
        tab_bar = self.tabs.tabBar().sizeHint().height() + PANEL_TAB_LINE + PANEL_TAB_GAP
        for _rows, area in areas:
            area.setFixedHeight(full)
        self.tabs.setFixedHeight(full + tab_bar)  # the tabs follow their rows only when told
        rest = self.layout().sizeHint().height() - full
        room = full if available is None else available - 2 * PANEL_SCREEN_ROOM - rest
        shown = max(min(full, PANEL_LEAST_ROWS), min(full, room))
        scrolls = shown < full
        # The style's width: macOS gives its overlay scroll bar's hint as 0, and it then covered the
        # last column.
        bar = self.rows_area.style().pixelMetric(QStyle.PM_ScrollBarExtent) + 4 if scrolls else 0
        wide = max(rows.sizeHint().width() for rows, _area in areas) + bar
        for _rows, area in areas:
            area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn if scrolls else Qt.ScrollBarAlwaysOff)
            area.setFixedSize(wide, shown)
        self.tabs.setFixedSize(wide, shown + tab_bar)
        self.adjustSize()
        self.resize(self.sizeHint())

    def rows_scroll(self):
        """Whether the rows of sections scroll (the screen is too short for them all)."""
        return self.rows_area.verticalScrollBarPolicy() == Qt.ScrollBarAlwaysOn

    def set_wanted(self, name, wanted):
        """Show whether a section shows, in both tabs, saying nothing back."""
        for boxes in (self.boxes, self.text_boxes):
            box = boxes.get(name)
            if box is not None and box.isChecked() != wanted:
                box.blockSignals(True)
                box.setChecked(wanted)
                box.blockSignals(False)

    def set_group(self, name, group):
        combo = self.groups.get(name)
        text = group or '-'
        if combo is not None and combo.currentText() != text:
            combo.blockSignals(True)
            combo.setCurrentText(text)
            combo.blockSignals(False)
            self._update_matches()

    def _update_matches(self):
        """A group's button works from two text sections in it."""
        for group, button in self.matches.items():
            members = [name for name in self.text_sections if self.groups[name].currentText() == group]
            button.setEnabled(len(members) >= 2)

    def set_tint(self, name, tint):
        box = self.tints.get(name)
        if box is not None and box.isChecked() != tint:
            box.blockSignals(True)
            box.setChecked(tint)
            box.blockSignals(False)

    def set_text_centred(self, name, centred):
        box = self.centres.get(name)
        if box is not None and box.isChecked() != centred:
            box.blockSignals(True)
            box.setChecked(centred)
            box.blockSignals(False)

    def set_font_size(self, name, font):
        """Show a section's own text size (None: global), saying nothing back."""
        box = self.font_sizes.get(name)
        value = FONT_SIZES[0] - 1 if font is None else font
        if box is not None and box.value() != value:
            box.blockSignals(True)
            box.setValue(value)
            box.blockSignals(False)

    def set_spacing(self, name, spacing):
        """Show a section's line spacing (a share of the usual), saying nothing back."""
        box = self.spacings.get(name)
        if box is not None and box.value() != round(spacing * 100):
            box.blockSignals(True)
            box.setValue(round(spacing * 100))
            box.blockSignals(False)

    def set_global_font(self, font):
        """Show the global text size, saying nothing back."""
        if self.global_size.value() != font:
            self.global_size.blockSignals(True)
            self.global_size.setValue(font)
            self.global_size.blockSignals(False)

    def set_fonts(self, families, chosen):
        """Offer `families` ({family: file name}) in every font list, `chosen` the global font ('' the
        system's), saying nothing back; each section keeps the font it shows."""
        self._fonts = (dict(families), chosen)
        fill_fonts(self.global_family, families, chosen)
        for box in self.families.values():
            fill_fonts(box, families, family_of(box.currentData()), True)

    def set_family(self, name, family):
        """Show a section's own font (None: the global one), saying nothing back."""
        box = self.families.get(name)
        if box is not None and family_of(box.currentData()) != family:
            fill_fonts(box, self._fonts[0], family, True)

    def set_global_family(self, family):
        """Show the global font, saying nothing back."""
        if self.global_family.currentData() != family:
            self._fonts = (self._fonts[0], family)
            fill_fonts(self.global_family, self._fonts[0], family)

    def set_presets_saved(self, numbers):
        self.layouts.set_presets_saved(numbers)

    def show_preset_status(self, text):
        """What was just done to a preset, below the presets in the layouts window."""
        self.layouts.show_status(text)

    def open_layouts(self):
        """The layouts window beside the panel, wholly on its screen; shown again where it was
        hidden behind something."""
        anchor = self.frameGeometry().getRect()
        screen = self.screen().availableGeometry().getRect() if self.screen() is not None else anchor
        size = (self.layouts.width(), self.layouts.height())
        if self.layouts.isVisible():
            self.native.raise_window(self.layouts)
        else:
            self.layouts.show_at(*beside(size, anchor, screen))

    def set_current_preset(self, text):
        """Show which preset is in use (settings.preset_shown)."""
        self.current_preset.setText(text)

    def set_undo_available(self, available):
        self.undo.setEnabled(available)

    def set_redo_available(self, available):
        self.redo.setEnabled(available)

    def set_designing(self, designing):
        self.layouts.set_designing(designing)

    def set_own_screen(self, size):
        self.layouts.set_own_screen(size)

    def set_relearn_available(self, available):
        """Relearn map works only while a track is known (in a race)."""
        if self.relearn is not None:
            self.relearn.setEnabled(available)

    def mousePressEvent(self, event):
        # Dragged by its background, out of the way of a section if need be.
        if event.button() == Qt.LeftButton and self.windowHandle() is not None:
            self.windowHandle().startSystemMove()

    def show_at(self, x, y):
        self.move(x, y)
        self.show()
        log.info('panel: %s', self.native.raise_window(self))

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(*BORDER), 2))
        painter.setBrush(QColor(15, 30, 55, 225))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 10, 10)
        painter.end()

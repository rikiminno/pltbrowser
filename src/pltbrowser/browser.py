"""Single-window browser for nested mappings of Matplotlib figures."""

import threading

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.backend_bases import FigureCanvasBase
from matplotlib.backends.backend_qtagg import (
    FigureCanvasQTAgg, NavigationToolbar2QT,
)
from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets
from matplotlib.colors import to_hex, to_rgb
from matplotlib.figure import Figure

from .figures import walk_figures
from .flow import FlowLayout, find_tiles


# colors of the light window theme, besides the accent
TEXT = "#374151"
BACKGROUND = "#F7F8FA"

# height of a row of the figure tree, in pixels
ROW_HEIGHT = 28

# tree-item data role that holds the index of the item's figure
_FIGURE = QtCore.Qt.ItemDataRole.UserRole.value


class FigureBrowser:
    """Browse a nested mapping of Matplotlib figures in one Qt window.

    A tree on the left mirrors the nesting of the mapping; the selected
    figure is displayed on the right. The figures leave their pyplot
    windows when the browser is created, and get their size, resolution,
    and subplot grid back when the browser is closed.

    Parameters
    ----------
    figures : mapping
        Maps names to Matplotlib figures or to nested mappings of them.
    title : str, optional
        Title of the window and heading of the figure tree.
    accent : color, optional
        Any Matplotlib color, used for the heading and the selection.
    label : callable, optional
        Returns the text displayed in the tree for a name of the mapping.
    size : tuple of int, optional
        Initial width and height of the window, in pixels.
    interactive : bool, optional
        Whether figures have the Matplotlib toolbar and respond to the
        mouse and the keyboard.
    flow_layout : bool, optional
        Whether subplot grids are rearranged to fit the window, like
        MATLAB's ``tiledlayout('flow')``. Grids with shared axes,
        spanning subplots, or freely placed axes are left as they are.

    Attributes
    ----------
    window : QMainWindow
        Qt window of the browser.
    selected : matplotlib.figure.Figure
        Figure on display.
    """

    def __init__(
        self, figures, title="Figures", accent="tab:blue", label=str,
        size=(1380, 840), interactive=True, flow_layout=False,
    ):
        leaves = list(walk_figures(figures))
        if not leaves:
            raise ValueError("The figure browser needs at least one figure.")
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError(
                "The figure browser must be created on the main thread, "
                "where Qt windows live."
            )
        self.figures = figures
        self.interactive = bool(interactive)
        self.flow_layout = bool(flow_layout)
        self.selected = None
        self._label = label
        self._figures = []
        self._first = None
        self._pages = {}

        # the pyplot windows of the figures would open next to the browser
        for _, figure in leaves:
            plt.close(figure)

        # an empty canvas lets Matplotlib create and set up the Qt
        # application, which must exist before any widget
        FigureCanvasQTAgg(Figure())

        self._build_window(title, accent, size)
        self._add_items(figures, self._tree)
        for index in range(self._tree.topLevelItemCount()):
            self._tree.topLevelItem(index).setExpanded(True)
        self._tree.setCurrentItem(self._first)

    def show(self, block=None):
        """Display the browser.

        Parameters
        ----------
        block : bool, optional
            Whether to wait until the window is closed. By default, as
            in Matplotlib: wait unless interactive mode is on.
        """

        # closing the window released the figures: display one again
        self._display(self.selected)
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

        if block is None:
            block = not matplotlib.is_interactive()
        if block:
            # a local event loop returns when this window closes, even
            # if other Qt windows stay open
            loop = QtCore.QEventLoop()
            self.window.closed.connect(loop.quit)
            loop.exec()

    def close(self):
        """Close the browser window."""

        self.window.close()

    def _build_window(self, title, accent, size):
        """Create the window: the figure tree on the left, the path and
        the canvas of the selected figure on the right."""

        self.window = _Window()
        self.window.setWindowTitle(title)
        self.window.resize(*size)
        self.window.closed.connect(self._release)

        # every widget inherits the light palette, whatever the system
        # theme; a style sheet here would stop that inheritance
        central = QtWidgets.QWidget()
        central.setPalette(_palette(accent))
        central.setAutoFillBackground(True)
        self.window.setCentralWidget(central)

        # left: heading and figure tree; a label with a style sheet does
        # not inherit the palette, so its color is always given
        heading = QtWidgets.QLabel(title)
        heading.setStyleSheet(
            f"color: {to_hex(accent)}; font-size: 14pt; font-weight: bold;"
        )
        self._tree = QtWidgets.QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setAnimated(True)
        self._tree.currentItemChanged.connect(self._select)
        navigation = QtWidgets.QWidget()
        navigation.setMinimumWidth(200)
        column = QtWidgets.QVBoxLayout(navigation)
        column.addWidget(heading)
        column.addWidget(self._tree, 1)

        # right: path of the selected figure and one page per figure
        self._breadcrumb = QtWidgets.QLabel()
        self._breadcrumb.setStyleSheet(
            f"color: {TEXT}; font-size: 10pt; font-weight: bold;"
        )
        self._breadcrumb.setWordWrap(True)
        self._stack = QtWidgets.QStackedWidget()
        content = QtWidgets.QWidget()
        column = QtWidgets.QVBoxLayout(content)
        column.addWidget(self._breadcrumb)
        column.addWidget(self._stack, 1)

        splitter = QtWidgets.QSplitter()
        splitter.addWidget(navigation)
        splitter.addWidget(content)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([285, size[0] - 285])
        QtWidgets.QHBoxLayout(central).addWidget(splitter)

    def _add_items(self, figures, parent):
        """Mirror one level of the figure mapping below ``parent``."""

        for name, value in figures.items():
            text = str(self._label(name))
            item = QtWidgets.QTreeWidgetItem(parent, [text])
            item.setToolTip(0, _path(item))
            item.setSizeHint(0, QtCore.QSize(0, ROW_HEIGHT))
            if isinstance(value, Figure):
                item.setData(0, _FIGURE, len(self._figures))
                self._figures.append(value)
                if self._first is None:
                    self._first = item
            else:
                font = item.font(0)
                font.setBold(True)
                item.setFont(0, font)
                self._add_items(value, item)

    def _select(self, item, previous=None):
        """Display the figure of a tree item; a group only unfolds."""

        if item is None:
            return
        index = item.data(0, _FIGURE)
        if index is None:
            item.setExpanded(True)
            return
        self._breadcrumb.setText(_path(item))
        self._display(self._figures[index])

    def _display(self, figure):
        """Bring the page of a figure to the front, creating it on the
        first visit so that hidden figures cost nothing."""

        page = self._pages.get(figure)
        if page is None:
            page = _Page(figure, self.interactive, self.flow_layout)
            self._pages[figure] = page
            self._stack.addWidget(page)
        self._stack.setCurrentWidget(page)
        self.selected = figure

        # show what changed while the figure was hidden
        page.canvas.draw_idle()
        if self.interactive:
            page.canvas.setFocus()

    def _release(self):
        """Give every displayed figure back as it was."""

        for page in self._pages.values():
            page.release()
            self._stack.removeWidget(page)
            page.deleteLater()
        self._pages.clear()


class _Window(QtWidgets.QMainWindow):
    """Main window that tells when it is closed."""

    closed = QtCore.Signal()

    def closeEvent(self, event):
        super().closeEvent(event)
        self.closed.emit()


class _Page(QtWidgets.QWidget):
    """Canvas and toolbar of one figure on display."""

    def __init__(self, figure, interactive, flow_layout):
        super().__init__()
        self.figure = figure
        # what the Qt canvas changes in the figure, for release()
        self._dpi = figure.dpi
        self._size = figure.get_size_inches()
        self._flow = None

        self.canvas = FigureCanvasQTAgg(figure)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        if interactive:
            layout.addWidget(NavigationToolbar2QT(self.canvas, self))
        else:
            # ignore the mouse and the keyboard without looking disabled
            attributes = QtCore.Qt.WidgetAttribute
            self.canvas.setAttribute(
                attributes.WA_TransparentForMouseEvents
            )
            self.canvas.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)

        rows = _table_rows(figure)
        if rows:
            # a table keeps a readable row height and scrolls
            self.canvas.setMinimumHeight(max(500, 28 * rows + 100))
            area = QtWidgets.QScrollArea()
            area.setWidgetResizable(True)
            area.setWidget(self.canvas)
            layout.addWidget(area, 1)
        else:
            layout.addWidget(self.canvas, 1)
            tiles = find_tiles(figure) if flow_layout else None
            if tiles:
                self._flow = FlowLayout(figure, tiles)

    def release(self):
        """Give the figure back as it was before it was displayed."""

        if self._flow is not None:
            self._flow.restore()
        self.figure.dpi = self._dpi
        self.figure.set_size_inches(self._size, forward=False)
        # a plain canvas detaches the figure from the Qt widget
        FigureCanvasBase(self.figure)


def _path(item):
    """Return the labels from the top of the tree down to ``item``."""

    labels = []
    while item is not None:
        labels.insert(0, item.text(0))
        item = item.parent()
    return " / ".join(labels)


def _table_rows(figure):
    """Return the row count of the longest table of a figure."""

    return max(
        (
            1 + max(row for row, _ in table.get_celld())
            for axis in figure.axes for table in axis.tables
            if table.get_celld()
        ),
        default=0,
    )


def _palette(accent):
    """Return the light palette of the browser for an accent color."""

    roles = QtGui.QPalette.ColorRole
    palette = QtGui.QPalette(QtGui.QColor(BACKGROUND))
    for role in (
        roles.WindowText, roles.Text, roles.ButtonText,
        roles.HighlightedText,
    ):
        palette.setColor(role, QtGui.QColor(TEXT))
    # the selection is a light tint of the accent, under dark text
    tint = (1.0 - 0.18 * (1.0 - value) for value in to_rgb(accent))
    palette.setColor(roles.Highlight, QtGui.QColor.fromRgbF(*tint))
    return palette

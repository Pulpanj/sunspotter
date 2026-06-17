# %%-----------------------------------------------------------------------------
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPixmap, QWheelEvent, QMouseEvent
from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
import os
import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QLabel, QFileDialog
)
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import QRectF
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QSplitter, QLabel, QTextEdit
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QComboBox
)
import matplotlib.pyplot as plt

import numpy as np
from astropy.io import fits
import cv2
# from PIL import Image
# import PIL.Image

# %%-----------------------------------------------------------------------------


def extract_rgb_channels(rgb):
    r = rgb[:, :, 0]
    g = rgb[:, :, 1]
    b = rgb[:, :, 2]
    return r, g, b


def load_png_rgb16(filename):

    def header_dict_to_string(header: dict) -> str:
        lines = []
        for key, value in header.items():
            base = f"{key:10} = {value!r:20}"
            line = f"{base:<45}"    # type:{type(value).__name__}"
            lines.append(line)
        return "\n".join(lines)

    def get_image_attributes_cv2(img, filename):

        if img is None:
            raise ValueError(f"Cannot load image: {filename}")

        # Dimensions
        height, width = img.shape[:2]

        # Channels
        if img.ndim == 2:
            channels = 1
        else:
            channels = img.shape[2]

        # Bits per channel
        bits_per_channel = img.dtype.itemsize * 8

        # Bits per pixel
        bits_per_pixel = bits_per_channel * channels

        # Color type
        color_type = "Gray" if channels == 1 else "RGB"

        return {
            "File": filename,
            "Format": "PNG",
            "Mode": "RGB" if channels == 3 else "L",
            "Channels": channels,
            "Width": width,
            "Height": height,
            "ColorType": color_type,
            "BitsPerChannel": bits_per_channel,
            "BitsPerPixel": bits_per_pixel,
            "dtype": str(img.dtype),
            "shape": img.shape,
        }

    # Load image exactly as stored (8/16-bit, grayscale/RGB)
    img = cv2.imread(filename, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError("Cannot read PNG")
    if img.ndim == 3:
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    header = get_image_attributes_cv2(img, filename)
    # header = header_dict_to_string(info)

    # Ensure uint16
    if img.dtype == np.uint8:
        rgb = rgb.astype(np.uint16) * 256  # 0–255 → 0–65535

    r, g, b = extract_rgb_channels(rgb)
    return rgb, r, g, b, header


# filename_png = r"D:\ajps\astro\sunspotter\data\example_data\m31\stacked-16_M 31_15s60_Astro_20250126-200204018.png"

# img16, r, g, b, header = load_png_rgb16(filename_png)

# r.base
# %%-----------------------------------------------------------------------------

def extract_rgb_from_grbg(raw_data):
    # raw_data má shape=(2180, 3856), dtype=uint16

    # 1. Červený kanál (R) - nachází se na sudých řádcích a lichých sloupcích
    red_channel = raw_data[0::2, 1::2]

    # 2. Modrý kanál (B) - nachází se na lichých řádcích a sudých sloupcích
    blue_channel = raw_data[1::2, 0::2]

    # 3. Zelený kanál (G) - senzor má dva zelené pixely v bloku 2x2
    # G1: sudé řádky, sudé sloupce
    green1 = raw_data[0::2, 0::2]
    # G2: liché řádky, liché sloupce
    green2 = raw_data[1::2, 1::2]

    # Pro získání finálního zeleného kanálu obě matice zprůměrujeme
    # Převod na float zamezí přetečení (overflow) při sčítání uint16
    green_channel = ((green1.astype(np.float32) +
                     green2.astype(np.float32)) / 2.0).astype(np.uint16)

    return red_channel, green1, green2, blue_channel


def combine_bayer_to_rgb(R, G1, G2, B):
    H, W = R.shape
    rgb = np.zeros((H*2, W*2, 3), dtype=R.dtype)

    # R channel
    rgb[0::2, 0::2, 0] = R
    # G channel (G1)
    rgb[0::2, 1::2, 1] = G1
    # G channel (G2)
    rgb[1::2, 0::2, 1] = G2
    # B channel
    rgb[1::2, 1::2, 2] = B

    return rgb
# %%-----------------------------------------------------------------------------


def load_fits(fits_file):
    with fits.open(fits_file) as hdul:
        raw = hdul[0].data
        header = hdul[0].header
    return raw, header

# %%-----------------------------------------------------------------------------


def load_fits_raw(fits_file):
    raw, header = load_fits(fits_file)
    R, G1, G2, B = extract_rgb_from_grbg(raw)
    rgb = combine_bayer_to_rgb(R, G1, G2, B)
    rgb = rgb
    r, g, b = extract_rgb_channels(rgb)
    # !!!
    return rgb, r, g, b, header


# fits_raw_file = r"D:\ajps\astro\sunspotter\data\example_data\m31\M 31_15s60_Astro_20250126-203118151_17C.fits"
# # raw, header = load_fits(fits_raw_file)
# rgb16, r, g, b, header = load_fits_raw(fits_raw_file)


def header_to_string(fits_file, header):
    def header_dict_to_string(header: dict) -> str:
        lines = []
        for key, value in header.items():
            lines.append(f"{key}: {value}")
        return "\n".join(lines)

    lines = []
    if isinstance(header, dict):
        return header_dict_to_string(header)
    else:
        lines.append("=== FITS INFO ===")
        lines.append(f"File: {fits_file}")
        lines.append("=" * 60)

        for key, value, comment in header.cards:
            line = f"{(f'{key:10} = {value!r:20}'): <45} # {comment}"
            # line = f"{key:10} = {value!r:20}             # {comment}  "
            lines.append(line)
        return "\n".join(lines)


# header_to_string(fits_raw_file, header)
# %%-----------------------------------------------------------------------------


def load_fits_rgb16(fits_file):
    raw, header = load_fits(fits_file)
    if raw.ndim == 3 and raw.shape[0] == 3:
        rgb = np.transpose(raw, (1, 2, 0))   # CHW → HWC
    else:
        raise ValueError("Tento FITS není RGB stack ani Bayer RAW.")
    r, g, b = extract_rgb_channels(rgb)
    # !!!
    rgb[:, :, 1] //= 2
    return rgb, r, g, b, header


# fits_file = r"D:\ajps\astro\sunspotter\data\example_data\m31\stacked-16_M 31_15s60_Astro_20250126-200204018.fits"

# rgb16, r, g, b, header = load_fits_rgb16(fits_file)
# %%-----------------------------------------------------------------------------

def load_rgb16(filename):
    if filename.lower().endswith(".fits"):
        if os.path.basename(filename).lower().startswith("stacked"):
            return load_fits_rgb16(filename)
        else:
            return load_fits_raw(filename)
    elif filename.lower().endswith(".png"):
        return load_png_rgb16(filename)
    else:
        raise ValueError("Unknown file type, expected PNG or FITS")


# f=r"D:\ajps\astro\sunspotter\data\example_data\2026\Sun_0.001s0_VIS_20260510-113001928_27C.fits"
# rgb16, r, g, b, header = load_rgb16(f)
# %%-----------------------------------------------------------------------------


def rgb16_to_qimage(rgb16):
    # Convert to 8-bit for display
    rgb8 = np.ascontiguousarray(rgb16 // 256).astype(np.uint8)

    h, w, _ = rgb8.shape
    bytes_per_line = 3 * w

    qimg = QImage(
        rgb8.data,
        w,
        h,
        bytes_per_line,
        QImage.Format.Format_RGB888
    )
    # print("Size:", qimg.width(), qimg.height())
    # print("Format:", qimg.format())
    # print("BytesPerLine:", qimg.bytesPerLine())
    # print("Depth:", qimg.depth())
    # print("IsNull:", qimg.isNull())
    return qimg


# qimg=rgb16_to_qimage(rgb16)
# %%-----------------------------------------------------------------------------

class HistogramControlPanel(QWidget):
    def __init__(
        self, parent=None, on_apply=None,
        def_params=None
    ):
        super().__init__(parent)

        self.on_apply = on_apply  # callback function

        layout = QVBoxLayout(self)
        print(def_params["xmax"])
        # --- X range ---
        x_layout = QHBoxLayout()
        x_layout.addWidget(QLabel("xmin:"))
        self.xmin_edit = QLineEdit(str(def_params["xmin"]))
        x_layout.addWidget(self.xmin_edit)

        x_layout.addWidget(QLabel("xmax:"))
        self.xmax_edit = QLineEdit(str(def_params["xmax"]))
        x_layout.addWidget(self.xmax_edit)

        layout.addLayout(x_layout)

        # --- Y max ---
        if def_params["ymax"] is None:
            ymax = ""
        else:
            ymax = str(def_params["ymax"])
        y_layout = QHBoxLayout()
        y_layout.addWidget(QLabel("ymax:"))
        self.ymax_edit = QLineEdit(ymax)
        y_layout.addWidget(self.ymax_edit)
        layout.addLayout(y_layout)

        # --- Y scale ---
        scale_layout = QHBoxLayout()
        scale_layout.addWidget(QLabel("yscale:"))
        self.scale_combo = QComboBox()
        self.scale_combo.addItems(["linear", "log"])
        # Set initial value
        self.scale_combo.setCurrentText(def_params["yscale"])
        scale_layout.addWidget(self.scale_combo)
        layout.addLayout(scale_layout)

        # # --- Apply button ---
        # self.apply_btn = QPushButton("Apply")
        # self.apply_btn.clicked.connect(self.apply_clicked)
        # layout.addWidget(self.apply_btn)
        # Optional: set fixed height
        self.setFixedHeight(100)
    # --- ENTER triggers apply ---
        self.xmin_edit.returnPressed.connect(self.apply_clicked)
        self.xmax_edit.returnPressed.connect(self.apply_clicked)
        self.ymax_edit.returnPressed.connect(self.apply_clicked)
        self.scale_combo.activated.connect(self.apply_clicked)

    def apply_clicked(self):
        """Collect parameters and call callback."""
        params = {
            "xmin": int(self.xmin_edit.text()),
            "xmax": int(self.xmax_edit.text()),
            "ymax": None if self.ymax_edit.text() == "" else int(self.ymax_edit.text()),
            "yscale": self.scale_combo.currentText()
        }
        if self.on_apply:
            self.on_apply(params)

# %%-----------------------------------------------------------------------------


class MatplotlibCanvas(FigureCanvasQTAgg):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        # self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.fig, self.ax = plt.subplots(
            3, 1,
            figsize=(12, 8),
            sharex=True, sharey=True,
        )
        # 3 subplots (R, G, B)
        # self.ax[0] = fig.add_subplot(311)
        # self.ax_g = fig.add_subplot(312, sharex=self.ax_r)
        # self.ax_b = fig.add_subplot(313, sharex=self.ax_r)

        super().__init__(self.fig)
        self.setParent(parent)
    # ---------------------------------------------------------
    # ⭐ Update histogram with real RGB scatter
    # ---------------------------------------------------------

    def update_histogram(self, r, g, b, params):
        xmin = params["xmin"]
        xmax = params["xmax"]
        ymax = params["ymax"]
        yscale = params["yscale"]


        self.ax_r=self.ax[0]
        self.ax_g=self.ax[1]
        self.ax_b=self.ax[2]

        # Clear axes
        self.ax_r.clear()
        self.ax_g.clear()
        self.ax_b.clear()

        # -----------------------------------------------------
        # Helper: compute scatter data
        # -----------------------------------------------------
        def compute_xy(c):
            counts = np.bincount(c.ravel())
            x = np.nonzero(counts)[0]
            y = counts[x]
            return x, y


        def count_values_remove_zero_counts(c):
            """ Mám pole x a pole count. Chci odstranit všechny prvky, kde count == 0,
            a odstranit stejné indexy i v x. Vytvořit nové x2, y2 bez nul.
            """
            vals = c[c > 0]
            c_counts = np.bincount(vals)
            # c_counts = np.bincount(c.ravel())
            x0 = np.arange(len(c_counts))
            mask = c_counts > 0
            x = x0[mask]
            y = c_counts[mask]
            # print(x.shape, y.shape)
            return x, y
        
        # Compute histograms
        xr, yr = count_values_remove_zero_counts(r)
        xg, yg = count_values_remove_zero_counts(g)
        xb, yb = count_values_remove_zero_counts(b)
        # -----------------------------------------------------
        # Draw scatter for each channel
        # -----------------------------------------------------
        self.ax_r.scatter(xr, yr, s=1, color="red", alpha=0.9)
        self.ax_g.scatter(xg, yg, s=1, color="green", alpha=0.9)
        self.ax_b.scatter(xb, yb, s=1, color="blue", alpha=0.9)

        # -----------------------------------------------------
        # Apply axis settings
        # -----------------------------------------------------
        for ax in (self.ax_r, self.ax_g, self.ax_b):
            ax.set_xlim(xmin, xmax)
            ax.set_yscale(yscale)
            ax.grid(True, alpha=0.3)

            if ymax is not None:
                ax.set_ylim(0, ymax)

        # Titles
        # self.ax_r.set_title("R channel")
        # self.ax_g.set_title("G channel")
        # self.ax_b.set_title("B channel")
        self.ax_b.set_xlabel("Pixel value")

        self.ax_r.set_ylabel("R channel")
        self.ax_g.set_ylabel("G channel")
        self.ax_b.set_ylabel("B channel")

        # --- Statistics ---
        def stats(arr):
            return arr.min(), arr.max(), arr.size
        print(xr.min())
        rmin, rmax, rmean = stats(xr)
        gmin, gmax, gmean = stats(xg)
        bmin, bmax, bmean = stats(xb)

        # --- Subtitles ---
        self.ax_r.set_title(f"Red:  min={rmin}  max={rmax}  dcount={rmean:.1f}")
        self.ax_g.set_title(f"Green:min={gmin}  max={gmax}  dcount={gmean:.1f}")
        self.ax_b.set_title(f"Blue: min={bmin}  max={bmax}  dcount={bmean:.1f}")
        # self.ax_r.text(
        #     0.5, 0.82,
        #     f"min={rmin}  max={rmax}  mean={rmean:.1f}",
        #     ha="center", transform=self.ax_r.transAxes
        # )

        # self.ax_g.text(
        #     0.5, 0.82,
        #     f"min={gmin}  max={gmax}  mean={gmean:.1f}",
        #     ha="center", transform=self.ax_g.transAxes
        # )

        # self.ax_b.text(
        #     0.5, 0.82,
        #     f"min={bmin}  max={bmax}  mean={bmean:.1f}",
        #     ha="center", transform=self.ax_b.transAxes
        # )

        # self.ax_r.text(
        #     0.5, 1.02, "subtitle R", ha="center",
        #     va="bottom", transform=self.ax_r.transAxes
        # )

        # self.ax_g.text(
        #     0.5, 1.02, "subtitle G", ha="center",
        #     va="bottom", transform=self.ax_g.transAxes
        # )

        # self.ax_b.text(
        #     0.5, 1.02, "subtitle B", ha="center",
        #     va="bottom", transform=self.ax_b.transAxes
        # )

        # --- Automatic limits ---
        self.ax_r.relim()
        self.ax_r.autoscale()

        self.ax_g.relim()
        self.ax_g.autoscale()

        self.ax_b.relim()
        self.ax_b.autoscale()

        # self.fig.subplots_adjust(top=0.62)
        self.fig.subplots_adjust(
            left=0.08,
            right=0.98,
            top=0.95,
            bottom=0.07,
            hspace=0.35
        )

        # self.fig.tight_layout()
        self.draw()

        # self.draw()

    # def plot_example(self):
    #     self.ax.clear()
    #     self.ax.plot([0, 1, 2, 3], [10, 1, 20, 5], marker="o")
    #     self.ax.set_title("Example Graph")
    #     self.draw()
# %%-----------------------------------------------------------------------------


class ImageView(QGraphicsView):

    def __init__(self, pixel_callback=None, parent=None):
        super().__init__(parent)
        self.pixel_callback = pixel_callback
        self.setScene(QGraphicsScene(self))
        self.pixmap_item = QGraphicsPixmapItem()
        self.scene().addItem(self.pixmap_item)

        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        self._zoom = 0

    def setImage(self, qimg):
        pix = QPixmap.fromImage(qimg)
        self.pixmap_item.setPixmap(pix)

        rect = QRectF(pix.rect())
        self.setSceneRect(rect)

        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom = 0

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._zoom == 0:  # jen pokud uživatel nezoomoval
            self.fitInView(self.sceneRect(),
                           Qt.AspectRatioMode.KeepAspectRatio)

    def mouseMoveEvent(self, event):
        pos = self.mapToScene(event.pos())
        x = int(pos.x())
        y = int(pos.y())

        if self.pixel_callback is not None:
            self.pixel_callback(x, y)

        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.resetTransform()
            self.fitInView(self.sceneRect(),
                           Qt.AspectRatioMode.KeepAspectRatio)
            self._zoom = 0
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom = 0
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        if event.angleDelta().y() > 0:
            factor = 1.25
            self._zoom += 1
        else:
            factor = 0.8
            self._zoom -= 1

        if self._zoom < -10:
            self._zoom = -10
            return

        self.scale(factor, factor)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        super().mouseReleaseEvent(event)
# %%-----------------------------------------------------------------------------


def make_empty_image(width=800, height=600):
    return np.zeros((height, width, 3), dtype=np.uint16)

# %%-----------------------------------------------------------------------------


def make_panel(text, color):
    """Create a colored placeholder panel with centered text."""
    w = QWidget()
    layout = QVBoxLayout(w)
    label = QLabel(text)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(label)

    pal = w.palette()
    pal.setColor(QPalette.ColorRole.Window, QColor(color))
    w.setAutoFillBackground(True)
    w.setPalette(pal)
    return w
# %%-----------------------------------------------------------------------------


class MainWindow(QMainWindow):

    def setImage(self, qimg):
        self.scene().clear()
        pix = QPixmap.fromImage(qimg)
        self.pixmap_item = QGraphicsPixmapItem(pix)
        self.scene().addItem(self.pixmap_item)

        rect = QRectF(pix.rect())
        self.setSceneRect(rect)

        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom = 0

    def load_image_to_label(self, filename):
        try:
            # 1) načti FITS → ulož do atributů
            self.rgb16, self.r, self.g, self.b, self.header = load_rgb16(
                filename)

        except Exception as e:
            self.rgb16 = make_empty_image()
            self.r = self.rgb16[:, :, 0]
            self.g = self.rgb16[:, :, 1]
            self.b = self.rgb16[:, :, 2]

            self.statusBar().showMessage(f"Failed to load image: {e}")
            self.setWindowTitle(f"FITS Viewer —  failed to load: {filename}")
            qimg = rgb16_to_qimage(self.rgb16)
            self.image_view.setImage(qimg)
            return

        self.setWindowTitle(f"FITS Viewer — {filename}")
        # 2) konverze na QImage
        qimg = rgb16_to_qimage(self.rgb16)

        # 3) přepiš obrázek v ImageView
        self.image_view.setImage(qimg)

        # 4) statusbar info
        self.statusBar().showMessage(f"Loaded: {filename}")

    def open_file_dialog(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select a PNG or FITS Image file",
            self.last_dir,
            "FITS files (*.fits);;PNG files (*.png);;All supported (*.fits *.png)"
        )
        if filename:
            self.last_dir = os.path.dirname(filename)
            self.last_file = os.path.basename(filename)
            self.load_image_to_label(filename)
            self.hist_canvas.update_histogram(
                self.r, self.g, self.b, self.def_params)

    def __init__(self, argv):
        super().__init__()

        screen = QApplication.primaryScreen().availableGeometry()
        self.setGeometry(screen)
        self.setWindowTitle("Arg1 or File Dialog Demo")
        self.resize(screen.width(), screen.height()-100)

        # self.resize(600, 400)

        # --- Central panel ---
        panel = QWidget()
        layout = QVBoxLayout(panel)

        self.image_view = ImageView(pixel_callback=self.update_pixel_info)
        self.image_view.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.pixel_info_panel = QTextEdit()
        self.pixel_info_panel.setReadOnly(True)
        self.pixel_info_panel.setStyleSheet(
            "background-color: #203040; color: white; "
            "font-family: Consolas; font-size: 12px;"
        )
        self.pixel_info_panel.setText("FITS pixels WILL APPEAR HERE")

        # hist_panel = make_panel("HISTOGRAM AREA", "#384830")
        self.hist_canvas = MatplotlibCanvas()
        # self.hist_canvas.plot_example()   # draw initial graph
        hist_panel = self.hist_canvas

        self.def_params = {
            "xmin": 0,
            "xmax": 65535,
            "ymax": None,
            "yscale": "log"
        }

        # --- Histogram control panel ---
        self.hist_controls = HistogramControlPanel(
            on_apply=self.on_hist_params,
            def_params=self.def_params
        )

        self.header_panel = QTextEdit()
        self.header_panel.setReadOnly(True)
        self.header_panel.setStyleSheet(
            "background-color: #203040; color: white; "
            "font-family: Consolas; font-size: 12px;"
        )
        self.header_panel.setText("")

        split2 = QSplitter(Qt.Orientation.Vertical)
        # split2.addWidget(self.pixel_info_panel)
        split2.addWidget(hist_panel)
        split2.addWidget(self.hist_controls)
        split2.addWidget(self.header_panel)
        # split2.setSizes([450, 5,160])

        split2.setSizes([600, 120, 300])   # ✔️ TADY

        split1 = QSplitter(Qt.Orientation.Horizontal)
        split1.addWidget(self.image_view)
        split1.addWidget(split2)
        split1.setSizes([1000, 300])

        layout.addWidget(split1)
        self.setCentralWidget(panel)

        # --- Menu bar ---
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")

        open_action = QAction("Open Image…", self)
        open_action.triggered.connect(self.open_file_dialog)
        file_menu.addAction(open_action)

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # --- Handle arg1 or open dialog ---
        arg1 = argv[1] if len(sys.argv) > 1 else None
        if arg1 is None:
            # No argument → open dialog immediately
            self.last_dir = ""
            self.open_file_dialog()
        else:
            # Argument provided → show it
            self.last_dir = os.path.dirname(arg1)
            self.last_file = os.path.basename(arg1)
            # filename=arg1
            self.load_image_to_label(arg1)
        self.header_panel.setText(
            header_to_string(self.last_file, self.header)
        )
        self.hist_canvas.update_histogram(
            self.r, self.g, self.b, self.def_params)

    def update_pixel_info(self, x, y):
        if 0 <= x < self.rgb16.shape[1] and 0 <= y < self.rgb16.shape[0]:
            r, g, b = self.rgb16[y, x]
            self.statusBar().showMessage(f"x={x}, y={y}, R={r}, G={g}, B={b}")

    def on_hist_params(self, params):
        if hasattr(self, "r"):
            self.hist_canvas.update_histogram(self.r, self.g, self.b, params)


filename_png = r"D:\ajps\astro\sunspotter\data\example_data\m31\stacked-16_M 31_15s60_Astro_20250126-200204018.png"

fits_rgb_file = r"D:\ajps\astro\sunspotter\data\example_data\m31\stacked-16_M 31_15s60_Astro_20250126-200204018.fits"
fits_raw_file = r"D:\ajps\astro\sunspotter\data\example_data\m31\M 31_15s60_Astro_20250126-203118151_17C.fits"

f = r"D:\ajps\astro\sunspotter\data\example_data\2026\Sun_0.001s0_VIS_20260510-113001928_27C.fits"
fpng = r"D:\ajps\astro\sunspotter\data\example_data\2026\stacked-16_Sun_0.001000s0_VIS_20260510-112954325.png"


def main():
    # Simulate argv during debugging (optional)

    if len(sys.argv) == 1:
        sys.argv.append(f)

    # arg1 = sys.argv[1] if len(sys.argv) > 1 else None

    app = QApplication(sys.argv)
    win = MainWindow(sys.argv)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
# %%-----------------------------------------------------------------------------

"""
(*)~---------------------------------------------------------------------------
Pupil - eye tracking platform
Copyright (C) 2012-2020 Pupil Labs

Distributed under the terms of the GNU
Lesser General Public License (LGPL v3.0).
See COPYING and COPYING.LESSER for license details.
---------------------------------------------------------------------------~(*)
"""
import logging

import pye3d
from pye3d.detector_3d import Detector3D, CameraModel, DetectorMode
from pyglui import ui
from methods import normalize

from .detector_base_plugin import PupilDetectorPlugin
from .visualizer_2d import draw_eyeball_outline, draw_pupil_outline, draw_ellipse
from .visualizer_pye3d import Eye_Visualizer

logger = logging.getLogger(__name__)

version_installed = getattr(pye3d, "__version__", "0.0.1")
version_supported = "0.0.4"

if version_installed != version_supported:
    logger.info(
        f"Requires pye3d version {version_supported} "
        f"(Installed: {version_installed})"
    )
    raise ImportError("Unsupported version found")


class Pye3DPlugin(PupilDetectorPlugin):
    uniqueness = "by_class"
    icon_font = "pupil_icons"
    icon_chr = chr(0xEC19)

    label = "Pye3D"
    identifier = "3d"
    order = 0.101

    @property
    def pupil_detector(self):
        return self.detector

    def __init__(
        self,
        g_pool=None,
    ):
        super().__init__(g_pool=g_pool)
        self.camera = CameraModel(
            focal_length=self.g_pool.capture.intrinsics.focal_length,
            resolution=self.g_pool.capture.intrinsics.resolution,
        )
        async_apps = ("capture", "service")
        mode = (
            DetectorMode.asynchronous
            if g_pool.app in async_apps
            else DetectorMode.blocking
        )
        logger.debug(f"Running {mode.name} in {g_pool.app}")
        self.detector = Detector3D(camera=self.camera, long_term_mode=mode)
        self.debugVisualizer3D = Eye_Visualizer(self.g_pool, self.camera.focal_length)

    def get_init_dict(self):
        init_dict = super().get_init_dict()
        return init_dict

    def _process_camera_changes(self):
        camera = CameraModel(
            focal_length=self.g_pool.capture.intrinsics.focal_length,
            resolution=self.g_pool.capture.intrinsics.resolution,
        )
        if self.camera == camera:
            return

        logger.debug(f"Camera model change detected: {camera}. Resetting 3D detector.")
        self.camera = camera
        self.detector.reset_camera(self.camera)

        # Debug window also depends on focal_length, need to replace it with a new
        # instance. Make sure debug window is closed at this point or we leak the opengl
        # window.
        debug_window_was_opened = self.is_debug_window_open
        self.debug_window_close()
        self.debugVisualizer3D = Eye_Visualizer(self.g_pool, self.camera.focal_length)
        if debug_window_was_opened:
            self.debug_window_open()

    def on_resolution_change(self, old_size, new_size):
        # TODO: the logic for old 2D/3D resetting does not fit here anymore, but was
        # included in the PupilDetectorPlugin base class. This needs some cleaning up.
        pass

    def detect(self, frame, **kwargs):
        self._process_camera_changes()

        previous_detection_results = kwargs.get("previous_detection_results", [])
        for datum in previous_detection_results:
            if datum.get("method", "") == "2d c++":
                datum_2d = datum
                break
        else:
            # TODO: Should we handle this more gracefully? Can this even happen? What
            # could we return in that case?
            raise RuntimeError("No 2D detection result! Needed for pye3D!")

        result = self.detector.update_and_detect(
            datum_2d, frame.gray, debug=self.is_debug_window_open
        )

        eye_id = self.g_pool.eye_id
        result["timestamp"] = frame.timestamp
        result["topic"] = f"pupil.{eye_id}.{self.identifier}"
        result["id"] = eye_id
        result["method"] = "3d c++"
        result["norm_pos"] = normalize(
            result["location"], (frame.width, frame.height), flip_y=True
        )

        return result

    def on_notify(self, notification):
        super().on_notify(notification)

        subject = notification["subject"]
        if subject == "pupil_detector.3d.reset_model":
            if "id" not in notification:
                # simply apply to all eye processes
                self.reset_model()
            elif notification["id"] == self.g_pool.eye_id:
                # filter for specific eye processes
                self.reset_model()

    @classmethod
    def parse_pretty_class_name(cls) -> str:
        return "Pye3D Detector"

    def init_ui(self):
        super().init_ui()
        self.menu.label = self.pretty_class_name

        self.menu.append(ui.Button("Reset 3D model", self.reset_model))
        self.menu.append(ui.Button("Toggle debug window", self.debug_window_toggle))
        self.menu.append(
            ui.Switch("is_long_term_model_frozen", self.detector, label="Freeze model")
        )

    def gl_display(self):
        self.debug_window_update()
        result = self._recent_detection_result
        if result is not None:
            if not self.is_debug_window_open:
                # normal drawing
                draw_eyeball_outline(result)
                draw_pupil_outline(result)

            elif "debug_info" in result:
                # debug drawing
                debug_info = result["debug_info"]
                draw_ellipse(
                    ellipse=debug_info["projected_ultra_long_term"],
                    rgba=(0.5, 0, 0, 1),
                    thickness=2,
                )
                draw_ellipse(
                    ellipse=debug_info["projected_long_term"],
                    rgba=(0.8, 0.8, 0, 1),
                    thickness=2,
                )
                draw_ellipse(
                    ellipse=debug_info["projected_short_term"],
                    rgba=(0, 1, 0, 1),
                    thickness=2,
                )

    def cleanup(self):
        # if we change detectors, be sure debug window is also closed
        self.debug_window_close()

    # Public

    def reset_model(self):
        self.detector.reset()

    # Debug window management

    @property
    def is_debug_window_open(self) -> bool:
        return self.debugVisualizer3D.window is not None

    def debug_window_toggle(self):
        if not self.is_debug_window_open:
            self.debug_window_open()
        else:
            self.debug_window_close()

    def debug_window_open(self):
        if not self.is_debug_window_open:
            self.debugVisualizer3D.open_window()

    def debug_window_close(self):
        if self.is_debug_window_open:
            self.debugVisualizer3D.close_window()

    def debug_window_update(self):
        if self.is_debug_window_open:
            self.debugVisualizer3D.update_window(
                self.g_pool, self._recent_detection_result
            )

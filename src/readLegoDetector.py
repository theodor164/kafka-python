"""
Detectare piese LEGO folosind Pi Camera + OpenCV detecție culoare HSV.
Nu necesită ultralytics/YOLO — funcționează prin filtrarea culorilor
caracteristice LEGO (roșu, galben, albastru, verde, portocaliu).
"""
import cv2
import numpy as np
import logging
import threading
import datetime


# ── Praguri culori LEGO în spațiu HSV ────────────────────────
# (H: 0-179, S: 0-255, V: 0-255)
LEGO_COLORS = [
    # Roșu (două intervale în HSV)
    (np.array([0,   120, 70]),  np.array([10,  255, 255])),
    (np.array([170, 120, 70]),  np.array([179, 255, 255])),
    # Galben
    (np.array([20,  120, 100]), np.array([35,  255, 255])),
    # Albastru
    (np.array([100, 120, 70]),  np.array([130, 255, 255])),
    # Verde
    (np.array([40,  80,  70]),  np.array([80,  255, 255])),
    # Portocaliu
    (np.array([10,  120, 100]), np.array([20,  255, 255])),
]

# Număr minim de pixeli colorați pentru a considera că există LEGO
MIN_PIXELS = 500


class LegoDetector:
    def __init__(self, model_path=None):
        # model_path ignorat — păstrat pentru compatibilitate cu thread_lego
        self._lock    = threading.Lock()
        self._camera  = None
        self._running = False
        self._count   = 0

    def _start_camera(self):
        try:
            from picamera2 import Picamera2
            self._camera = Picamera2()
            self._camera.configure(
                self._camera.create_still_configuration(
                    main={"size": (640, 480), "format": "RGB888"}
                )
            )
            self._camera.start()
            self._running = True
            logging.info("[LegoDetector] Cameră inițializată ✅")
        except Exception as e:
            self._running = False
            logging.warning(f"[LegoDetector] Inițializare eșuată: {e}")

    def get_count(self) -> int:
        """
        Capturează un cadru și detectează piese LEGO prin culoare.
        Returnează numărul de regiuni LEGO distincte detectate.
        """
        if not self._running:
            self._start_camera()
            if not self._running:
                return 0

        try:
            with self._lock:
                frame = self._camera.capture_array()

            hsv   = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
            mask  = np.zeros(hsv.shape[:2], dtype=np.uint8)

            # Aplică masca pentru fiecare culoare LEGO
            for lower, upper in LEGO_COLORS:
                mask |= cv2.inRange(hsv, lower, upper)

            # Curăță zgomotul
            kernel = np.ones((5, 5), np.uint8)
            mask   = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  kernel)
            mask   = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

            # Găsește contururi distincte (piese separate)
            contours, _ = cv2.findContours(
                mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            # Numără doar contururile suficient de mari
            lego_contours = [c for c in contours if cv2.contourArea(c) > MIN_PIXELS]
            count = len(lego_contours)

            if count != self._count:
                logging.info(f"[LegoDetector] 🧱 {count} piese LEGO detectate")
                self._count = count

            return count

        except Exception as e:
            logging.error(f"[LegoDetector] Eroare detecție: {e}")
            return 0

    def stop(self):
        self._running = False
        if self._camera:
            try:
                self._camera.stop()
                self._camera.close()
            except Exception:
                pass
        logging.info("[LegoDetector] Cameră oprită")
    def is_occupied(self) -> bool:
      return self.get_count() > 0
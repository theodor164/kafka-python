# shared_camera.py
import threading
import time
import logging

class SharedCamera:
    def __init__(self, resolution=(640, 480)):
        from picamera2 import Picamera2
        self._picam2 = Picamera2()
        config = self._picam2.create_preview_configuration(
            main={"size": resolution, "format": "BGR888"}
        )
        self._picam2.configure(config)
        self._picam2.start()
        time.sleep(2)
        self._frame = None
        self._lock = threading.Lock()
        self._running = True
        threading.Thread(target=self._capture_loop, daemon=True).start()
        logging.info("[SharedCamera] Pornită")

    def _capture_loop(self):
        while self._running:
            frame = self._picam2.capture_array()
            with self._lock:
                self._frame = frame

    def get_frame(self):
        with self._lock:
            return self._frame.copy() if self._frame is not None else None

    def stop(self):
        self._running = False
        self._picam2.stop()
        self._picam2.close()
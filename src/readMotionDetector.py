import cv2
import numpy as np
import logging
import time
import datetime

class MotionDetector:
    def __init__(self, threshold_pixel=25, threshold_motion=500, resolution=(640, 480)):
        self.threshold_pixel = threshold_pixel
        self.threshold_motion = threshold_motion
        self.resolution = resolution
        self._picam2 = None
        self._prev_gray = None

    def start(self):
        from picamera2 import Picamera2
        self._picam2 = Picamera2()
        config = self._picam2.create_preview_configuration(
            main={"size": self.resolution, "format": "BGR888"}
        )
        self._picam2.configure(config)
        self._picam2.start()
        time.sleep(2)
        frame = self._picam2.capture_array()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        self._prev_gray = cv2.GaussianBlur(gray, (21, 21), 0)
        logging.info(f"[MotionDetector] Pornit — rezoluție {self.resolution}")

    def detect(self):
        frame = self._picam2.capture_array()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_blur = cv2.GaussianBlur(gray, (21, 21), 0)
        diff = cv2.absdiff(self._prev_gray, gray_blur)
        _, thresh = cv2.threshold(diff, self.threshold_pixel, 255, cv2.THRESH_BINARY)
        motion_pixels = cv2.countNonZero(thresh)
        motion_detected = motion_pixels > self.threshold_motion
        self._prev_gray = gray_blur
        return {
            "sensor_type": "motion",
            "timestamp": datetime.datetime.now().isoformat(),
            "motion_detected": motion_detected,
            "motion_pixels": int(motion_pixels),
        }

    def stop(self):
        if self._picam2 is not None:
            self._picam2.stop()
            self._picam2.close()
            self._picam2 = None
            logging.info("[MotionDetector] Cameră oprită")

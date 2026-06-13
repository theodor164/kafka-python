"""
Detectare persoane folosind Pi Camera + OpenCV HOG detector.
Returnează dacă există persoane în cameră și câte.
"""
import cv2
import logging
import threading
import datetime

class PersonDetector:
    def __init__(self):
        self._lock    = threading.Lock()
        self._camera  = None
        self._hog     = None
        self._running = False

    def start(self):
        """Inițializare cameră și detector HOG."""
        try:
            from picamera2 import Picamera2
            self._camera = Picamera2()
            self._camera.configure(
                self._camera.create_still_configuration(
                    main={"size": (640, 480), "format": "RGB888"}
                )
            )
            self._camera.start()

            self._hog = cv2.HOGDescriptor()
            self._hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

            self._running = True
            logging.info("[PersonDetector] Cameră și HOG inițializate ✅")
        except Exception as e:
            self._running = False
            logging.warning(f"[PersonDetector] Inițializare eșuată: {e}")

    def detect(self) -> dict:
        if not self._running or self._camera is None:
            return {
                "timestamp":       datetime.datetime.now().isoformat(),
                "person_detected": False,
                "person_count":    0,
            }
        try:
            with self._lock:
                frame = self._camera.capture_array()

            # Folosim rezoluție mai mare pentru detecție mai bună
            frame_resized = cv2.resize(frame, (640, 480))
            gray = cv2.cvtColor(frame_resized, cv2.COLOR_RGB2GRAY)

            boxes, weights = self._hog.detectMultiScale(
                gray,
                winStride=(4, 4),    # ← mai mic = mai sensibil
                padding=(8, 8),      # ← mai mult padding
                scale=1.02,          # ← mai multe scale-uri
                hitThreshold=0.0,    # ← prag minim
            )

            count    = len(boxes)
            detected = count > 0

            logging.info(f"[PersonDetector] {'🧍 ' + str(count) + ' persoană' if detected else 'Gol'}")

            return {
                "timestamp":       datetime.datetime.now().isoformat(),
                "person_detected": detected,
                "person_count":    count,
            }
        except Exception as e:
            logging.error(f"[PersonDetector] Eroare: {e}")
            return {
                "timestamp":       datetime.datetime.now().isoformat(),
                "person_detected": False,
                "person_count":    0,
            }

    def stop(self):
        """Oprire cameră."""
        self._running = False
        if self._camera:
            try:
                self._camera.stop()
                self._camera.close()
            except Exception:
                pass
        logging.info("[PersonDetector] Cameră oprită")
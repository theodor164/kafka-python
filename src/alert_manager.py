"""
Gestionează starea de alertă și condițiile de revenire.
Rulează independent de Kafka/internet.
"""
import threading
import math
import logging
from enum import Enum
from actuators import (
    activate_earthquake_alert,
    activate_air_alert,
    deactivate_all,
    lcd_write,
)

class AlertState(Enum):
    NORMAL       = "normal"
    EARTHQUAKE   = "earthquake"
    AIR_CRITICAL = "air_critical"
    PENDING      = "pending"

class AlertManager:
    def __init__(self):
        self.state            = AlertState.NORMAL
        self.lock             = threading.Lock()
        self._revenire_ok     = False
        self._revenire_timer  = None
        self.MAGNITUDINE_PRAG  = 2.0
        self.MAGNITUDINE_PROBE = 5
        self.CO_PPM_PRAG       = 500
        self.CO2_PPM_PRAG      = 1500
        self.TIMP_REVENIRE     = 60
        self._mag_buffer       = []
        self._last_co          = 0

        logging.info("[AlertManager] Inițializat")
        deactivate_all()

    def process_mpu6050(self, data: dict):
        ax = data.get("accel_x", 0)
        ay = data.get("accel_y", 0)
        az = data.get("accel_z", 0)
        mag = math.sqrt(ax**2 + ay**2 + az**2)

        self._mag_buffer.append(mag)
        if len(self._mag_buffer) > self.MAGNITUDINE_PROBE:
            self._mag_buffer.pop(0)

        if (len(self._mag_buffer) == self.MAGNITUDINE_PROBE and
                all(m > self.MAGNITUDINE_PRAG for m in self._mag_buffer)):
            self._trigger_earthquake()

    def process_air_quality(self, co_ppm: float, co2_ppm: float):
        if self.state == AlertState.NORMAL:
            if co_ppm > self.CO_PPM_PRAG or co2_ppm > self.CO2_PPM_PRAG:
                self._trigger_air_alert(co_ppm, co2_ppm)
        elif self.state == AlertState.AIR_CRITICAL:
            if co_ppm < self.CO_PPM_PRAG and co2_ppm < self.CO2_PPM_PRAG:
                self._start_revenire_timer()

    def _trigger_earthquake(self):
        with self.lock:
            if self.state != AlertState.EARTHQUAKE:
                logging.warning("[AlertManager] 🚨 Cutremur declanșat!")
                self.state = AlertState.EARTHQUAKE
                self._mag_buffer.clear()
                activate_earthquake_alert()
                if self._revenire_timer:
                    self._revenire_timer.cancel()
                self._revenire_timer = threading.Timer(
                    self.TIMP_REVENIRE,
                    self._set_pending
                )
                self._revenire_timer.start()

    def _trigger_air_alert(self, co_ppm, co2_ppm):
        with self.lock:
            logging.warning(f"[AlertManager] ⚠️ Aer critic! CO={co_ppm} CO2={co2_ppm}")
            self.state = AlertState.AIR_CRITICAL
            activate_air_alert()

    def _start_revenire_timer(self):
        if self._revenire_timer is None:
            logging.info(f"[AlertManager] Valori revenite, aștept {self.TIMP_REVENIRE}s...")
            self._revenire_timer = threading.Timer(
                self.TIMP_REVENIRE,
                self._set_pending
            )
            self._revenire_timer.start()
            lcd_write("Aer OK!", "Astept confirmare")

    def _set_pending(self):
        with self.lock:
            if self.state in (AlertState.AIR_CRITICAL, AlertState.EARTHQUAKE):
                logging.info("[AlertManager] Stare PENDING — așteaptă confirmare Angular")
                self.state = AlertState.PENDING
                lcd_write("Apasati butonul", "din aplicatie!")

    def confirm_revenire(self):
        with self.lock:
            if self.state == AlertState.PENDING:
                logging.info("[AlertManager] ✅ Confirmare primită — revenire la NORMAL")
                self.state = AlertState.NORMAL
                self._revenire_timer = None
                deactivate_all()
                return True
            elif self.state == AlertState.EARTHQUAKE:
                logging.info("[AlertManager] ✅ Cutremur confirmat oprit — NORMAL")
                self.state = AlertState.NORMAL
                self._revenire_timer = None
                deactivate_all()
                return True
            else:
                logging.warning(f"[AlertManager] Confirmare ignorată — stare: {self.state}")
                return False

    def get_state(self) -> str:
        return self.state.value

    def cleanup(self):
        if self._revenire_timer:
            self._revenire_timer.cancel()
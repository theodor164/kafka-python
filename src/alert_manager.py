"""
Gestionează starea de alertă și condițiile de revenire.
Logică:
  - Cutremur nou în EARTHQUAKE → resetează timer-ul
  - Cutremur nou în PENDING → reactivează alerta
  - Aer critic nou în PENDING → reactivează alerta
  - Aer critic nou în AIR_CRITICAL → resetează timer-ul de revenire
"""
import threading
import math
import logging
import time
from enum import Enum
from actuators import (
    activate_earthquake_alert,
    activate_air_alert,
    activate_pending,
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
        self._revenire_timer  = None
        self.MAGNITUDINE_PRAG  = 1.8
        self.MAGNITUDINE_PROBE = 1
        self.CO_PPM_PRAG       = 500
        self.CO2_PPM_PRAG      = 2000
        self.TIMP_REVENIRE     = 10
        self._mag_buffer       = []
        self._last_co          = 0
        self._cooldown_until = 0

        logging.info("[AlertManager] Inițializat")
        deactivate_all()

    def process_mpu6050(self, data: dict):
        if time.time() < self._cooldown_until:
            return
        ax = data.get("accel_x", 0)
        ay = data.get("accel_y", 0)
        az = data.get("accel_z", 0)
        mag = math.sqrt(ax**2 + ay**2 + az**2)

        self._mag_buffer.append(mag)
        if len(self._mag_buffer) > self.MAGNITUDINE_PROBE:
            self._mag_buffer.pop(0)

        if (
            len(self._mag_buffer) == self.MAGNITUDINE_PROBE
            and all(m > self.MAGNITUDINE_PRAG for m in self._mag_buffer)
        ):
            self._trigger_earthquake()

    def process_air_quality(self, co_ppm: float, co2_ppm: float):
        if time.time() < self._cooldown_until:
            return
        is_critical = co_ppm > self.CO_PPM_PRAG or co2_ppm > self.CO2_PPM_PRAG

        if self.state == AlertState.NORMAL:
            if is_critical:
                self._trigger_air_alert(co_ppm, co2_ppm)

        elif self.state == AlertState.AIR_CRITICAL:
            if is_critical:
                # Valorile rămân critice — anulează timer-ul de revenire
                self._cancel_timer()
            else:
                # Valorile s-au normalizat — pornește timer
                self._start_revenire_timer()

        elif self.state == AlertState.PENDING:
            if is_critical:
                # Reapare pericolul — reactivează alerta
                logging.warning("[AlertManager] ⚠️ Aer critic reapărut în PENDING — reactivez!")
                self._trigger_air_alert(co_ppm, co2_ppm)

    def _trigger_earthquake(self):
        with self.lock:
            if self.state == AlertState.NORMAL:
                # Primă alertă seismică
                logging.warning("[AlertManager] 🚨 Cutremur declanșat!")
                self.state = AlertState.EARTHQUAKE
                self._mag_buffer.clear()
                activate_earthquake_alert()
                self._reset_revenire_timer()

            elif self.state == AlertState.EARTHQUAKE:
                # Cutremur continuu — resetează timer-ul
                logging.warning("[AlertManager] 🔄 Cutremur continuu — resetez timer!")
                self._mag_buffer.clear()
                self._reset_revenire_timer()

            elif self.state == AlertState.PENDING:
                # Cutremur nou după perioadă de așteptare — reactivează
                logging.warning("[AlertManager] 🚨 Cutremur nou în PENDING — reactivez!")
                self.state = AlertState.EARTHQUAKE
                self._mag_buffer.clear()
                activate_earthquake_alert()
                self._reset_revenire_timer()

    def _trigger_air_alert(self, co_ppm, co2_ppm):
        with self.lock:
            logging.warning(f"[AlertManager] ⚠️ Aer critic! CO={co_ppm} CO2={co2_ppm}")
            self.state = AlertState.AIR_CRITICAL
            self._cancel_timer()
            activate_air_alert()

    def _start_revenire_timer(self):
        with self.lock:
            if self._revenire_timer is None:
                logging.info(f"[AlertManager] Valori revenite, aștept {self.TIMP_REVENIRE}s...")
                self._revenire_timer = threading.Timer(
                    self.TIMP_REVENIRE, self._set_pending
                )
                self._revenire_timer.start()
                lcd_write("Aer OK!", "Astept confirmare")

    def _reset_revenire_timer(self):
        """Anulează timer-ul curent și pornește unul nou."""
        if self._revenire_timer:
            self._revenire_timer.cancel()
        self._revenire_timer = threading.Timer(
            self.TIMP_REVENIRE, self._set_pending
        )
        self._revenire_timer.start()

    def _cancel_timer(self):
        """Anulează timer-ul de revenire."""
        if self._revenire_timer:
            self._revenire_timer.cancel()
            self._revenire_timer = None

    def _set_pending(self):
        with self.lock:
            if self.state in (AlertState.AIR_CRITICAL, AlertState.EARTHQUAKE):
                logging.info("[AlertManager] Stare PENDING — așteaptă confirmare Angular")
                self.state = AlertState.PENDING
                self._revenire_timer = None
                activate_pending()

    def confirm_revenire(self):
        with self.lock:
            if self.state in (AlertState.PENDING, AlertState.EARTHQUAKE):
                logging.info("[AlertManager] ✅ Confirmare primită — revenire la NORMAL")
                self.state = AlertState.NORMAL
                self._cancel_timer()
                deactivate_all()
                return True
            else:
                logging.warning(f"[AlertManager] Confirmare ignorată — stare: {self.state}")
                return False

    def force_reset(self):
        with self.lock:
            logging.warning("[AlertManager] ⚠️ RESET FORȚAT!")
            self.state = AlertState.NORMAL
            self._cancel_timer()
            self._mag_buffer.clear()
            self._cooldown_until = time.time() + 30
            deactivate_all()
            return True

    def get_state(self) -> str:
        return self.state.value

    def cleanup(self):
        self._cancel_timer()
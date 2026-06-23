"""
Gestionează toți actuatorii fizici:
  - 2 relee (active LOW): Fan 1 → GPIO17, Fan 2 → GPIO27
  - LED RGB (3 LED-uri separate): Roșu→GPIO23, Verde→GPIO24, Albastru→GPIO25
  - Buzzer activ (active HIGH): GPIO16
  - Servo SG90: GPIO12 (gpiozero + LGPIOFactory)
  - LCD 16x2 I2C: adresa 0x27
"""
import logging
import time  

# ── lgpio ────────────────────────────────────────────────────
try:
    import lgpio
    LGPIO_AVAILABLE = True
except Exception:
    LGPIO_AVAILABLE = False

# ── gpiozero pentru servo ────────────────────────────────────
try:
    from gpiozero import Servo
    from gpiozero.pins.lgpio import LGPIOFactory
    GPIOZERO_AVAILABLE = True
except Exception:
    GPIOZERO_AVAILABLE = False

# ── State globale ────────────────────────────────────────────
HARDWARE_AVAILABLE = False
h      = None
lcd    = None
LCD_AVAILABLE = False
_servo = None

# ── Pini și logică relee ─────────────────────────────────────
# Relee ACTIVE LOW: 0 = pornit, 1 = oprit
# În asta:
RELAY_ON  = 1
RELAY_OFF = 0

# LED-uri și buzzer ACTIVE HIGH: 1 = pornit, 0 = oprit
LED_ON  = 1
LED_OFF = 0

PINS = {
    # Relee (active LOW)
    "fan1":    17,
    "fan2":    27,
    # LED-uri (active HIGH)
    "led_r":   23,
    "led_g":   24,
    "led_b":   25,
    # Buzzer activ (active HIGH)
    "buzzer":  16,
}

SERVO_PIN = 12  # controlat separat prin gpiozero

# ── Inițializare ─────────────────────────────────────────────

def _init_hardware():
    global HARDWARE_AVAILABLE, h
    if h is not None:
        return
    if not LGPIO_AVAILABLE:
        logging.warning("[Actuatori] lgpio lipsă — MOCK MODE 🔧")
        return
    try:
        h = lgpio.gpiochip_open(0)
        # Relee — stare inițială OFF (HIGH pentru active LOW)
        for name in ("fan1", "fan2"):
            lgpio.gpio_claim_output(h, PINS[name])
            lgpio.gpio_write(h, PINS[name], RELAY_OFF)
        # LED-uri și buzzer — stare inițială OFF (LOW)
        for name in ("led_r", "led_g", "led_b", "buzzer"):
            lgpio.gpio_claim_output(h, PINS[name])
            lgpio.gpio_write(h, PINS[name], LED_OFF)
        HARDWARE_AVAILABLE = True
        logging.info("[Actuatori] lgpio inițializat ✅")
    except Exception as e:
        HARDWARE_AVAILABLE = False
        h = None
        logging.warning(f"[Actuatori] GPIO indisponibil — MOCK MODE 🔧: {e}")


def _init_servo():
    global _servo
    if _servo is not None:
        return
    if not GPIOZERO_AVAILABLE:
        logging.warning("[Servo] gpiozero lipsă — mock mode")
        return
    try:
        factory = LGPIOFactory()
        _servo = Servo(
            SERVO_PIN,
            pin_factory=factory,
            min_pulse_width=0.5 / 1000,  # 0.5 ms → 0°
            max_pulse_width=2.5 / 1000,  # 2.5 ms → 180°
        )
        logging.info(f"[Servo] SG90 inițializat pe GPIO{SERVO_PIN} ✅")
    except Exception as e:
        _servo = None
        logging.warning(f"[Servo] Indisponibil — mock mode: {e}")


def _init_lcd():
    global LCD_AVAILABLE, lcd
    if lcd is not None:
        return
    try:
        from RPLCD.i2c import CharLCD
        lcd = CharLCD(
            i2c_expander="PCF8574",
            address=0x27,
            port=1,
            cols=16,
            rows=2,
            dotsize=8,
        )
        LCD_AVAILABLE = True
        logging.info("[LCD] Detectat la 0x27 ✅")
    except Exception as e:
        LCD_AVAILABLE = False
        lcd = None
        logging.warning(f"[LCD] Indisponibil — mock mode 🔧: {e}")

# ── Primitive ────────────────────────────────────────────────

def _set_relay(name: str, on: bool):
    """Controlează un releu ținând cont de logica active LOW."""
    _init_hardware()
    pin = PINS[name]
    value = RELAY_ON if on else RELAY_OFF
    if HARDWARE_AVAILABLE and h:
        lgpio.gpio_write(h, pin, value)
    else:
        logging.info(f"[MOCK Releu] GPIO{pin} ({name}) → {'ON 🟢' if on else 'OFF ⚫'}")


def _set_output(name: str, on: bool):
    """Controlează LED sau buzzer (active HIGH)."""
    _init_hardware()
    pin = PINS[name]
    value = LED_ON if on else LED_OFF
    if HARDWARE_AVAILABLE and h:
        lgpio.gpio_write(h, pin, value)
    else:
        logging.info(f"[MOCK] GPIO{pin} ({name}) → {'ON ✅' if on else 'OFF ⬛'}")

# ── Ventilatoare ─────────────────────────────────────────────

def set_fans(on: bool):
    _set_relay("fan1", on)
    _set_relay("fan2", on)
    logging.info(f"[Ventilatoare] → {'ON 💨' if on else 'OFF'}")

# ── LED RGB ──────────────────────────────────────────────────

def set_led_color(color: str):
    """
    Aprinde un singur LED la un moment dat.
    color: 'red' | 'green' | 'blue' | 'off'
    """
    _set_output("led_r", color == "red")
    _set_output("led_g", color == "green")
    _set_output("led_b", color == "blue")
    logging.info(f"[LED] → {color.upper()}")

# ── Buzzer ───────────────────────────────────────────────────

def set_buzzer(on: bool):
    _set_output("buzzer", on)
    logging.info(f"[Buzzer] → {'ON 🔔' if on else 'OFF'}")

# ── Servo ────────────────────────────────────────────────────

def set_servo(position: str):
    _init_servo()
    mapping = {"normal": "min", "alert": "mid", "ventilatie": "mid"}
    pos = mapping.get(position, "mid")
    if _servo:
        getattr(_servo, pos)()
        time.sleep(0.5)      # așteaptă să ajungă la poziție
        _servo.value = None  # ← detașează — oprește PWM, fără zgomot
        logging.info(f"[Servo] → {position}")
    else:
        logging.info(f"[MOCK Servo] → {position}")

# ── LCD ──────────────────────────────────────────────────────

def lcd_write(line1: str, line2: str = ""):
    from i2c_lock import i2c_lock
    _init_lcd()
    with i2c_lock:   # ← adaugă
        if LCD_AVAILABLE and lcd:
            try:
                lcd.clear()
                lcd.write_string(line1[:16])
                if line2:
                    lcd.cursor_pos = (1, 0)
                    lcd.write_string(line2[:16])
            except Exception as e:
                logging.warning(f"[LCD] Eroare scriere: {e}")
        else:
            logging.info(f"[MOCK LCD] ┌────────────────┐")
            logging.info(f"[MOCK LCD] │{line1[:16]:<16}│")
            logging.info(f"[MOCK LCD] │{line2[:16]:<16}│")
            logging.info(f"[MOCK LCD] └────────────────┘")

# ── Stări sistem ─────────────────────────────────────────────

def activate_earthquake_alert(occupied: bool = False):
    set_led_color("red")
    set_fans(True)
    set_buzzer(True)
    if occupied:
        set_servo("ventilatie")  # 180° — ușă complet deschisă, evacuare
        lcd_write("CUTREMUR!", "Iesiti din casa!")
    else:
        set_servo("alert")       # 90° — ușă parțial închisă, casa goală
        lcd_write("CUTREMUR!", "Casa goala")



def activate_air_alert(occupied: bool = False):
    set_led_color("red")
    set_fans(True)
    set_buzzer(True)
    if occupied:
        set_servo("ventilatie")  # 180° — ventilație maximă + evacuare
        lcd_write("AER VICIAT!", "Deschide geamul!")
    else:
        set_servo("ventilatie")  # 180° — ventilație automată
        lcd_write("AER VICIAT!", "Ventilatie auto")


def activate_pending():
    logging.info("[Actuatori] Stare PENDING")
    set_led_color("blue")
    set_buzzer(False)        # oprire buzzer — valori s-au normalizat
    # ventilatoarele rămân ON până la confirmare
    lcd_write("Apasati butonul", "din aplicatie!")


def deactivate_all():
    set_led_color("green")
    set_fans(False)
    set_buzzer(False)
    set_servo("normal")          # 0° — ușă normală
    lcd_write("CASA ACTIVA", "Stare: Normala")

# ── Cleanup ──────────────────────────────────────────────────

def cleanup():
    global h, lcd, _servo
    logging.info("[Actuatori] Cleanup...")
    try:
        set_fans(False)
        set_led_color("off")
        set_buzzer(False)
    except Exception:
        pass
    if HARDWARE_AVAILABLE and h:
        for pin in PINS.values():
            # relee → RELAY_OFF (HIGH), restul → LOW
            if pin in (PINS["fan1"], PINS["fan2"]):
                lgpio.gpio_write(h, pin, RELAY_OFF)
            else:
                lgpio.gpio_write(h, pin, LED_OFF)
        lgpio.gpiochip_close(h)
        h = None
    if LCD_AVAILABLE and lcd:
        try:
            lcd.clear()
            lcd.close()
        except Exception:
            pass
        lcd = None
    if _servo:
        try:
            _servo.close()
        except Exception:
            pass
        _servo = None
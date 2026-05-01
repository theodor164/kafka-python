import logging

# ── Încearcă să importe lgpio ────────────────────────────────
try:
    import lgpio
    LGPIO_AVAILABLE = True
except Exception:
    LGPIO_AVAILABLE = False

HARDWARE_AVAILABLE = False
h = None
LCD_AVAILABLE = False
lcd = None

# ── Definire pini ─────────────────────────────────────────────
PINS = {
    "led1":  17,
    "led2":  18,
    "led3":  27,
    "led4":  22,
    "fan1":  23,
    "fan2":  24,
    "door":  25,
    "spare": 12,
}

def _init_hardware():
    """Inițializare lazy — apelată doar când e nevoie."""
    global HARDWARE_AVAILABLE, h
    if h is not None:
        return  # deja inițializat
    try:
        h = lgpio.gpiochip_open(0)
        for name, pin in PINS.items():
            lgpio.gpio_claim_output(h, pin)
            lgpio.gpio_write(h, pin, 0)
        HARDWARE_AVAILABLE = True
        logging.info("[Actuatori] Hardware lgpio inițializat ✅")
    except Exception as e:
        HARDWARE_AVAILABLE = False
        h = None
        logging.warning(f"[Actuatori] GPIO indisponibil — MOCK MODE 🔧: {e}")

def _init_lcd():
    """Inițializare lazy LCD."""
    global LCD_AVAILABLE, lcd
    if lcd is not None:
        return
    try:
        from RPLCD.i2c import CharLCD
        lcd = CharLCD(
            i2c_expander='PCF8574',
            address=0x27,
            port=1,
            cols=16,
            rows=2,
            dotsize=8
        )
        LCD_AVAILABLE = True
        logging.info("[LCD] Detectat la 0x27 ✅")
    except Exception:
        LCD_AVAILABLE = False
        lcd = None
        logging.warning("[LCD] Indisponibil — mock mode 🔧")

def _set_pin(name: str, state: bool):
    _init_hardware()
    pin = PINS[name]
    if HARDWARE_AVAILABLE and h:
        lgpio.gpio_write(h, pin, 1 if state else 0)
    else:
        logging.info(f"[MOCK] GPIO {pin} ({name}) → {'HIGH ✅' if state else 'LOW ⬛'}")

def set_leds(state: bool):
    for led in ["led1", "led2", "led3", "led4"]:
        _set_pin(led, state)
    logging.info(f"[Actuatori] LED-uri → {'ON' if state else 'OFF'}")

def set_fans(state: bool):
    _set_pin("fan1", state)
    _set_pin("fan2", state)
    logging.info(f"[Actuatori] Ventilatoare → {'ON' if state else 'OFF'}")

def set_door(state: bool):
    _set_pin("door", state)
    logging.info(f"[Actuatori] Ușă → {'INCHISA 🔒' if state else 'DESCHISA 🔓'}")

def lcd_write(line1: str, line2: str = ""):
    _init_lcd()
    if LCD_AVAILABLE and lcd:
        lcd.clear()
        lcd.write_string(line1[:16])
        if line2:
            lcd.cursor_pos = (1, 0)
            lcd.write_string(line2[:16])
    else:
        logging.info(f"[MOCK LCD] ┌────────────────┐")
        logging.info(f"[MOCK LCD] │{line1[:16]:<16}│")
        logging.info(f"[MOCK LCD] │{line2[:16]:<16}│")
        logging.info(f"[MOCK LCD] └────────────────┘")

def activate_earthquake_alert():
    logging.warning("[ALERTĂ] 🚨 CUTREMUR DETECTAT")
    set_leds(True)
    set_fans(True)
    set_door(False)
    lcd_write("!! CUTREMUR !!", "INTRATI ADAPOST")

def activate_air_alert():
    logging.warning("[ALERTĂ] ⚠️ CALITATE AER CRITICĂ")
    set_leds(True)
    set_fans(True)
    set_door(True)
    lcd_write("AER VICIAT!", "VENTILATIE ON")

def deactivate_all():
    logging.info("[Actuatori] Revenire la stare normală")
    set_leds(False)
    set_fans(False)
    set_door(True)
    lcd_write("ADAPOST ACTIV", "Stare: Normala")

def cleanup():
    global h, lcd
    if HARDWARE_AVAILABLE and h:
        for pin in PINS.values():
            lgpio.gpio_write(h, pin, 0)
        lgpio.gpiochip_close(h)
        h = None
        logging.info("[Actuatori] lgpio cleanup")
    if LCD_AVAILABLE and lcd:
        lcd.clear()
        lcd.close()
        lcd = None
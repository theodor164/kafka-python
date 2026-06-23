import threading
i2c_lock = threading.RLock()   # ← RLock în loc de Lock
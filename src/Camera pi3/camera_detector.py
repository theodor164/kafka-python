import threading
import time
import subprocess
import os
from ultralytics import YOLO 

class LegoDetector:
    def __init__(self, model_lego_path):
        self.latest_count = 0
        self.running = True
        
        print(f"Incarc modelul custom LEGO din: {model_lego_path}...")
        self.model = YOLO(model_lego_path)
        
        # Firul de execuție în fundal
        self.thread = threading.Thread(target=self._update, args=())
        self.thread.daemon = True
        self.thread.start()

    def _update(self):
        poza_nume = "cadru_curent.jpg"
        
        while self.running:
           # Am adăugat setările pentru înghețarea mișcării (Shutter Speed)
           # 1 & 2: Echilibrul perfect între lumină și înghețarea mișcării
            cmd = [
                "rpicam-jpeg", 
                "-o", poza_nume, 
                "-t", "200", 
                "--shutter", "10000", # 1/100 dintr-o secundă (mult mai luminos!)
                "--gain", "4.0",      # Forțăm senzorul să extragă lumină din umbre
                "--width", "640", 
                "--height", "480", 
                "--nopreview"
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            if not os.path.exists(poza_nume):
                time.sleep(1)
                continue

            # 3. Cerem AI-ului să accepte și detecțiile de care e doar 35% sigur (din cauza umbrelor)
            results = self.model.predict(source=poza_nume, conf=0.35, save=False, verbose=False)
            
            # 3. Numărăm câte pătrate (omuleți) a găsit
            self.latest_count = len(results[0].boxes)
            
            time.sleep(1) 

    def get_count(self):
        return self.latest_count

    def stop(self):
        self.running = False
        if os.path.exists("cadru_curent.jpg"):
            os.remove("cadru_curent.jpg")

# --- BLOCUL DE TESTARE PENTRU LEGO ---
if __name__ == "__main__":
    MODEL_CUSTOM_LEGO = "models/best.pt"
    
    try:
        if not os.path.exists(MODEL_CUSTOM_LEGO):
            print(f"⚠️ EROARE: Nu gasesc modelul {MODEL_CUSTOM_LEGO}. L-ai pus în folderul 'models/'?")
            exit()
            
        detector = LegoDetector(MODEL_CUSTOM_LEGO)
        print("Sistemul de detecție LEGO custom este activ! Aștept imaginea...")
        time.sleep(2)
        
        while True:
            curent = detector.get_count()
            print(f"[{time.strftime('%H:%M:%S')}] Omuleți LEGO detectați: {curent}")
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nTestare oprită de utilizator.")
    finally:
        if 'detector' in locals():
            detector.stop()
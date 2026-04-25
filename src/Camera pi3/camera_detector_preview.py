import cv2
import threading
import time
import subprocess
import os
from ultralytics import YOLO 

class LegoDetector:
    def __init__(self, model_lego_path):
        self.latest_count = 0
        self.latest_frame = None  # Nou: Aici salvăm imaginea desenată
        self.running = True
        
        print(f"Incarc modelul custom LEGO din: {model_lego_path}...")
        self.model = YOLO(model_lego_path)
        
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
            
            # Numărăm omuleții
            self.latest_count = len(results[0].boxes)
            
            # MAGIA NOUĂ: Cerem lui YOLO să ne dea imaginea cu pătrățelele desenate
            self.latest_frame = results[0].plot() 
            
            time.sleep(1) 

    def get_data(self):
        # Acum returnăm atât numărul, cât și poza
        return self.latest_count, self.latest_frame

    def stop(self):
        self.running = False
        if os.path.exists("cadru_curent.jpg"):
            os.remove("cadru_curent.jpg")
        cv2.destroyAllWindows() # Închidem fereastra la final

# --- BLOCUL DE TESTARE PENTRU LEGO ---
if __name__ == "__main__":
    MODEL_CUSTOM_LEGO = "/home/teddy164/proiecte pi/Camera pi3/best.pt"
    
    try:
        if not os.path.exists(MODEL_CUSTOM_LEGO):
            print(f"⚠️ EROARE: Nu gasesc modelul {MODEL_CUSTOM_LEGO}.")
            exit()
            
        detector = LegoDetector(MODEL_CUSTOM_LEGO)
        print("Sistemul este activ! Aștept imaginea... (Apasă 'q' pe fereastra video pentru a ieși)")
        time.sleep(2)
        
        while True:
            # Luăm datele din fundal
            curent, cadru = detector.get_data()
            print(f"[{time.strftime('%H:%M:%S')}] Omuleți LEGO detectați: {curent}")
            
            # Dacă avem o imagine procesată, o afișăm pe ecran
            if cadru is not None:
                cv2.imshow("Camera AI - Live", cadru)
                
                # Această linie este obligatorie! Actualizează fereastra grafică.
                # Dacă apeși tasta 'q', programul se oprește.
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                    
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nTestare oprită din terminal.")
    finally:
        if 'detector' in locals():
            detector.stop()
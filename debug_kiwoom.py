import sys
print("Start", flush=True)
import time
print("Imported time", flush=True)
from PyQt5.QtWidgets import QApplication
print("Imported PyQt5", flush=True)
from kiwoom_api import Kiwoom
print("Imported kiwoom_api", flush=True)

if __name__ == "__main__":
    print("Main start", flush=True)
    app = QApplication(sys.argv)
    print("App created", flush=True)
    kiwoom = Kiwoom()
    print("Kiwoom created", flush=True)
    kiwoom.comm_connect()
    print("Connected", flush=True)
    
    # Just exit
    sys.exit(0)

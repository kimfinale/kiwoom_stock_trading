
import sys
import os

with open("python_check.txt", "w") as f:
    f.write(f"Python executable: {sys.executable}\n")
    f.write(f"CWD: {os.getcwd()}\n")
    f.write("Python is working.\n")

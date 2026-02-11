import sys
import time
import json
import logging
import schedule
from PyQt5.QtWidgets import QApplication
from kiwoom_api import Kiwoom
from state_manager import StateManager
from strategy_executor import StrategyExecutor

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def load_config():
    with open("config.json", "r", encoding='utf-8') as f:
        return json.load(f)

def job(executor):
    try:
        executor.execute_step()
    except Exception as e:
        logging.error(f"Error during execution step: {e}")

def main():
    app = QApplication(sys.argv)
    
    # 1. Load Config & State
    config = load_config()
    state_manager = StateManager()
    
    # 2. Init Kiwoom
    kiwoom = Kiwoom()
    kiwoom.comm_connect() # Blocking login
    
    # 3. Init Executor
    executor = StrategyExecutor(kiwoom, state_manager, config)
    
    print("Bot initialized. Starting scheduler...")
    
    # 4. Schedule
    # interval = config["strategy"]["buy_interval_minutes"]
    # schedule.every(interval).minutes.do(job, executor)
    
    # For now, we utilize a simple loop with sleep to allow PyQt event loop processing if needed
    # But PyQt needs app.exec_() to treat events.
    # We can use QTimer to trigger the job within PyQt loop.
    
    from PyQt5.QtCore import QTimer
    timer = QTimer()
    interval_ms = config["strategy"]["buy_interval_minutes"] * 60 * 1000
    
    # For testing, let's force 10 seconds if dry run? No, stick to config.
    # interval_ms = 10000 # 10s DEBUG
    
    timer.timeout.connect(lambda: job(executor))
    timer.start(interval_ms)
    
    # Run immediately once
    job(executor)
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()

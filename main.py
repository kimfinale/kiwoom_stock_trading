import sys
import pickle
import os
import datetime
import pandas as pd
import pandas_ta as ta
from PyQt5.QtWidgets import *
from PyQt5.QAxContainer import *
from PyQt5.QtCore import *

class Kiwoom(QAxWidget):
    msg_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._create_kiwoom_instance()
        self._set_signal_slots()
        self.account_num = None
        self.tr_data = {}  # Dictionary to store TR data

    def _create_kiwoom_instance(self):
        self.setControl("KHOPENAPI.KHOpenAPICtrl.1")

    def _set_signal_slots(self):
        self.OnEventConnect.connect(self._event_connect)
        self.OnReceiveTrData.connect(self._receive_tr_data)
        self.OnReceiveMsg.connect(self._receive_msg)
        self.OnReceiveRealData.connect(self._receive_real_data)
        self.OnReceiveChejanData.connect(self._receive_chejan_data)

    def comm_connect(self):
        self.dynamicCall("CommConnect()")
        self.login_event_loop = QEventLoop()
        self.login_event_loop.exec_()

    def _event_connect(self, err_code):
        if err_code == 0:
            print("Connected successfully")
            self._get_account_info()
        else:
            print("Disconnected")
        self.login_event_loop.exit()

    def _get_account_info(self):
        account_list = self.dynamicCall("GetLoginInfo(QString)", "ACCLIST")
        self.account_num = account_list.split(';')[0]
        print(f"Account Number: {self.account_num}")

    def get_current_price(self, code):
        self.dynamicCall("SetInputValue(QString, QString)", "종목코드", code)
        self.dynamicCall("CommRqData(QString, QString, int, QString)", "opt10001_req", "opt10001", 0, "0101")
        
        self.tr_event_loop = QEventLoop()
        self.tr_event_loop.exec_()
        return self.tr_data.get(code)

    def _receive_tr_data(self, screen_no, rqname, trcode, recordname, next, unused1, unused2, unused3, unused4):
        if rqname == "opt10001_req":
            code = self.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, "", 0, "종목코드").strip()
            name = self.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, "", 0, "종목명").strip()
            price = self.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, "", 0, "현재가").strip()
            # Price comes with +/- sign, strip it
            price = abs(int(price))
            
            self.tr_data[code] = {'name': name, 'price': price}
            self.tr_event_loop.exit()

    def _receive_msg(self, screen_no, rqname, trcode, msg):
        self.msg_signal.emit(msg)

    def _receive_real_data(self, code, real_type, real_data):
        # Implementation for real-time data if needed
        pass

    def _receive_chejan_data(self, gubun, item_cnt, fid_list):
        # Implementation for Chejan (Order/Execution) data
        print(f"Chejan Data: {gubun}")

    def send_order(self, rqname, screen_no, order_type, code, quantity, price, order_gov, order_num=""):
        # order_type: 1:Buy, 2:Sell
        # order_gov: 00:Limit, 03:Market
        result = self.dynamicCall("SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)", 
                                  [rqname, screen_no, self.account_num, order_type, code, quantity, price, order_gov, order_num])
        return result

class TradingBotWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kiwoom Trading Bot")
        self.setGeometry(300, 300, 800, 500)
        
        self.kiwoom = Kiwoom()
        self.kiwoom.comm_connect()
        self.kiwoom.msg_signal.connect(self.log)
        
        self.init_ui()
        self.init_timer()
        
        self.active_trades = pd.DataFrame(columns=["code", "name", "price", "quantity", "type"])
        self.history_df = pd.DataFrame(columns=["close"])
        self.target_stock = "005930" # Samsung Electronics
        
        self.load_state()

    def init_ui(self):
        # Create Layouts and Widgets
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Account Info
        self.label_account = QLabel("Account Info: Loading...")
        if self.kiwoom.account_num:
            self.label_account.setText(f"Account: {self.kiwoom.account_num}")
        self.layout.addWidget(self.label_account)
        
        # Trading Table
        self.table_trades = QTableWidget()
        self.table_trades.setColumnCount(4)
        self.table_trades.setHorizontalHeaderLabels(["Stock Name", "Price", "Quantity", "Type"])
        self.layout.addWidget(self.table_trades)
        
        # Log Window
        self.text_log = QTextEdit()
        self.text_log.setReadOnly(True)
        self.layout.addWidget(self.text_log)

    def log(self, msg):
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        self.text_log.append(f"[{current_time}] {msg}")

    def init_timer(self):
        self.timer = QTimer(self)
        self.timer.setInterval(1000 * 60 * 10) # 10 Minutes
        self.timer.timeout.connect(self.trading_loop)
        self.timer.start()

    def load_state(self):
        if os.path.exists("trading_state.pkl"):
            try:
                with open("trading_state.pkl", "rb") as f:
                    state = pickle.load(f)
                    self.active_trades = state.get('active_trades', self.active_trades)
                    self.history_df = state.get('history_df', self.history_df)
                    self.log("State loaded successfully.")
                    
                    # Restore table from active_trades
                    for index, row in self.active_trades.iterrows():
                         row_position = self.table_trades.rowCount()
                         self.table_trades.insertRow(row_position)
                         self.table_trades.setItem(row_position, 0, QTableWidgetItem(row['name']))
                         self.table_trades.setItem(row_position, 1, QTableWidgetItem(str(row['price'])))
                         self.table_trades.setItem(row_position, 2, QTableWidgetItem(str(row['quantity'])))
                         self.table_trades.setItem(row_position, 3, QTableWidgetItem(row['type']))
            except Exception as e:
                self.log(f"Failed to load state: {e}")

    def save_state(self):
        try:
            with open("trading_state.pkl", "wb") as f:
                state = {
                    'active_trades': self.active_trades,
                    'history_df': self.history_df
                }
                pickle.dump(state, f)
            self.log("State saved successfully.")
        except Exception as e:
            self.log(f"Failed to save state: {e}")

    def closeEvent(self, event):
        self.save_state()
        event.accept()

    def trading_loop(self):
        now = datetime.datetime.now()
        market_start = now.replace(hour=9, minute=0, second=0, microsecond=0)
        market_end = now.replace(hour=15, minute=30, second=0, microsecond=0)
        
        if not (market_start <= now <= market_end):
             # Uncomment below to restrict trading to market hours
             # self.log("Market is closed. Skipping trading loop.")
             # return
             pass # Allow testing outside market hours for now

        self.log("Starting Trading Loop...")
        
        # 1. Data Retrieval
        data = self.kiwoom.get_current_price(self.target_stock)
        if data:
            price = data['price']
            self.log(f"Current Price of {data['name']}: {price}")
            
            # 2. Update History & Calc Indicators
            new_row = pd.DataFrame({'close': [price]}, index=[now])
            self.history_df = pd.concat([self.history_df, new_row])
            
            # Ensure we have enough data for RSI (e.g., 14 periods)
            rsi = None
            if len(self.history_df) >= 14:
                 self.history_df.ta.rsi(length=14, append=True)
                 rsi = self.history_df['RSI_14'].iloc[-1]
                 self.log(f"Current RSI: {rsi:.2f}")

            # 3. Market Order Execution logic
            # Condition: If RSI < 30 (Oversold) -> Buy
            if rsi and rsi < 30:
                self.log("RSI below 30. Attempting to Buy.")
                order_type = 1 # Buy
                quantity = 1
                
                res = self.kiwoom.send_order("send_buy_order", "0101", order_type, self.target_stock, quantity, 0, "03")
                
                if res == 0:
                    self.log("Order Sent Successfully")
                    # Update Table & DataFrame
                    row_position = self.table_trades.rowCount()
                    self.table_trades.insertRow(row_position)
                    self.table_trades.setItem(row_position, 0, QTableWidgetItem(data['name']))
                    self.table_trades.setItem(row_position, 1, QTableWidgetItem(str(price)))
                    self.table_trades.setItem(row_position, 2, QTableWidgetItem(str(quantity)))
                    self.table_trades.setItem(row_position, 3, QTableWidgetItem("Buy"))
                    
                    new_trade = pd.DataFrame([{
                        "code": self.target_stock,
                        "name": data['name'], 
                        "price": price, 
                        "quantity": quantity, 
                        "type": "Buy"
                    }])
                    self.active_trades = pd.concat([self.active_trades, new_trade], ignore_index=True)
            else:
                self.log("Conditions not met or insufficient data.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TradingBotWindow()
    window.show()
    sys.exit(app.exec_())

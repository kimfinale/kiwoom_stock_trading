import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QAxContainer import QAxWidget
from PyQt5.QtCore import QEventLoop
import time
import pandas as pd

class Kiwoom(QAxWidget):
    def __init__(self):
        super().__init__()
        self.setControl("KHOPENAPI.KHOpenAPICtrl.1")
        
        self.login_event_loop = QEventLoop()
        self.tr_event_loop = QEventLoop()
        
        self.OnEventConnect.connect(self._on_event_connect)
        self.OnReceiveTrData.connect(self._on_receive_tr_data)
        self.OnReceiveMsg.connect(self._on_receive_msg)
        self.OnReceiveChejanData.connect(self._on_receive_chejan_data)
        
        self.tr_data = None
        self.remaining_data = False
        self.msg = ""

    # --- Login & Connection ---
    def comm_connect(self):
        self.dynamicCall("CommConnect()")
        self.login_event_loop.exec_()

    def _on_event_connect(self, err_code):
        if err_code == 0:
            print("Connected to Kiwoom Server.")
        else:
            print(f"Connection Failed. Error Code: {err_code}")
        self.login_event_loop.exit()
    
    def get_login_info(self, tag):
        """
        tag: "ACCOUNT_CNT", "ACCNO", "USER_ID", "USER_NAME", "KEY_BSECGB", "FIREW_SECGB"
        """
        ret = self.dynamicCall("GetLoginInfo(QString)", tag)
        if tag == "ACCNO":
            return ret.split(';')[:-1]
        return ret

    # --- Transaction & Data ---
    def set_input_value(self, id, value):
        self.dynamicCall("SetInputValue(QString, QString)", id, value)

    def comm_rq_data(self, rqname, trcode, next, screen_no):
        self.dynamicCall("CommRqData(QString, QString, int, QString)", rqname, trcode, next, screen_no)
        self.tr_event_loop.exec_()

    def _on_receive_tr_data(self, screen_no, rqname, trcode, record_name, next, unused1, unused2, unused3, unused4):
        if next == '2':
            self.remaining_data = True
        else:
            self.remaining_data = False

        if rqname == "opt10001_req": # Basic Stock Info
            self._opt10001(trcode, record_name)
        elif rqname == "opw00001_req": # Deposit Info
            self._opw00001(trcode, record_name)
        elif rqname == "opw00018_req": # Account Balance
             self._opw00018(trcode, record_name)

        try:
            self.tr_event_loop.exit()
        except:
            pass

    def _on_receive_msg(self, screen_no, rqname, trcode, msg):
        self.msg = msg
        # print(f"[{rqname}] {msg}")

    def _on_receive_chejan_data(self, gubun, item_cnt, fid_list):
        # Real-time order execution data (to be implemented if needed)
        # gubun: 0 (Order/Exec), 1 (Balance)
        pass

    def get_comm_data(self, trcode, record_name, index, item_name):
        ret = self.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, record_name, index, item_name)
        return ret.strip()

    # --- Specific TR Handlers ---
    def get_current_price(self, code):
        """
        Returns (current_price, name)
        """
        self.set_input_value("종목코드", code)
        self.comm_rq_data("opt10001_req", "opt10001", 0, "0101")
        return self.tr_data

    def _opt10001(self, trcode, record_name):
        name = self.get_comm_data(trcode, record_name, 0, "종목명")
        price = self.get_comm_data(trcode, record_name, 0, "현재가").replace('+', '').replace('-', '')
        self.tr_data = {'name': name, 'price': int(price)}

    def get_deposit(self, account_no):
        self.set_input_value("계좌번호", account_no)
        self.set_input_value("비밀번호", "") # Empty for OpenApi (Should be saved in system tray)
        self.set_input_value("비밀번호입력매체구분", "00")
        self.set_input_value("조회구분", "2")
        self.comm_rq_data("opw00001_req", "opw00001", 0, "0201")
        return self.tr_data
    
    def _opw00001(self, trcode, record_name):
        deposit = self.get_comm_data(trcode, record_name, 0, "주문가능금액")
        self.tr_data = int(deposit)

    def get_account_evaluation(self, account_no):
        self.set_input_value("계좌번호", account_no)
        self.set_input_value("비밀번호", "")
        self.set_input_value("비밀번호입력매체구분", "00")
        self.set_input_value("조회구분", "2")
        self.comm_rq_data("opw00018_req", "opw00018", 0, "8100")
        return self.tr_data

    def _opw00018(self, trcode, record_name):
        # Single Data (Account Summary)
        total_buy_money = self.get_comm_data(trcode, record_name, 0, "총매입금액")
        total_eval_money = self.get_comm_data(trcode, record_name, 0, "총평가금액")
        total_profit_loss_money = self.get_comm_data(trcode, record_name, 0, "총평가손익금액")
        total_profit_loss_rate = self.get_comm_data(trcode, record_name, 0, "총수익률(%)")
        estimated_assets = self.get_comm_data(trcode, record_name, 0, "추정예탁자산")
        
        # Try to get Daily PnL. Note: The exact field name in opw00018 might vary or be '당일투자손익'
        # If not available, it effectively returns 0 or empty.
        daily_investment_pnl = self.get_comm_data(trcode, record_name, 0, "당일투자손익")
        daily_profit_loss_rate = self.get_comm_data(trcode, record_name, 0, "당일투자수익률(%)") # Or sometimes it's implied

        def safe_int(val):
            try:
                return int(val.strip())
            except:
                return 0
        
        def safe_float(val):
             try:
                 return float(val.strip())
             except:
                 return 0.0

        summary = {
            "total_buy": safe_int(total_buy_money),
            "total_eval": safe_int(total_eval_money),
            "total_profit_loss": safe_int(total_profit_loss_money),
            "total_rate": safe_float(total_profit_loss_rate),
            "estimated_assets": safe_int(estimated_assets),
            "daily_pnl": safe_int(daily_investment_pnl)
        }

        # Multi Data (Holdings)
        cnt = self.dynamicCall("GetRepeatCnt(QString, QString)", trcode, record_name)
        holdings = []
        for i in range(cnt):
            name = self.get_comm_data(trcode, record_name, i, "종목명")
            code = self.get_comm_data(trcode, record_name, i, "종목번호").strip()[1:] # Remove 'A'
            qty = self.get_comm_data(trcode, record_name, i, "보유수량")
            buy_price = self.get_comm_data(trcode, record_name, i, "매입가")
            current_price = self.get_comm_data(trcode, record_name, i, "현재가")
            eval_profit = self.get_comm_data(trcode, record_name, i, "평가손익")
            yield_rate = self.get_comm_data(trcode, record_name, i, "수익률(%)")
            
            holdings.append({
                "name": name,
                "code": code,
                "qty": int(qty),
                "buy_price": int(buy_price),
                "current_price": int(current_price),
                "eval_profit": int(eval_profit),
                "yield_rate": float(yield_rate)
            })
            
        self.tr_data = {"summary": summary, "holdings": holdings}

    # --- Order Sending ---
    def send_order(self, order_type, account_no, code, qty, price, order_no=""):
        """
        order_type: 1:New Buy, 2:New Sell, 3:Buy Cancel, 4:Sell Cancel, 5:Buy Modify, 6:Sell Modify
        price: 0 for market price
        """
        # transform order_type
        # 1: buy, 2: sell
        # Quotes: "시장가매수" if price=0 else "지정가"
        
        quote_type = "03" if price == 0 else "00" # 03: Market, 00: Limit
        
        # rqname, screen_no, acc_no, order_type, code, qty, price, quote_type, org_order_no
        res = self.dynamicCall("SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)", 
                         ["send_order_req", "0101", account_no, order_type, code, qty, price, quote_type, order_no])
        
        if res == 0:
            print(f"Order Sent: { 'Buy' if order_type==1 else 'Sell' } {code} {qty}ea")
            return True
        else:
            print(f"Order Failed. Error: {res}")
            return False

if __name__ == "__main__":
    app = QApplication(sys.argv)
    kiwoom = Kiwoom()
    kiwoom.comm_connect()
    
    # Test
    accs = kiwoom.get_login_info("ACCNO")
    print(f"Accounts: {accs}")
    
    # market = kiwoom.GetCodeListByMarket('0')
    # print(f"Kospi Total: {len(market)}")

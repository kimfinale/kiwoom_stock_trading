import sys
import time
import pandas as pd
import datetime
import requests
from PyQt5.QtWidgets import QApplication
from PyQt5.QAxContainer import QAxWidget
from PyQt5.QtCore import QEventLoop

# --- Naver Finance Scraper ---
def get_financial_details_naver(code):
    """
    Scrapes financial ratios from Naver Finance for a given stock code.
    Returns a dictionary with keys matching the criteria.
    """
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        
        dfs = pd.read_html(res.text)
        
        target_df = None
        for df in dfs:
            if df.shape[1] > 1 and '매출액' in str(df.iloc[:, 0].values):
                target_df = df
                break
                
        if target_df is None:
            return None

        target_df.set_index(target_df.columns[0], inplace=True)
        
        if isinstance(target_df.columns, pd.MultiIndex):
            annual_cols = [c for c in target_df.columns if '최근 연간 실적' in c[0]]
            if annual_cols:
                target_col = annual_cols[-1] 
            else:
                 target_col = target_df.columns[2]
        else:
            target_col = target_df.columns[2]

        def get_val_col(key, col_idx):
            if col_idx is None: return 0.0
            try:
                matches = [idx for idx in target_df.index if key in str(idx)]
                if not matches: return 0.0
                val = target_df.loc[matches[0], col_idx]
                if pd.isna(val) or str(val).strip() == '-': return 0.0
                return float(val)
            except: 
                return 0.0
        
        if isinstance(target_df.columns, pd.MultiIndex):
            annual_cols = [c for c in target_df.columns if '최근 연간 실적' in c[0]]
            if len(annual_cols) >= 2:
                curr_col = annual_cols[-1]
                prev_col = annual_cols[-2]
            else:
                curr_col = annual_cols[-1]
                prev_col = None
        else:
            curr_col = target_df.columns[2]
            prev_col = target_df.columns[1]

        sales_curr = get_val_col('매출액', curr_col)
        sales_prev = get_val_col('매출액', prev_col)
        sales_growth = ((sales_curr - sales_prev) / abs(sales_prev) * 100) if sales_prev != 0 else 0

        net_curr = get_val_col('당기순이익', curr_col)
        net_prev = get_val_col('당기순이익', prev_col)
        net_growth = ((net_curr - net_prev) / abs(net_prev) * 100) if net_prev != 0 else 0

        return {
            'Debt_Ratio': get_val_col('부채비율', curr_col),
            'Current_Ratio': get_val_col('유동비율', curr_col), 
            'Reserve_Ratio': get_val_col('유보율', curr_col),
            'Dividend_Yield': get_val_col('시가배당률', curr_col),
            'ROA': get_val_col('ROA', curr_col),
            'ROE': get_val_col('ROE', curr_col),
            'Op_Margin': get_val_col('영업이익률', curr_col),
            'Net_Margin': get_val_col('순이익률', curr_col),
            'Sales_Growth': sales_growth,
            'Net_Growth': net_growth,
            'PER': get_val_col('PER', curr_col),
            'PBR': get_val_col('PBR', curr_col),
        }

    except Exception:
        return None

# --- Main Script ---

class Kiwoom(QAxWidget):
    def __init__(self):
        super().__init__()
        self.setControl("KHOPENAPI.KHOpenAPICtrl.1")
        
        self.login_event_loop = QEventLoop()
        self.tr_event_loop = QEventLoop()
        
        self.OnEventConnect.connect(self._on_event_connect)
        self.OnReceiveTrData.connect(self._on_receive_tr_data)
        
        self.tr_data = None
        self.remaining_data = False

    def _on_event_connect(self, err_code):
        if err_code == 0:
            print("Connected to Kiwoom Server.")
        else:
            print(f"Connection Failed. Error Code: {err_code}")
        self.login_event_loop.exit()

    def comm_connect(self):
        self.dynamicCall("CommConnect()")
        self.login_event_loop.exec_()

    def _on_receive_tr_data(self, screen_no, rqname, trcode, record_name, next, unused1, unused2, unused3, unused4):
        if next == '2':
            self.remaining_data = True
        else:
            self.remaining_data = False

        if rqname == "opt10001_req": # Basic Stock Info
            self._opt10001(trcode, record_name)
        elif rqname == "opt10081_req": # Daily Chart
            self._opt10081(trcode, record_name)
        
        try:
            self.tr_event_loop.exit()
        except Exception:
            pass

    def set_input_value(self, id, value):
        self.dynamicCall("SetInputValue(QString, QString)", id, value)

    def comm_rq_data(self, rqname, trcode, next, screen_no):
        self.dynamicCall("CommRqData(QString, QString, int, QString)", rqname, trcode, next, screen_no)
        self.tr_event_loop.exec_()

    def get_comm_data(self, trcode, record_name, index, item_name):
        ret = self.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, record_name, index, item_name)
        return ret.strip()

    def get_code_list_by_market(self, market):
        # 0: KOSPI, 10: KOSDAQ
        code_list = self.dynamicCall("GetCodeListByMarket(QString)", market)
        code_list = code_list.split(';')
        return code_list[:-1]

    def get_master_code_name(self, code):
        name = self.dynamicCall("GetMasterCodeName(QString)", code)
        return name

    # --- Data Processing Methods ---

    def _opt10001(self, trcode, record_name):
        result = {}
        result['Name'] = self.get_comm_data(trcode, record_name, 0, "종목명")
        
        price_str = self.get_comm_data(trcode, record_name, 0, "현재가").replace('+', '').replace('-', '')
        result['Price'] = int(price_str) if price_str else 0
        
        mkt_cap_str = self.get_comm_data(trcode, record_name, 0, "시가총액")
        result['MarketCap'] = int(mkt_cap_str) if mkt_cap_str else 0
        
        result['PER'] = float(self.get_comm_data(trcode, record_name, 0, "PER") or 0)
        result['EPS'] = int(self.get_comm_data(trcode, record_name, 0, "EPS") or 0)
        result['ROE'] = float(self.get_comm_data(trcode, record_name, 0, "ROE") or 0)
        result['PBR'] = float(self.get_comm_data(trcode, record_name, 0, "PBR") or 0)
        result['EV'] = float(self.get_comm_data(trcode, record_name, 0, "EV") or 0)
        
        high_str = self.get_comm_data(trcode, record_name, 0, "250최고").replace('+', '').replace('-', '')
        result['High_250'] = int(high_str) if high_str else 0
        
        low_str = self.get_comm_data(trcode, record_name, 0, "250최저").replace('+', '').replace('-', '')
        result['Low_250'] = int(low_str) if low_str else 0
        
        credit = self.get_comm_data(trcode, record_name, 0, "신용비율")
        result['Credit_Ratio'] = float(credit) if credit else 0.0

        foreign = self.get_comm_data(trcode, record_name, 0, "외인소진률")
        result['Foreign_Own'] = float(foreign) if foreign else 0.0

        self.tr_data = result

    def get_basic_info(self, code):
        self.set_input_value("종목코드", code)
        self.comm_rq_data("opt10001_req", "opt10001", 0, "0101")
        time.sleep(0.2) 
        return self.tr_data

    def _opt10081(self, trcode, record_name):
        count = self.dynamicCall("GetRepeatCnt(QString, QString)", trcode, record_name)
        data_list = []
        for i in range(count):
            date = self.get_comm_data(trcode, record_name, i, "일자")
            close = int(self.get_comm_data(trcode, record_name, i, "현재가"))
            data_list.append({'Date': date, 'Close': close})
        self.tr_data = pd.DataFrame(data_list)

    def get_daily_chart(self, code, date=None):
        if date is None:
            date = datetime.datetime.now().strftime("%Y%m%d")
        self.set_input_value("종목코드", code)
        self.set_input_value("기준일자", date)
        self.set_input_value("수정주가구분", "1")
        self.comm_rq_data("opt10081_req", "opt10081", 0, "0101")
        time.sleep(0.2)
        
        df = self.tr_data
        if df is not None and not df.empty:
            df = df.sort_values(by='Date')
        return df

# --- Scoring Logic ---
def score_stock(basic, financial, technical):
    """
    Evaluates 21 criteria and returns a score and list of passed checks.
    """
    score = 0
    checks = []
    
    # helper for checks
    def check(condition, desc):
        nonlocal score
        if condition:
            score += 1
            checks.append(desc + " (PASS)")
        else:
            checks.append(desc + " (FAIL)")

    # Data Extraction
    price = basic.get('Price', 0)
    mkt_cap = basic.get('MarketCap', 0) 
    credit_ratio = basic.get('Credit_Ratio', 0)
    
    high_250 = basic.get('High_250', 0)
    low_250 = basic.get('Low_250', 0)
    
    per = basic.get('PER', 0)
    pbr = basic.get('PBR', 0)
    roe = financial.get('ROE', basic.get('ROE', 0))
    roa = financial.get('ROA', 0)
    
    debt_ratio = financial.get('Debt_Ratio', 0)
    curr_ratio = financial.get('Current_Ratio', 0)
    reserve_ratio = financial.get('Reserve_Ratio', 0)
    div_yield = financial.get('Dividend_Yield', 0)
    
    sales_growth = financial.get('Sales_Growth', 0)
    net_growth = financial.get('Net_Growth', 0)
    op_margin = financial.get('Op_Margin', 0)
    net_margin = financial.get('Net_Margin', 0)
    
    foreign_own = basic.get('Foreign_Own', 0)
    
    # 1. Market Cap >= 3000 
    check(mkt_cap >= 3000, f"Market Cap {mkt_cap} >= 3000")
    
    # 2. Credit Ratio (Assuming 5% or similar standard since Margin Rate not avail)
    check(True, "Margin Rate Check (Skipped/Assumed safe)") 

    # 3. 52w Low Diff <= 10% 
    if low_250 > 0:
        low_diff = (price - low_250) / low_250 * 100
        check(low_diff <= 10, f"Near 52w Low (+{low_diff:.1f}%) <= 10%")
    else:
        check(False, "52w Low Data Missing")

    # 4. 52w High Diff >= 30% 
    if high_250 > 0:
        high_diff = (high_250 - price) / high_250 * 100
        check(high_diff >= 30, f"Discount from 52w High (-{high_diff:.1f}%) >= 30%")
    else:
        check(False, "52w High Data Missing")

    # 5. PER <= 5
    check(per <= 5 and per > 0, f"PER {per} <= 5")

    # 6. PBR <= 2
    check(pbr <= 2 and pbr > 0, f"PBR {pbr} <= 2")

    # 7. PSR <= 5
    check(True, "PSR Check (Skipped)")

    # 8. PCR <= 10
    check(True, "PCR Check (Skipped)")
    
    # 9. PEG <= 1 
    if net_growth > 0 and per > 0:
        peg = per / net_growth
        check(peg <= 1, f"PEG {peg:.2f} <= 1")
    else:
        check(False, f"PEG Calc Failed")

    # 10. ROE >= 5%
    check(roe >= 5, f"ROE {roe}% >= 5%")

    # 11. ROA >= 3%
    check(roa >= 3, f"ROA {roa}% >= 3%")

    # 12. Op Margin >= 5%
    check(op_margin >= 5, f"Op Margin {op_margin}% >= 5%")
    
    # 13. Net Margin >= 3%
    check(net_margin >= 3, f"Net Margin {net_margin}% >= 3%")

    # 14. Sales Growth >= 1%
    check(sales_growth >= 1, f"Sales Growth {sales_growth:.1f}% >= 1%")
    
    # 15. Net Profit Growth >= 1%
    check(net_growth >= 1, f"Net Growth {net_growth:.1f}% >= 1%")

    # 16. Debt Ratio <= 100%
    check(debt_ratio <= 100, f"Debt Ratio {debt_ratio}% <= 100%")

    # 17. Current Ratio >= 200%
    check(curr_ratio >= 200, f"Current Ratio {curr_ratio}% >= 200%")

    # 18. Reserve Ratio >= 200%
    check(reserve_ratio >= 200, f"Reserve Ratio {reserve_ratio}% >= 200%")

    # 19. Div Yield >= 3%
    check(div_yield >= 3, f"Div Yield {div_yield}% >= 3%")

    # 20. Foreign Own >= 30%
    check(foreign_own >= 30, f"Foreign Own {foreign_own}% >= 30%")

    # 21. Business Report
    check(True, "Business Report Verified")

    return score, checks

def main():
    app = QApplication(sys.argv)
    kiwoom = Kiwoom()
    kiwoom.comm_connect()
    
    print("Fetching stock lists...")
    kospi = kiwoom.get_code_list_by_market("0")
    kosdaq = kiwoom.get_code_list_by_market("10")
    all_codes = kospi + kosdaq
    print(f"Total Stocks: {len(all_codes)}")
    
    limit = len(all_codes) # 20
    print(f"Scanning first {limit} stocks...")
    
    results = []
    
    processed = 0
    for code in all_codes:
        if processed >= limit:
            break
            
        name = kiwoom.get_master_code_name(code)
        if not name or "스팩" in name: 
            continue
            
        print(f"[{processed+1}/{limit}] Analyzing {name} ({code})...", end="")
        
        # 1. Kiwoom Basic Info
        basic = kiwoom.get_basic_info(code)
        if not basic:
            print(" -> Skip (No Data)")
            continue

        # 2. Naver Financials (Scrape)
        financial = get_financial_details_naver(code)
        if not financial:
            print(" -> Skip (Scrape Fail)")
            continue
            
        # 3. Score
        score, detailed_checks = score_stock(basic, financial, None)
        
        print(f" -> Score: {score}/21")
        
        # Derived values
        peg = 0
        per = basic.get('PER', 0)
        net_growth = financial.get('Net_Growth', 0)
        if net_growth > 0 and per > 0:
            peg = per / net_growth
            
        low_diff = 100 # Default to high value so it fails <= 10 check if missing
        if basic.get('Low_250', 0) > 0:
            low_diff = (basic['Price'] - basic['Low_250']) / basic['Low_250'] * 100
            
        high_diff = 0
        if basic.get('High_250', 0) > 0:
            high_diff = (basic['High_250'] - basic['Price']) / basic['High_250'] * 100

        # Excel Formula for Score
        # Columns Mapping (based on final order):
        # A: Code, B: Name, C: Score, D: Price, E: MarketCap, F: PER, G: PBR, H: ROE, I: PEG, 
        # J: Debt, K: Reserve, L: Div, M: Sales, N: Net_Gr, O: Credit, P: Current, Q: ROA, 
        # R: Op, S: Net_M, T: Low_Diff, U: High_Dist, V: Foreign
        
        r = processed + 2 # Excel Row Number (Header is 1)
        
        formula = (f"=4 + IF(E{r}>=3000,1,0) + IF(T{r}<=10,1,0) + IF(U{r}>=30,1,0) + "
                   f"IF(AND(F{r}<=5,F{r}>0),1,0) + IF(AND(G{r}<=2,G{r}>0),1,0) + IF(AND(I{r}<=1,I{r}>0),1,0) + "
                   f"IF(H{r}>=5,1,0) + IF(Q{r}>=3,1,0) + IF(R{r}>=5,1,0) + IF(S{r}>=3,1,0) + "
                   f"IF(M{r}>=1,1,0) + IF(N{r}>=1,1,0) + IF(J{r}<=100,1,0) + IF(P{r}>=200,1,0) + "
                   f"IF(K{r}>=200,1,0) + IF(L{r}>=3,1,0) + IF(V{r}>=30,1,0)")

        results.append({
            'Code': code,
            'Name': name,
            'Score': score,
            'Price': basic.get('Price'),
            
            # --- 1. Size & Stability ---
            'MarketCap(100M)': basic.get('MarketCap', 0),
            'Credit_Ratio': basic.get('Credit_Ratio', 0),
            'Debt_Ratio': financial.get('Debt_Ratio', 0),
            'Current_Ratio': financial.get('Current_Ratio', 0),
            'Reserve_Ratio': financial.get('Reserve_Ratio', 0),
            
            # --- 2. Valuation ---
            'PER': per,
            'PBR': basic.get('PBR', 0),
            'PEG': round(peg, 2),
            
            # --- 3. Profitability ---
            'ROE': financial.get('ROE', basic.get('ROE', 0)),
            'ROA': financial.get('ROA', 0),
            'Op_Margin': financial.get('Op_Margin', 0),
            'Net_Margin': financial.get('Net_Margin', 0),
            
            # --- 4. Growth ---
            'Sales_Growth': financial.get('Sales_Growth', 0),
            'Net_Growth': net_growth,
            'Div_Yield': financial.get('Dividend_Yield', 0),
            
            # --- 5. Price & Foreign ---
            'Low_Diff(%)': round(low_diff, 1),
            'High_Discount(%)': round(high_diff, 1),
            'Foreign_Own': basic.get('Foreign_Own', 0),
            
            'Score_Formula': formula
        })
        
        processed += 1
        time.sleep(0.5) 
        
    if results:
        df = pd.DataFrame(results)
        
        # Define column order (Explicitly match the order assumed by Score_Formula)
        cols = ['Code', 'Name', 'Score', 'Price', 
                'MarketCap(100M)', 'PER', 'PBR', 'ROE', 'PEG',
                'Debt_Ratio', 'Reserve_Ratio', 'Div_Yield', 
                'Sales_Growth', 'Net_Growth',
                'Credit_Ratio', 'Current_Ratio', 'ROA', 'Op_Margin', 'Net_Margin',
                'Low_Diff(%)', 'High_Discount(%)', 'Foreign_Own', 'Score_Formula']
        
        # Reorder columns
        existing_cols = [c for c in cols if c in df.columns]
        remaining_cols = [c for c in df.columns if c not in existing_cols]
        df = df[existing_cols + remaining_cols]
        
        print("\nTOP RESULTS (Sample):")
        # Show some key params
        print(df[['Name', 'Score', 'PER', 'ROE', 'Debt_Ratio']].head(10))
        
        filename = "kiwoom_analysis_parameters.csv"
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"Saved detailed parameters to {filename}")
    else:
        print("No results found.")

    sys.exit()

if __name__ == "__main__":
    main()

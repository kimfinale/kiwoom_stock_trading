from pykiwoom.kiwoom import *

kiwoom = Kiwoom()
kiwoom.CommConnect(block=True)

kospi = kiwoom.GetCodeListByMarket('0')
kosdaq = kiwoom.GetCodeListByMarket('10')
etf = kiwoom.GetCodeListByMarket('8')

print(len(kospi), kospi)
print(len(kosdaq), kosdaq)
print(len(etf), etf)

# get name by code
name = kiwoom.GetMasterCodeName("005930")
print(name)

# get connect state
state = kiwoom.GetConnectState()
if state == 0:
    print("미연결")
elif state == 1:
    print("연결완료")

# get stock count
stock_cnt = kiwoom.GetMasterListedStockCnt("005930")
print("삼성전자 상장주식수: ", stock_cnt)

# get last price
last_price = kiwoom.GetMasterLastPrice("005930")
print(int(last_price))
print(type(last_price))

# get theme group list
import pprint
group = kiwoom.GetThemeGroupList(1)
pprint.pprint(group)


tickers = kiwoom.GetThemeGroupCode('212')
print(tickers)
for ticker in tickers:
    name = kiwoom.GetMasterCodeName(ticker)
    print(ticker, name)

# 주식계좌
accounts = kiwoom.GetLoginInfo("ACCNO")
stock_account = accounts[1]

# Samsung Electronics, 10 shares, market price order buy
kiwoom.SendOrder("시장가매수", "0101", stock_account, 1, "005930", 10, 0, "03", "")

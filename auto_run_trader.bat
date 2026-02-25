@echo off
cd /d "C:\Users\jonghoon.kim\Workspace\Antigravity\kiwoom_stock_trading"
call conda activate py38_32bit

echo START | python real_time_trader.py

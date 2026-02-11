import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import json

# Pre-mock kiwoom_api to avoid import errors or side effects if PyQt5 is missing/broken
mock_kiwoom_module = MagicMock()
sys.modules['kiwoom_api'] = mock_kiwoom_module

# Also mock PyQt5 if needed, though strictly speaking if kiwoom_api is mocked, generate_portfolio_json only imports QApp from PyQt5.QtWidgets
mock_pyqt5 = MagicMock()
sys.modules['PyQt5'] = mock_pyqt5
sys.modules['PyQt5.QtWidgets'] = mock_pyqt5
sys.modules['PyQt5.QAxContainer'] = MagicMock()

# Now import the target script
# We need to make sure generate_portfolio_json is imported AFTER mocking
if 'generate_portfolio_json' in sys.modules:
    del sys.modules['generate_portfolio_json']

import generate_portfolio_json

class TestGeneratePortfolio(unittest.TestCase):
    
    def setUp(self):
        if os.path.exists("portfolio.json"):
            os.remove("portfolio.json")

    def tearDown(self):
        if os.path.exists("portfolio.json"):
            os.remove("portfolio.json")

    @patch('generate_portfolio_json.Kiwoom')
    @patch('generate_portfolio_json.QApplication')
    def test_generate_portfolio(self, mock_qapp, mock_kiwoom_cls):
        # Setup Mock Kiwoom instance
        mock_kiwoom = mock_kiwoom_cls.return_value
        
        # Mock get_login_info
        mock_kiwoom.get_login_info.return_value = ["ACC1", "ACC2"]
        
        # Mock get_deposit (opw00001)
        # Side effect to handle multiple calls
        # Returns tr_data property value logic
        # Since the script calls get_deposit then accesses .tr_data, we need to set .tr_data when get_deposit is called.
        
        def get_deposit_side_effect(acc):
            if acc == "ACC1":
                mock_kiwoom.tr_data = 10000000 # 10M Cash
            elif acc == "ACC2":
                mock_kiwoom.tr_data = 5000000 # 5M Cash
        
        mock_kiwoom.get_deposit.side_effect = get_deposit_side_effect
        
        # Mock get_account_evaluation (opw00018)
        # Returns dict
        def get_eval_side_effect(acc):
            if acc == "ACC1":
                return {
                    "summary": {
                        "total_buy": 50000000,
                        "total_eval": 60000000, # Eval (Stocks)
                        "total_profit_loss": 10000000,
                        "total_rate": 20.0,
                        "estimated_assets": 70000000, # Approx Total Value
                        "daily_pnl": 500000
                    },
                    "holdings": [
                        {
                            "name": "Samsung",
                            "code": "005930",
                            "qty": 100,
                            "buy_price": 50000,
                            "current_price": 60000,
                            "eval_profit": 1000000,
                            "yield_rate": 20.0
                        }
                    ]
                }
            elif acc == "ACC2":
                return {
                    "summary": {
                        "total_buy": 20000000,
                        "total_eval": 15000000,
                        "total_profit_loss": -5000000,
                        "total_rate": -25.0,
                        "estimated_assets": 20000000, 
                        "daily_pnl": -100000
                    },
                    "holdings": []
                }
        
        mock_kiwoom.get_account_evaluation.side_effect = get_eval_side_effect

        # Run main
        generate_portfolio_json.main()
        
        # Check if file exists
        self.assertTrue(os.path.exists("portfolio.json"))
        
        # Read file and verify content
        with open("portfolio.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            
        print("\nGenerated JSON Content:")
        print(json.dumps(data, indent=2, ensure_ascii=False))

        # Verify Summary
        # Total Value = 70M + 20M = 90M
        self.assertEqual(data["summary"]["total_value"], 90000000)
        # Total Cash = 10M + 5M = 15M
        self.assertEqual(data["summary"]["cash"], 15000000)
        # Total PnL = 10M - 5M = 5M
        self.assertEqual(data["summary"]["total_pnl"], 5000000)
        
        # Verify Accounts
        self.assertEqual(len(data["accounts"]), 2)


if __name__ == '__main__':
    unittest.main()

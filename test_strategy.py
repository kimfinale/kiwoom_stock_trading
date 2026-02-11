import unittest
from unittest.mock import MagicMock
import os
import json
import sys
from state_manager import StateManager
from strategy_executor import StrategyExecutor

class MockKiwoom:
    def __init__(self):
        self.price = 10000
        
    def get_current_price(self, code):
        return {'name': 'Samsung', 'price': self.price}
        
    def send_order(self, *args):
        return True

class TestStrategy(unittest.TestCase):
    def setUp(self):
        self.config = {
            "accounts": {
                "Account1": "ACC1", "Account2": "ACC2", 
                "Account3": "ACC3", "Account4": "ACC4", "Account5": "ACC5"
            },
            "stocks": [{"code": "005930", "name": "Samsung"}],
            "strategy": {
                "P": 0.1, "D": 0.05, "R": 0.1,
                "allocation_ratio": {
                    "Account1": 0.2, "Account2": 0.2, "Account3": 0.2, "Account4": 0.2, "Account5": 0.2
                }
            },
            "total_capital": 1000000,
            "dry_run": True
        }
        
        self.test_state_file = "test_trade_state.json"
        if os.path.exists(self.test_state_file):
            os.remove(self.test_state_file)
            
        self.state_manager = StateManager(self.test_state_file)
        self.kiwoom = MockKiwoom()
        self.executor = StrategyExecutor(self.kiwoom, self.state_manager, self.config)

    def tearDown(self):
        if os.path.exists(self.test_state_file):
            os.remove(self.test_state_file)

    def test_account_1_buy_sell(self):
        print("\n--- Test Account 1 Buy/Sell ---")
        self.kiwoom.price = 10000
        self.executor.execute_step()
        
        trades = self.state_manager.get_account_history("Account1")
        self.assertEqual(len(trades), 1, "Should have 1 trade (Buy)")
        self.assertEqual(trades[0]["price"], 10000)
        
        # Increase price to 10500 (5% gain) - No Sell (Target 11000)
        self.kiwoom.price = 10500
        self.executor.execute_step()
        self.assertEqual(len(self.state_manager.get_open_positions("Account1", "005930")), 1, "Should still hold position")
        
        # Increase price to 11100 (11% gain) - Sell
        self.kiwoom.price = 11100
        self.executor.execute_step()
        
        open_pos = self.state_manager.get_open_positions("Account1", "005930")
        self.assertEqual(len(open_pos), 0, "Should have sold position")
        
        history = self.state_manager.get_account_history("Account1")
        self.assertEqual(history[0]["status"], "CLOSED")
        self.assertEqual(history[0]["sell_price"], 11100)

    def test_account_2_logic(self):
        print("\n--- Test Account 2 Logic ---")
        # Acc 1 accumulates 4 shares
        prices = [10000, 10000, 10000, 10000] 
        for p in prices:
            self.kiwoom.price = p
            self.executor.execute_step()
            
        acc1_history = self.state_manager.get_account_history("Account1")
        self.assertEqual(len(acc1_history), 4)
        
        # Batch 1 Avg = 10000. Target Buy = 9500 (1-0.05).
        
        # Price 9600 - No Buy
        self.kiwoom.price = 9600
        self.executor.execute_step()
        acc2_history = self.state_manager.get_account_history("Account2")
        self.assertEqual(len(acc2_history), 0, "Should not buy at 9600")
        
        # Price 9500 - Buy
        self.kiwoom.price = 9500
        self.executor.execute_step()
        acc2_history = self.state_manager.get_account_history("Account2")
        self.assertEqual(len(acc2_history), 1, "Should buy at 9500")
        
        # Check metadata
        expected_target_sell = 10000 * (1 - 0.05) * (1 + 0.1) # 10450
        self.assertAlmostEqual(acc2_history[0]["target_sell_price"], expected_target_sell, places=2)
        
        # Sell Logic
        # Target Sell = 10450.
        self.kiwoom.price = 10500
        self.executor.execute_step()
        
        open_pos = self.state_manager.get_open_positions("Account2", "005930")
        self.assertEqual(len(open_pos), 0, "Should have sold Acc2 position")
        
        history = self.state_manager.get_account_history("Account2")
        self.assertEqual(history[0]["status"], "CLOSED")

if __name__ == '__main__':
    with open("test_result.txt", "w") as f:
        runner = unittest.TextTestRunner(stream=f, verbosity=2)
        unittest.main(testRunner=runner, exit=False)

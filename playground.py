# playground.py
from account_manager import create_split_account

# 1. SETUP YOUR INPUTS
total_money = 100000000  # 100 Million KRW
num_subs = 5
proportions = [0.4, 0.15, 0.15, 0.1, 0.1]
strategies = [
    {"account_id": "Acc_1", "type": "LEADER", "R": 0.1, "D": None},
    {"account_id": "Acc_2", "type": "FOLLOWER", "R": 0.03, "D": 0.03},
    {"account_id": "Acc_3", "type": "FOLLOWER", "R": 0.03, "D": 0.03},
    {"account_id": "Acc_4", "type": "FOLLOWER", "R": 0.03, "D": 0.03},
    {"account_id": "Acc_5", "type": "FOLLOWER", "R": 0.03, "D": 0.03},
]

# 2. RUN THE FACTORY
accounts = create_split_account(total_money, num_subs, proportions, strategies)

# 3. INSPECT THE RESULTS
print(f"{'Account ID':<10} | {'Principal':<15} | {'Strategy Detail'}")
print("-" * 60)
for acc in accounts:
    # See exactly what's inside each object
    print(f"{acc.account_id:<10} | {acc.principal:15,.0f} | {acc.strategy_config}")



# If you want to add a whole new strategy (like the ones in your 
# config.json
# ) without erasing your existing Samsung accounts:

from account_manager import load_accounts, save_accounts, create_split_account
# 1. Load existing
accounts = load_accounts()
# 2. Create a new set of split accounts (e.g., a 3-way split)
new_group = create_split_account(
    total_money=30000000,
    num_sub_accounts=3,
    proportions=[0.4, 0.3, 0.3],
    strategy_configs=[{"suffix": "1"}, {"suffix": "2"}, {"suffix": "3"}],
    stock_code="005380" # Hyundai Motor
)
# 3. Use .extend() to add the whole list
accounts.extend(new_group)
# 4. Save
save_accounts(accounts)
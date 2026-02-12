import json

stocks = [
    {"code": "005930", "name": "Samsung"},
    {"code": "032640", "name": "LGUplus"},
    {"code": "259960", "name": "Krafton"},
    {"code": "030200", "name": "KT"},
    {"code": "015760", "name": "KEPCO"},
    {"code": "000660", "name": "SKHynix"},
    {"code": "086280", "name": "HyundaiGlovis"},
    {"code": "064350", "name": "HyundaiRotem"},
    {"code": "071050", "name": "KoreaInv"}, # Global Investment
    {"code": "251270", "name": "Netmarble"}
]

total_capital = 100000000
allocation_per_stock = 0.1 # 10%

strategies = []
for stock in stocks:
    strategies.append({
        "id": stock["name"],
        "stock_code": stock["code"],
        "stock_name": stock["name"],
        "total_allocation_percent": allocation_per_stock,
        "check_interval_minutes": 5,
        "accounts": [
            { 
                "suffix": "1", 
                "ratio": 0.40, 
                "strategy_type": "LEADER", 
                "params": { "target_profit": 0.10 } 
            },
            { 
                "suffix": "2", 
                "ratio": 0.15, 
                "strategy_type": "FOLLOWER", 
                "params": { "dip": 0.01, "target_profit": 0.03 } 
            },
            { 
                "suffix": "3", 
                "ratio": 0.15, 
                "strategy_type": "FOLLOWER", 
                "params": { "dip": 0.02, "target_profit": 0.03 } 
            },
            { 
                "suffix": "4", 
                "ratio": 0.15, 
                "strategy_type": "FOLLOWER", 
                "params": { "dip": 0.03, "target_profit": 0.03 } 
            },
            { 
                "suffix": "5", 
                "ratio": 0.15, 
                "strategy_type": "FOLLOWER", 
                "params": { "dip": 0.04, "target_profit": 0.03 } 
            }
        ]
    })

config = {
    "total_capital": total_capital,
    "real_account_id": "8119599511",
    "dry_run": True,
    "strategies": strategies
}

with open("config.json", "w", encoding="utf-8") as f:
    json.dump(config, f, indent=4, ensure_ascii=False)

print("config.json generated successfully.")

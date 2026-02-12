import json
import os

def check_follower_prices():
    config_path = 'config.json'
    state_path = 'trade_state.json'

    if not os.path.exists(config_path):
        print(f"Error: {config_path} not found.")
        return
    
    if not os.path.exists(state_path):
        print(f"Error: {state_path} not found.")
        return

    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    with open(state_path, 'r', encoding='utf-8') as f:
        state_data = json.load(f)

    accounts_map = {acc['account_id']: acc for acc in state_data}
    
    print("\n" + "=" * 105)
    print(f"{'Stock Name':<20} | {'Follower':<12} | {'Condition':<20} | {'Leader Status':<18} | {'Est. Target Price'}")
    print("-" * 105)

    for strategy in config.get('strategies', []):
        s_id = strategy['id']
        code = strategy['stock_code']
        stock_name = strategy['stock_name']
        
        leader_acc_id = None
        for acc_cfg in strategy['accounts']:
            if acc_cfg['strategy_type'] == 'LEADER':
                leader_acc_id = f"{s_id}_{acc_cfg['suffix']}"
                break
        
        if not leader_acc_id or leader_acc_id not in accounts_map:
            print(f"{stock_name:<20} | Leader {leader_acc_id} not found in state.")
            continue

        leader_acc = accounts_map[leader_acc_id]
        leader_buys = [t for t in leader_acc.get('history', []) 
                       if t.get('code') == code and t.get('action') == 'BUY']
        
        batch_size = 4
        
        for acc_cfg in strategy['accounts']:
            if acc_cfg['strategy_type'] == 'FOLLOWER':
                acc_id = f"{s_id}_{acc_cfg['suffix']}"
                dip = acc_cfg['params'].get('dip', 0)
                
                follower_acc = accounts_map.get(acc_id)
                if not follower_acc: continue

                follower_buys = [t for t in follower_acc.get('history', []) 
                                if t.get('code') == code and t.get('action') == 'BUY']
                
                next_batch_idx = len(follower_buys)
                
                # Determine Leader Context
                num_full_batches = len(leader_buys) // batch_size
                
                if next_batch_idx < num_full_batches:
                    # Target is LOCKED because the leader batch is full
                    start = next_batch_idx * batch_size
                    end = (next_batch_idx + 1) * batch_size
                    batch_slice = leader_buys[start:end]
                    avg_price = sum(t['price'] for t in batch_slice) / len(batch_slice)
                    target_price = avg_price * (1 - dip)
                    
                    status = f"LOCKED (Batch {next_batch_idx+1})"
                    print(f"{stock_name:<20} | {acc_id:<12} | {dip*100:>4.1f}% below Ldr | {status:<18} | {int(target_price):,} KRW")
                else:
                    # Target is ESTIMATED because the leader batch is still growing
                    start = next_batch_idx * batch_size
                    batch_slice = leader_buys[start:]
                    
                    if batch_slice:
                        avg_price = sum(t['price'] for t in batch_slice) / len(batch_slice)
                        est_target = avg_price * (1 - dip)
                        status = f"In Progress ({len(batch_slice)}/4)"
                        print(f"{stock_name:<20} | {acc_id:<12} | {dip*100:>4.1f}% below Ldr | {status:<18} | {int(est_target):,} KRW (est)")
                    else:
                        status = "Waiting for Ldr"
                        print(f"{stock_name:<20} | {acc_id:<12} | {dip*100:>4.1f}% below Ldr | {status:<18} | -")

    print("-" * 105)
    print("Notes: 'LOCKED' means the price is final. 'In Progress' is an estimate based on current leader buy prices.")
    print("=" * 105 + "\n")

if __name__ == "__main__":
    check_follower_prices()

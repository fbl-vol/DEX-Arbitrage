#!/usr/bin/env python3
"""
DEX Arbitrage Simulation Script
Simulates arbitrage opportunities between two Uniswap V2-style AMM pools.
Read-only, no transaction execution.
"""

import json
from decimal import Decimal, getcontext
from typing import Tuple, Optional
import sys

try:
    from web3 import Web3
    import numpy as np
except ImportError:
    print("Error: Required libraries not installed.")
    print("Please run: pip install web3 eth-abi numpy")
    sys.exit(1)

# Set decimal precision for accurate calculations
getcontext().prec = 50

# ============================================================================
# CONFIGURATION SECTION - Modify these values as needed
# ============================================================================

# Demo mode - set to True to run with mock data (no RPC connection needed)
DEMO_MODE = False

# RPC endpoint (public Arbitrum RPC)
RPC_URL = "https://arb1.arbitrum.io/rpc"

# Pool addresses (example: WETH/USDC pools on Arbitrum)
# Pool 1: Uniswap V2 style pool
POOL_1_ADDRESS = "0x905dfCD5649217c42684f23958568e533C711Aa3"  # Example pool
# Pool 2: Another DEX pool with same token pair
POOL_2_ADDRESS = "0x8e295789c9465487074a65b1ae9Ce0351172393f"  # Example pool

# Token addresses (WETH and USDC on Arbitrum)
TOKEN_A_ADDRESS = "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1"  # WETH
TOKEN_B_ADDRESS = "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"  # USDC

# Token decimals
TOKEN_A_DECIMALS = 18  # WETH
TOKEN_B_DECIMALS = 6   # USDC

# Fee tier (in basis points, e.g., 30 = 0.3%)
FEE_BPS = 30  # 0.3% fee typical for Uniswap V2

# Sweep parameters for finding optimal trade size
MIN_INPUT_AMOUNT = 0.01  # Minimum amount of Token A to try
MAX_INPUT_AMOUNT = 10.0  # Maximum amount of Token A to try
SWEEP_STEPS = 100        # Number of steps in the sweep

# Optional: Gas cost estimation (in ETH, for breakeven calculation)
GAS_COST_ETH = 0.001  # Placeholder for gas cost

# Optional: CSV output file
CSV_OUTPUT_FILE = "arbitrage_results.csv"
ENABLE_CSV_OUTPUT = False  # Set to True to enable CSV logging

# ============================================================================
# MINIMAL ABI DEFINITIONS
# ============================================================================

# Minimal ABI for Uniswap V2 Pair contract
PAIR_ABI = json.dumps([
    {
        "constant": True,
        "inputs": [],
        "name": "getReserves",
        "outputs": [
            {"internalType": "uint112", "name": "_reserve0", "type": "uint112"},
            {"internalType": "uint112", "name": "_reserve1", "type": "uint112"},
            {"internalType": "uint32", "name": "_blockTimestampLast", "type": "uint32"}
        ],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "token0",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "token1",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    }
])

# ============================================================================
# CORE FUNCTIONS
# ============================================================================

def get_web3_connection(rpc_url: str) -> Web3:
    """
    Establish connection to RPC endpoint.
    """
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise ConnectionError(f"Failed to connect to RPC: {rpc_url}")
    return w3


def get_pool_reserves(
    w3: Web3,
    pool_address: str,
    token_a: str,
    token_b: str
) -> Tuple[int, int, int]:
    """
    Read pool reserves using getReserves() and determine token order.
    Returns (reserve_a, reserve_b, block_number) where reserve_a is for token_a.
    """
    pool_contract = w3.eth.contract(
        address=Web3.to_checksum_address(pool_address),
        abi=json.loads(PAIR_ABI)
    )
    
    # Get current block number
    block_number = w3.eth.block_number
    
    # Call getReserves
    reserves = pool_contract.functions.getReserves().call()
    reserve0, reserve1, timestamp = reserves
    
    # Get token order in the pool
    token0 = pool_contract.functions.token0().call()
    token1 = pool_contract.functions.token1().call()
    
    # Determine which reserve corresponds to which token
    token_a_checksum = Web3.to_checksum_address(token_a)
    token_b_checksum = Web3.to_checksum_address(token_b)
    
    if token0.lower() == token_a_checksum.lower():
        reserve_a, reserve_b = reserve0, reserve1
    elif token1.lower() == token_a_checksum.lower():
        reserve_a, reserve_b = reserve1, reserve0
    else:
        raise ValueError(f"Token {token_a} not found in pool {pool_address}")
    
    return reserve_a, reserve_b, block_number


def calculate_amount_out(
    amount_in: int,
    reserve_in: int,
    reserve_out: int,
    fee_bps: int = 30
) -> int:
    """
    Calculate output amount using constant-product formula with fees.
    Based on Uniswap V2 formula:
    amountOut = (amountIn * (10000 - fee) * reserveOut) / (reserveIn * 10000 + amountIn * (10000 - fee))
    
    Args:
        amount_in: Input amount (in token's smallest unit)
        reserve_in: Input token reserve
        reserve_out: Output token reserve
        fee_bps: Fee in basis points (e.g., 30 = 0.3%)
    
    Returns:
        Output amount (in token's smallest unit)
    """
    if amount_in <= 0 or reserve_in <= 0 or reserve_out <= 0:
        return 0
    
    # Calculate with fee (fee_bps out of 10000)
    fee_multiplier = 10000 - fee_bps
    amount_in_with_fee = amount_in * fee_multiplier
    numerator = amount_in_with_fee * reserve_out
    denominator = (reserve_in * 10000) + amount_in_with_fee
    
    amount_out = numerator // denominator
    return amount_out


def simulate_arbitrage(
    amount_in_token_a: float,
    pool1_reserve_a: int,
    pool1_reserve_b: int,
    pool2_reserve_a: int,
    pool2_reserve_b: int,
    fee_bps: int,
    token_a_decimals: int,
    token_b_decimals: int
) -> Tuple[float, float, float, str]:
    """
    Simulate arbitrage in both directions and return the most profitable:
    Direction 1: A → B in Pool 1, then B → A in Pool 2
    Direction 2: A → B in Pool 2, then B → A in Pool 1
    
    Returns:
        (gross_profit, net_profit_after_gas, profit_percentage, direction)
    """
    # Convert input amount to smallest unit
    amount_in = int(amount_in_token_a * (10 ** token_a_decimals))
    
    # Direction 1: Pool1 (A->B) then Pool2 (B->A)
    amount_b_out_1 = calculate_amount_out(
        amount_in,
        pool1_reserve_a,
        pool1_reserve_b,
        fee_bps
    )
    amount_a_out_1 = 0
    if amount_b_out_1 > 0:
        amount_a_out_1 = calculate_amount_out(
            amount_b_out_1,
            pool2_reserve_b,
            pool2_reserve_a,
            fee_bps
        )
    
    profit_1 = amount_a_out_1 - amount_in if amount_a_out_1 > 0 else 0
    
    # Direction 2: Pool2 (A->B) then Pool1 (B->A)
    amount_b_out_2 = calculate_amount_out(
        amount_in,
        pool2_reserve_a,
        pool2_reserve_b,
        fee_bps
    )
    amount_a_out_2 = 0
    if amount_b_out_2 > 0:
        amount_a_out_2 = calculate_amount_out(
            amount_b_out_2,
            pool1_reserve_b,
            pool1_reserve_a,
            fee_bps
        )
    
    profit_2 = amount_a_out_2 - amount_in if amount_a_out_2 > 0 else 0
    
    # Choose the more profitable direction
    if profit_1 >= profit_2:
        gross_profit_raw = profit_1
        direction = "Pool1→Pool2"
    else:
        gross_profit_raw = profit_2
        direction = "Pool2→Pool1"
    
    # Convert to token units
    gross_profit = gross_profit_raw / (10 ** token_a_decimals)
    
    # Calculate net profit (accounting for gas cost placeholder)
    net_profit = gross_profit - GAS_COST_ETH
    
    # Calculate profit percentage
    profit_pct = (gross_profit / amount_in_token_a) * 100 if amount_in_token_a > 0 else 0.0
    
    return gross_profit, net_profit, profit_pct, direction


def find_optimal_arbitrage(
    pool1_reserve_a: int,
    pool1_reserve_b: int,
    pool2_reserve_a: int,
    pool2_reserve_b: int,
    fee_bps: int,
    token_a_decimals: int,
    token_b_decimals: int,
    min_amount: float,
    max_amount: float,
    steps: int
) -> Tuple[float, float, float, float, str]:
    """
    Sweep through different input amounts to find the optimal trade size.
    
    Returns:
        (optimal_input, best_gross_profit, best_net_profit, best_profit_pct, direction)
    """
    # Generate input amounts to test
    input_amounts = np.linspace(min_amount, max_amount, steps)
    
    best_input = 0.0
    best_gross_profit = 0.0
    best_net_profit = 0.0
    best_profit_pct = 0.0
    best_direction = ""
    
    for amount in input_amounts:
        gross_profit, net_profit, profit_pct, direction = simulate_arbitrage(
            amount,
            pool1_reserve_a,
            pool1_reserve_b,
            pool2_reserve_a,
            pool2_reserve_b,
            fee_bps,
            token_a_decimals,
            token_b_decimals
        )
        
        # Track the best opportunity
        if gross_profit > best_gross_profit:
            best_input = amount
            best_gross_profit = gross_profit
            best_net_profit = net_profit
            best_profit_pct = profit_pct
            best_direction = direction
    
    return best_input, best_gross_profit, best_net_profit, best_profit_pct, best_direction


def format_reserve(reserve: int, decimals: int) -> str:
    """Format reserve amount with proper decimals."""
    return f"{reserve / (10 ** decimals):,.2f}"


def print_results(
    block_number: int,
    pool1_reserve_a: int,
    pool1_reserve_b: int,
    pool2_reserve_a: int,
    pool2_reserve_b: int,
    optimal_input: float,
    gross_profit: float,
    net_profit: float,
    profit_pct: float,
    direction: str,
    token_a_decimals: int,
    token_b_decimals: int
):
    """
    Print simulation results to console in a clear, readable format.
    """
    print("\n" + "=" * 70)
    print("DEX ARBITRAGE SIMULATION RESULTS")
    print("=" * 70)
    
    print(f"\nBlock Number: {block_number}")
    
    print("\n--- Pool Reserves Snapshot ---")
    print(f"Pool 1:")
    print(f"  Token A Reserve: {format_reserve(pool1_reserve_a, token_a_decimals)}")
    print(f"  Token B Reserve: {format_reserve(pool1_reserve_b, token_b_decimals)}")
    
    print(f"\nPool 2:")
    print(f"  Token A Reserve: {format_reserve(pool2_reserve_a, token_a_decimals)}")
    print(f"  Token B Reserve: {format_reserve(pool2_reserve_b, token_b_decimals)}")
    
    print("\n--- Optimal Arbitrage Opportunity ---")
    print(f"Direction: {direction}")
    print(f"Optimal Input Amount (Token A): {optimal_input:.4f}")
    print(f"Gross Profit (Token A): {gross_profit:.6f}")
    print(f"Net Profit (after gas, Token A): {net_profit:.6f}")
    print(f"Profit Percentage: {profit_pct:.2f}%")
    
    if gross_profit <= 0:
        print("\n⚠️  No profitable arbitrage opportunity found at current reserves.")
    elif net_profit <= 0:
        print("\n⚠️  Arbitrage opportunity exists but not profitable after gas costs.")
    else:
        print("\n✅ Profitable arbitrage opportunity detected!")
    
    print("\n--- Configuration ---")
    print(f"Fee (basis points): {FEE_BPS} ({FEE_BPS/100}%)")
    print(f"Gas Cost Estimate: {GAS_COST_ETH} ETH")
    
    print("\n" + "=" * 70 + "\n")


def save_to_csv(
    block_number: int,
    optimal_input: float,
    gross_profit: float,
    net_profit: float,
    profit_pct: float
):
    """
    Save results to CSV file (optional feature).
    """
    import csv
    import os
    from datetime import datetime
    
    file_exists = os.path.isfile(CSV_OUTPUT_FILE)
    
    with open(CSV_OUTPUT_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        
        # Write header if file is new
        if not file_exists:
            writer.writerow([
                'Timestamp',
                'Block Number',
                'Optimal Input',
                'Gross Profit',
                'Net Profit',
                'Profit %'
            ])
        
        # Write data
        writer.writerow([
            datetime.now().isoformat(),
            block_number,
            f"{optimal_input:.4f}",
            f"{gross_profit:.6f}",
            f"{net_profit:.6f}",
            f"{profit_pct:.2f}"
        ])


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """
    Main execution function.
    """
    try:
        if DEMO_MODE:
            print("Running in DEMO MODE with mock data...")
            print("(Set DEMO_MODE = False to use real on-chain data)")
            
            # Mock reserves for demonstration
            # Pool 1: Price = 200,000/100 = 2000 USDC per WETH
            pool1_reserve_a = int(100 * 10**TOKEN_A_DECIMALS)    # 100 WETH
            pool1_reserve_b = int(200000 * 10**TOKEN_B_DECIMALS)  # 200,000 USDC
            
            # Pool 2: Price = 220,000/100 = 2200 USDC per WETH (10% higher)
            # This creates an arbitrage opportunity: buy WETH cheap in Pool 1, sell in Pool 2
            pool2_reserve_a = int(100 * 10**TOKEN_A_DECIMALS)     # 100 WETH
            pool2_reserve_b = int(220000 * 10**TOKEN_B_DECIMALS)  # 220,000 USDC
            
            block_number = 123456789
            
            print("✅ Mock reserves loaded")
        else:
            print("Connecting to RPC endpoint...")
            w3 = get_web3_connection(RPC_URL)
            print(f"✅ Connected to network (Chain ID: {w3.eth.chain_id})")
            
            print("\nReading pool reserves...")
            
            # Get reserves from both pools
            pool1_reserve_a, pool1_reserve_b, block1 = get_pool_reserves(
                w3, POOL_1_ADDRESS, TOKEN_A_ADDRESS, TOKEN_B_ADDRESS
            )
            
            pool2_reserve_a, pool2_reserve_b, block2 = get_pool_reserves(
                w3, POOL_2_ADDRESS, TOKEN_A_ADDRESS, TOKEN_B_ADDRESS
            )
            
            # Use the latest block number
            block_number = max(block1, block2)
            
            print("✅ Reserves fetched successfully")
        
        print("\nSimulating arbitrage opportunities...")
        
        # Find optimal arbitrage trade
        optimal_input, gross_profit, net_profit, profit_pct, direction = find_optimal_arbitrage(
            pool1_reserve_a,
            pool1_reserve_b,
            pool2_reserve_a,
            pool2_reserve_b,
            FEE_BPS,
            TOKEN_A_DECIMALS,
            TOKEN_B_DECIMALS,
            MIN_INPUT_AMOUNT,
            MAX_INPUT_AMOUNT,
            SWEEP_STEPS
        )
        
        # Display results
        print_results(
            block_number,
            pool1_reserve_a,
            pool1_reserve_b,
            pool2_reserve_a,
            pool2_reserve_b,
            optimal_input,
            gross_profit,
            net_profit,
            profit_pct,
            direction,
            TOKEN_A_DECIMALS,
            TOKEN_B_DECIMALS
        )
        
        # Optional: Save to CSV
        if ENABLE_CSV_OUTPUT:
            save_to_csv(block_number, optimal_input, gross_profit, net_profit, profit_pct)
            print(f"Results saved to {CSV_OUTPUT_FILE}")
        
    except ConnectionError as e:
        print(f"\n❌ Connection Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

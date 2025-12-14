# DEX-Arbitrage

A minimal, read-only Python project that simulates DEX arbitrage opportunities using real on-chain state. This tool provides theoretical profit calculations only—no transaction execution, signing, or MEV.

## Features

- ✅ Connects to public RPC endpoints (Arbitrum by default)
- ✅ Reads pool reserves via `getReserves()` from Uniswap V2-style AMMs
- ✅ Implements constant-product swap math with configurable fees
- ✅ Simulates A → B arbitrage between two DEX pools
- ✅ Sweeps input sizes to find optimal trade size
- ✅ Clear console output with profit calculations
- ✅ Block number logging
- ✅ Gas breakeven placeholder
- ✅ Optional CSV output

## Requirements

- Python 3.10 or higher
- Libraries: `web3`, `eth-abi`, `numpy`

## Installation

1. Clone the repository:
```bash
git clone https://github.com/fbl-vol/DEX-Arbitrage.git
cd DEX-Arbitrage
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Run the simulation script:
```bash
python simulate.py
```

The script will:
1. Connect to the configured RPC endpoint
2. Read current reserves from two DEX pools
3. Simulate arbitrage opportunities across a range of input amounts
4. Display the optimal trade size and expected profit

## Configuration

All configuration is done in the `simulate.py` file at the top in the **CONFIGURATION SECTION**:

```python
# RPC endpoint
RPC_URL = "https://arb1.arbitrum.io/rpc"

# Pool addresses (modify with your target pools)
POOL_1_ADDRESS = "0x905dfCD5649217c42684f23958568e533C711Aa3"
POOL_2_ADDRESS = "0x8e295789c9465487074a65b1ae9Ce0351172393f"

# Token configuration
TOKEN_A_ADDRESS = "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1"  # WETH
TOKEN_B_ADDRESS = "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"  # USDC
TOKEN_A_DECIMALS = 18
TOKEN_B_DECIMALS = 6

# Fee tier (in basis points)
FEE_BPS = 30  # 0.3%

# Sweep parameters
MIN_INPUT_AMOUNT = 0.01
MAX_INPUT_AMOUNT = 10.0
SWEEP_STEPS = 100
```

### Modifying Pair Addresses

To analyze different token pairs:
1. Update `POOL_1_ADDRESS` and `POOL_2_ADDRESS` with your target pools
2. Update `TOKEN_A_ADDRESS` and `TOKEN_B_ADDRESS` with the token addresses
3. Update `TOKEN_A_DECIMALS` and `TOKEN_B_DECIMALS` accordingly

### Optional Features

Enable CSV output by setting:
```python
ENABLE_CSV_OUTPUT = True
```

Adjust gas cost estimation:
```python
GAS_COST_ETH = 0.001  # Estimated gas cost in ETH
```

## Output Example

```
======================================================================
DEX ARBITRAGE SIMULATION RESULTS
======================================================================

Block Number: 12345678

--- Pool Reserves Snapshot ---
Pool 1 (Buy on this pool):
  Token A Reserve: 1,234.56
  Token B Reserve: 2,345,678.90

Pool 2 (Sell on this pool):
  Token A Reserve: 1,240.00
  Token B Reserve: 2,350,000.00

--- Optimal Arbitrage Opportunity ---
Optimal Input Amount (Token A): 5.2500
Gross Profit (Token A): 0.012345
Net Profit (after gas, Token A): 0.011345
Profit Percentage: 0.24%

✅ Profitable arbitrage opportunity detected!

--- Configuration ---
Fee (basis points): 30 (0.3%)
Gas Cost Estimate: 0.001 ETH

======================================================================
```

## Scope & Limitations

### What This Does
- ✅ Read-only simulation of arbitrage opportunities
- ✅ Uniswap V2-style AMMs only
- ✅ Single chain analysis (Arbitrum by default)
- ✅ Two DEX pools, one token pair
- ✅ Theoretical profit calculations

### What This Does NOT Do
- ❌ No transaction execution
- ❌ No flashloans
- ❌ No mempool access
- ❌ No subgraph queries
- ❌ No private RPCs required
- ❌ No signing or wallet integration
- ❌ No MEV integration

## Acceptance Criteria

- ✅ Script runs without errors on valid pool addresses
- ✅ Output changes when reserves change (test with different blocks)
- ✅ Profit calculations disappear when fees are set to zero (as expected with constant product)
- ✅ No on-chain state mutations (read-only operations)
- ✅ Easy to modify pair addresses via configuration section

## Technical Details

### Constant Product Formula

The script uses the Uniswap V2 constant product formula with fees:

```
amountOut = (amountIn * (10000 - fee) * reserveOut) / (reserveIn * 10000 + amountIn * (10000 - fee))
```

Where `fee` is in basis points (e.g., 30 = 0.3%).

### Arbitrage Strategy

The simulation performs a simple two-step arbitrage:
1. **Pool 1**: Swap Token A → Token B
2. **Pool 2**: Swap Token B → Token A
3. Calculate profit: Final Token A - Initial Token A

The script sweeps through multiple input amounts to find the optimal trade size that maximizes profit.

## Extending for Execution

This codebase is designed to be easily extended for actual trade execution:
- Add wallet/account management
- Add transaction building and signing
- Add gas price optimization
- Add slippage protection
- Add flashloan integration
- Add mempool monitoring

## License

MIT

## Contributing

This is a minimal proof-of-concept. Contributions are welcome for:
- Additional DEX support (Uniswap V3, Curve, etc.)
- Multi-hop arbitrage
- Better optimization algorithms
- Real-time monitoring
- Additional chain support

## Disclaimer

This tool is for educational and research purposes only. Arbitrage trading involves significant risk. Always test thoroughly before executing real trades. No warranty is provided.
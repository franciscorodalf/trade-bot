import ccxt
import json

def check_symbols():
    exchange = ccxt.binance({'options': {'defaultType': 'future'}})
    markets = exchange.load_markets()
    
    print("Searching for PEPE and SHIB...")
    for symbol in markets:
        if "PEPE" in symbol or "SHIB" in symbol:
            print(f"Found: {symbol}")

if __name__ == "__main__":
    check_symbols()

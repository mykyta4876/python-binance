
from binance.client import Client
from binance.um_futures import UMFutures
from binance.error import ClientError
from binance.enums import SIDE_BUY, SIDE_SELL, ORDER_TYPE_MARKET

import pandas as pd
import requests
import time 
api = "c9cc79787d4ac477c47d5610a39ae3647e69565ecf9f87fd4348118af0735173"
api_secret = "8dfac7cb8bbf1ee09a860565d7530cc4c3683707e888dfce2d0ce0380bce131a"

client = Client(api,api_secret,tld="com",testnet=True)

csv_file = "Position.csv"
volume = 10  # volume for one order (if its 10 and leverage is 10, then you put 1 usdt to one position)
leverage = 10
type = 'CROSS'  # type is 'ISOLATED' or 'CROSS'
qty = 100  # Amount of concurrent opened positions

# Fetch USDT balance from Binance Futures
def get_usdt_balance():
    # Get futures account balance
    futures_balance = client.futures_account_balance()
    
    # Find USDT balance from the response
    for asset in futures_balance:
        if asset['asset'] == 'USDT':
            return round(float(asset['balance']),3)
            
def get_current_price(symbol):
        
        response = requests.get(f'https://testnet.binancefuture.com/fapi/v1/ticker/price?symbol={symbol}')
        price = float(response.json()['price'])
        return price

def get_mark_price(symbol):
        x = client.get_symbol_ticker(symbol=symbol)
        price = float(x["price"])
        return price

# Function to calculate unrealized ROI
def calculate_unrealized_roi(entry_price,current_price,position_side):

    if position_side.lower() == 'long':

        roi = (current_price - entry_price) / entry_price * 100

    elif position_side.lower() == 'short':

        roi = (entry_price - current_price) / entry_price * 100


    else:
        raise ValueError("Position side must be either 'long' or 'short'.")
    
    return roi

# Fetch break-even price for a given symbol (e.g., BTCUSDT)
def realized_pnl(symbol):
    # Fetch account position information
    positions = client.futures_position_information(symbol=symbol)

    
    for position in positions:
        #print(position)
        if position['symbol'] == symbol:

            entry_price = float(position['entryPrice'])
            position_amt = float(position['positionAmt'])  # Positive for long, negative for short
            realized_pnl = float(position['unRealizedProfit'])  # Unrealized PnL
            #break_even_price = float(position['breakEvenPrice'])
            # Long or short position
            if position_amt > 0:  # Long position
                print("Long position")
               
                return realized_pnl
               
            elif position_amt < 0:  # Short position
                print("Short position")
                
                return realized_pnl
                
            else:
                return None  # No position


    
    return None  # No position found for the symbol

# Set leverage for the needed symbol. You need this bcz different symbols can have different leverage
def set_leverage(symbol, level):
    try:
        
        response = client.futures_change_leverage(
            symbol=symbol, leverage=level, recvWindow=6000
        )
        print(response)
    except ClientError as error:
        print(
            "Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )


# Set defaults for csv file
def initialize_positions(symbol):
    
    posframe = pd.DataFrame(symbol, columns=['Currency'])
    posframe['Position'] = 0  # 0 means no active position, 1 means active position
    posframe['Quantity'] = 0
    posframe.to_csv(csv_file, index=False)

# Initialize positions on first run
try:
    pd.read_csv(csv_file)
except :
    initialize_positions(input("Input symbol to run bot for it\n"))

# Update the CSV file after buy/sell operations
def update_position_csv(posframe):
    posframe.to_csv(csv_file, index=False)

# Price precision. BTC has 1, XRP has 4
def get_price_precision(symbol):
    resp = client.get_exchange_info()['symbols']
    for elem in resp:
        if elem['symbol'] == symbol:
            return elem['pricePrecision']


# Amount precision. BTC has 3, XRP has 1
def get_qty_precision(symbol):

    resp = client.get_exchange_info()['symbols']
    for elem in resp:
        if elem['symbol'] == symbol:
            return elem['baseAssetPrecision']


# Your current positions (returns the symbols list):
def get_pos():
    try:
        resp = client.get_position_risk()
        pos = []
        for elem in resp:
            if float(elem['positionAmt']) != 0:
                pos.append(elem['symbol'])
        return pos
    except ClientError as error:
        print(
            "Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )

def check_orders():
    try:
        response = client.get_orders(recvWindow=6000)
        sym = []
        for elem in response:
            sym.append(elem['symbol'])
        return sym
    except ClientError as error:
        print(
            "Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )

# Close open orders for the needed symbol. If one stop order is executed and another one is still there
def close_open_orders(symbol):
    try:
        response = client.cancel_open_orders(symbol=symbol, recvWindow=6000)
        print(response)
    except ClientError as error:
        print(
            "Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )


def generate_numbers(start,end,side):
    
    result = []
    # Generate numbers from the start up to 0.029, in increments of 0.001
    if side == "long":
        while round(start, 3) < end:
            result.append(round(start, 3))
            start += 0.001
    else:

        while round(start, 3) > end:
            result.append(round(start, 3))
            start -= 0.001

    return result


# The symbol for which you want to close the position
symbol = 'BTCUSDT'
def close():
        # Step 1: Get position info
        position_info = client.futures_position_information(symbol=symbol)

        # Step 2: Check position size (for long, it's positive; for short, it's negative)
        for position in position_info:
            if position['symbol'] == symbol:
                position_amt = float(position['positionAmt'])  # Get the amount of position
                
                if position_amt > 0:  # Long position
                    # Step 3: Place a market sell order to close the long position
                    order = client.futures_create_order(
                        symbol=symbol,
                        side=SIDE_SELL,
                        type=ORDER_TYPE_MARKET,
                        quantity=abs(position_amt)  # Sell the same amount to close
                    )
                elif position_amt < 0:  # Short position
                    # Step 3: Place a market buy order to close the short position
                    order = client.futures_create_order(
                        symbol=symbol,
                        side=SIDE_BUY,
                        type=ORDER_TYPE_MARKET,
                        quantity=abs(position_amt)  # Buy the same amount to close
                    )

                print(f"Order placed to close the position: {order}")

def roi():
     
    symbol="BTCUSDT"
    print(f"ROI % is : {round(calculate_unrealized_roi(62999.70,get_current_price(symbol),"long")*100,2)}")
    time.sleep(0.5)
    print("Realized_pnl",realized_pnl(symbol)," USDT")
    # close_orders(symbol)
    print(get_qty_precision(symbol))
    #get_price_precision(symbol)
    #set_leverage(symbol, 50)
    # if(realized_pnl(symbol) != None):
    #     if(float(realized_pnl(symbol)) >= 1.30):
    #         close()


while True:
    roi()
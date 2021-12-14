import sys
import os
from os import path
parent_path = os.path.dirname(os.getcwd())
sys.path.append(parent_path)
from arbitrage.config import *
from binance.client import Client
import time
from common import *

wallet = 'TZFUe7XD2Di4G4pha8uhQnAXfstfMbRTp6'
#wallet = 'TNkZK6EoXHNYPyWQFetpEQziVV7MBHPC9c'
#wallet = 'TFUyXijDSyppV9hpqC3yJ7z9z2ft3H6RGD'

def withdrow(asset, amount):
    return client.withdraw(
        asset=asset,
        address=wallet,
        amount=amount,
        network='TRX')

def get_asset_info(**params):
    return client._request_margin_api('get', 'capital/config/getall', True, data=params)

if __name__ == "__main__":
    # assets_info = get_asset_info(timestamp = int(time.time() * 1000))
    # print(assets_info)
    withdraw_asset = input("input withdraw asset name:").upper()
    withdraw_amount_str = input("input withdraw amount:")
    withdraw_amount2_str = input("input withdraw amount again:")
    withdraw_amount = float(withdraw_amount_str)
    withdraw_amount2 = float(withdraw_amount2_str)
    withdrow(withdraw_asset, withdraw_amount)
                    

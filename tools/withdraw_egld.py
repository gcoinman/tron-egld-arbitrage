import sys
import os
from os import path
parent_path = os.path.dirname(os.getcwd())
sys.path.append(parent_path)
from arbitrage.config import *
from binance.client import Client
import time
from common import *

wallet = 'erd1gx76al98vt25tvndwemr6z34zv94xaj44le7a4zmzzr69mpzp8gsv3m403'

def withdrow(asset, amount):
    # print('dest address={}'.format(wallet))
    return client.withdraw(
        coin=asset,
        address=wallet,
        amount=amount,
        network='EGLD')

def get_asset_info(**params):
    return client._request_margin_api('get', 'capital/config/getall', True, data=params)

if __name__ == "__main__":
    # assets_info = get_asset_info(timestamp = int(time.time() * 1000))
    # print(assets_info)
    print('dest address={}'.format(wallet))
    withdraw_asset = 'EGLD'
    withdraw_amount_str = input("input withdraw amount:")
    withdraw_amount2_str = input("input withdraw amount again:")
    withdraw_amount = float(withdraw_amount_str)
    withdraw_amount2 = float(withdraw_amount2_str)
    assert withdraw_amount == withdraw_amount2
    withdrow(withdraw_asset, withdraw_amount)

import sys
import os
from os import path
parent_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
print(parent_path)
sys.path.append(parent_path)
from arbitrage.config import *
from arbitrage.key import *
from binance.client import Client
import time

public = key_public
secret = key_secret

client = Client(public, secret)

def get_margin_balance():
    response = client.get_margin_account()
    margin_balances = response['userAssets']
    return margin_balances

def get_spot_balances():
    response = client.get_account()
    spot_balances = response['balances']
    return spot_balances
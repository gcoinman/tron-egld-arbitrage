#encoding=‘utf-8’
from common import *
from arbitrage.binancemarket import BinanceMarket
from arbitrage.dexswap import DexSwap
from arbitrage.logger import Logger
from arbitrage.calladmin import *
from Crypto.Cipher import AES
from binascii import b2a_hex, a2b_hex
import getpass
from  Crypto import Random
from waiting import wait as wait_conf
from func_timeout import func_set_timeout
import func_timeout
import time
import func_timeout
from func_timeout import func_set_timeout
import json
from tronpy import Tron
from tronpy import keys
import requests
import json


trx_client = Tron()

query_abi = '''
[
	{
		"constant": true,
		"inputs": [
			{
				"internalType": "address",
				"name": "admin",
				"type": "address"
			},
			{
				"internalType": "address[]",
				"name": "tokens",
				"type": "address[]"
			},
			{
				"internalType": "address[]",
				"name": "pair_list",
				"type": "address[]"
			}
		],
		"name": "get_all_information",
		"outputs": [
			{
				"components": [
					{
						"internalType": "uint256",
						"name": "reserve0",
						"type": "uint256"
					},
					{
						"internalType": "uint256",
						"name": "reserve1",
						"type": "uint256"
					}
				],
				"internalType": "struct MQuery.Reserve[]",
				"name": "",
				"type": "tuple[]"
			},
			{
				"internalType": "uint256[]",
				"name": "",
				"type": "uint256[]"
			}
		],
		"payable": false,
		"stateMutability": "view",
		"type": "function"
	}
]
'''


trx_assets = ['TRX', 'USDT', 'JST', 'WIN', 'SUN']
trx_assets_precisions = {'TRX': 6, 'USDT': 6, 'JST': 18, 'WIN': 6, 'SUN': 18}
q_abi = json.loads(query_abi)
trx_query = trx_client.get_contract('TG4qLmPTPYrWs25vGBwm6ogZzhYHAZuhcn')
trx_query.abi = q_abi
def get_tron_chain_balances():
    balances_dic = {}
    asset_addrs = [eval(asset) for asset in trx_assets[1:]]
    pairs = [eval(asset+'_TRX') for asset in trx_assets[1:]]
    (reserves, balances) = trx_query.functions.get_all_information('TZFUe7XD2Di4G4pha8uhQnAXfstfMbRTp6', asset_addrs, pairs)
    for i in range(len(trx_assets)):
        balances_dic[trx_assets[i]] = balances[i] / 10 ** trx_assets_precisions[trx_assets[i]]
    return balances_dic


def get_asset_info(**params):
    return client._request_margin_api('get', 'capital/config/getall', True, data=params)

cex_wallet = 'TXWR2Uk9v1JdKtoHVtnSzqbSX9QtTAYCA3'
dex_wallet = 'TZFUe7XD2Di4G4pha8uhQnAXfstfMbRTp6'

def withdrow(asset, amount):
    try:
        resp = client.withdraw(
            coin=asset,
            address=dex_wallet,
            amount=amount,
            network='TRX')
        return {'success': True, 'id': resp['id']}
    except Exception as e:
        print(e)
        return {'success': False}

log = Logger('all.log',level='info')
dex_swap = DexSwap(log)
binance = BinanceMarket(log)

current_tron_balances = {}
current_binance_balances = {}
tickers = {}

def get_price(asset):
    global tickers
    if asset == 'USDT':
        return 1
    for ticker in tickers:
        if ticker['symbol'] == (asset + 'USDT'):
            return float(ticker['price'])

# wbtt_addr = 'TKfjV9RNKJJCqPvBtK8L7Knykh7DNWvnYt'
# btt_token_id = 1002000

wallet_assets_max_limit = {'TRX': 600000, 'USDT': 20000, 'BTT': 3500000, 'JST': 80000, 'WIN': 16000000, 'SUN': 500000}

withdrow_dex_ids = []

def transfer2cex():
    withdrow_dex_ids.clear()
    dex_swap.update_information()
    margin_balances = get_margin_balance()
    spot_balances = get_spot_balances()
    assets_info = get_asset_info(timestamp = int(time.time() * 1000))
    i = 0
    while(i < len(trx_assets)):
        asset = trx_assets[i]
        i += 1
        if asset == 'BTT':
            continue
        if not is_deposit_enable(assets_info, asset):
            continue
        dex_free = dex_swap.balances[asset]
        price = get_price(asset)
        if asset not in wallet_assets_max_limit:
            continue
        if dex_free / 10 ** dex_swap.precisions[asset] < wallet_assets_max_limit[asset]:
            continue
        amount = dex_free / 10 ** dex_swap.precisions[asset] - wallet_assets_max_limit[asset]
        if amount * price < 1000:
            continue
        print('{} transfer to cex, amount is {:.4f}'.format(asset, amount))
        amount = int(amount * 10 ** dex_swap.precisions[asset])
        try:
            txid = dex_swap.transfer(asset, cex_wallet, amount)
            if txid is None:
                continue
            withdrow_dex_ids.append(txid)
            print(txid)
        except func_timeout.exceptions.FunctionTimedOut:
            print('transfer_token time out')
            i -= 1
        except Exception as e:
            print('transfer_token exception')
            # traceback.print_exc()
            if 'lacement transaction underprice' in str(e) or 'once too low' in str(e):
                i -= 1
                time.sleep(1)
            else:
                time.sleep(0.5)
                dex_swap.update_information()

#######################################################
    # time.sleep(1)
    # asset = 'BTT'
    # if not is_deposit_enable(assets_info, asset):
    #     return
    # price = get_price(asset)
    # dex_free = dex_swap.balances[asset]
    # if dex_free / 10 ** dex_swap.precisions[asset] < wallet_assets_max_limit[asset]:
    #     return
    # amount = dex_free / 10 ** dex_swap.precisions[asset] - wallet_assets_max_limit[asset]
    # if amount * price < 1000:
    #     return
    # print('{} transfer to cex, amount is {:.4f}'.format(asset, amount))
    # amount = int(amount * 10 ** dex_swap.precisions[asset])
    # try:
    #     dex_swap.withdraw_btt(amount)
    #     btt_bal = dex_swap.get_btt_balance()
    #     if btt_bal / 10 ** 6 * price < 1000:
    #         print('btt balance is {}, too small'.format(btt_bal / 10 ** 6))
    #         return
    #     txid = dex_swap.transfer_btt(cex_wallet, btt_bal)
    #     withdrow_dex_ids.append(txid)
    #     print(txid)
    # except func_timeout.exceptions.FunctionTimedOut:
    #     print('btt transfer time out')
    #     i -= 1
    # except Exception as e:
    #     print('btt transfer exception')
    #     time.sleep(1)
# #######################################################

withdrow_cex_ids = []

def is_arbitrager_working():
    with open('flag') as f:
        if f.read() == 'true':
            return True
    return False

last_order_time = int(time.time())

last_transfer2dex_time = 0

def transfer2dex():
    global last_order_time
    last_order_time = int(time.time())
    if is_arbitrager_working():
        print('arbitrager is working')
        return True
    global last_transfer2dex_time
    withdrow_cex_ids.clear()
    current_transfer2dex_time = time.time()
    if current_transfer2dex_time - last_transfer2dex_time < 10:
        print('transfer2dex time interval too small')
        return True
    last_transfer2dex_time = current_transfer2dex_time
    margin_balances = get_margin_balance()
    spot_balances = get_spot_balances()
    dex_swap.update_information()
    assets_info = get_asset_info(timestamp = int(time.time() * 1000))
    # tmp_trx_assets = trx_assets + ['BTT']
    tmp_trx_assets = trx_assets
    try:
        for asset in tmp_trx_assets:
            if not is_withdraw_enable(assets_info, asset):
                continue
            # if asset == 'SUN':
            #     continue
            for asset_info in margin_balances:
                if asset_info['asset'] == asset:
                    if asset in spot_assets:
                        break
                    free = float(asset_info['free'])
                    dex_free = dex_swap.balances[asset] / 10 ** dex_swap.precisions[asset]
                    if asset not in wallet_assets_max_limit:
                        continue
                    price = get_price(asset)
                    amount = wallet_assets_max_limit[asset] - dex_free
                    if amount * price < 2000 or free < amount:
                        continue
                    amount = round(amount, 1)
                    print('{} transfer margin to spot amount: {}'.format(asset, amount))
                    client.transfer_margin_to_spot(
                        asset=asset,
                        amount=amount)
                    time.sleep(1)
                    print('{} withdraw to dex, amount is {:.4f}'.format(asset, amount))
                    reponse = withdrow(asset, amount)
                    if 'success' in reponse and reponse['success']:
                        withdrow_cex_ids.append(reponse['id'])
                    break
        
            for balance in spot_balances:
                if balance['asset'] == asset:
                    if asset not in spot_assets:
                        break
                    price = get_price(asset)
                    cex_free = float(balance['free'])
                    dex_free = dex_swap.balances[asset] / 10 ** dex_swap.precisions[asset]
                    amount = wallet_assets_max_limit[asset] - dex_free
                    if amount * price < 1000 or cex_free < amount:
                        break

                    print('{} withdraw to dex, amount is {:.4f}'.format(asset, amount))
                    reponse = withdrow(asset, amount)
                    if 'success' in reponse and reponse['success']:
                        withdrow_cex_ids.append(reponse['id'])
                    break
    except Exception as e:
        print(str(e))
    except:
        print('Unexpected error')


def check_status():
    return
    global last_order_time
    now = int(time.time())
    if now - last_order_time > 1800:
        last_order_time = now
        call_admin()

def wait_for_deposit_complete():
    l = len(withdrow_dex_ids)
    while(l > 0):
        try:
            print('\nwait for deposit to cex complete, pending txids:\n')
            print(withdrow_dex_ids)
            deposit_list = client.get_deposit_history(status=1, startTime = int(time.time() * 1000) - 40000 * 1000)
            for item in deposit_list:
                for txid in withdrow_dex_ids:
                    if item['txId'] == txid:
                        withdrow_dex_ids.remove(txid)
                        print('{} deposit succeed'.format(txid))
                        break
        finally:
            l = len(withdrow_dex_ids)
            check_status()
        time.sleep(3)

def wait_for_withdraw_complete():
    l = len(withdrow_cex_ids)
    if l==0:
        transfer2cex()
        wait_for_deposit_complete()
    while(l > 0):
        try:
            print('\nwait for withdraw to dex complete, pending ids:\n')
            print(withdrow_cex_ids)
            withdraw_list = client.get_withdraw_history(status=3, startTime = int(time.time() * 1000) - 40000 * 1000)
            withdraw_list += client.get_withdraw_history(status=5, startTime = int(time.time() * 1000) - 40000 * 1000)
            withdraw_list += client.get_withdraw_history(status=6, startTime = int(time.time() * 1000) - 40000 * 1000)

            for item in withdraw_list:
                for _id in withdrow_cex_ids:
                    if item['id'] == _id and 'txId' in item:
                        txid = item['txId']
                        print('withdraw txid={}'.format(txid))
                        tx = dex_swap.client.get_transaction_info(txid)
                        if 'result' in tx and tx['result'] == 'FAILED':
                            print('withdraw txid {} failed'.format(txid))
                            raise
                        withdrow_cex_ids.remove(_id)
            l = len(withdrow_cex_ids)
            if l > 0:            
                withdraw_list = client.get_withdraw_history(status=3)
                withdraw_list += client.get_withdraw_history(status=5)
                print('get completed withdraw history')
                for item in withdraw_list:
                    for _id in withdrow_cex_ids:
                        if item['id'] == _id:
                            withdrow_cex_ids.remove(_id)
                            break
            l = len(withdrow_cex_ids)
            if l > 0:
                transfer2cex()
                wait_for_deposit_complete()
        except Exception as e:
            print('wait_for_withdraw_complete exception')
            log.logger.info('wait_for_withdraw_complete exception: {}'.format(str(e)))
        finally:
            check_status()
            l = len(withdrow_cex_ids)
            
        time.sleep(3)

    ##################################
    # btt_bal = dex_swap.get_btt_balance()
    # if btt_bal / 10 ** 6 >  50000:
    #     print('btt balance is {:.2f}, deposit to wbtt'.format(btt_bal / 10 ** 6))
    #     dex_swap.deposit_btt(btt_bal)
    #     return
    ##################################

def is_withdraw_enable(assets_info, asset):
    for asset_info in assets_info:
        if asset_info['coin'].upper() == asset.upper():
            for network in asset_info['networkList']:
                if network['network'] == 'TRX':
                    return network['withdrawEnable']
    print('{} withdraw is disabled'.format(asset))
    return False

def is_deposit_enable(assets_info, asset):
    for asset_info in assets_info:
        if asset_info['coin'].upper() == asset.upper():
            for network in asset_info['networkList']:
                if network['network'] == 'TRX':
                    return network['depositEnable']
    print('{} deposit is disabled'.format(asset))
    return False

tickers = client.get_all_tickers()
if __name__ == "__main__":
    print('start monitor balance...')
    while(True):
        try:
            wait_for_withdraw_complete()
            check_status()
            transfer2dex()
            time.sleep(1)
        except func_timeout.exceptions.FunctionTimedOut:
            print('transfer_token time out') 
        except Exception as e:
            print(str(e))
        time.sleep(10)

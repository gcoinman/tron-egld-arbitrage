# Copyright (C) 2013, Maxime Biais <maxime@biais.org>

import time
import logging
import json
import threading
import sys
import os
file_path = os.path.dirname(os.path.realpath(__file__))
parent_path = os.path.dirname(file_path)
sys.path.append(parent_path)
from config import *
from binancemarket import BinanceMarket
from dexswap import DexSwap
from egldswap import EgldSwap
from concurrent.futures import ThreadPoolExecutor, wait
from logger import Logger
import func_timeout
from func_timeout import func_set_timeout

def get_valid_depth(depths, symbol):
    if symbol not in depths:
        return None 
    depth = depths[symbol]
    if depth is None:
        return None
    if symbol == 'WBTCBTC':
        return depth
    cur_timestamp = int(time.time() * 1000)
    if cur_timestamp - depth['timestamp'] > 20 * 1000:
        return None
    return depth

def get_depth_volume_price(index, depths, symbol):
    if symbol == 'USDTUSDT':
        return 1, 10 ** 10, 1, 10 ** 10
    if symbol == 'WBTCUSDT':
        btc_depth = get_valid_depth(depths, 'BTCUSDT')
        wbtc_depth = get_valid_depth(depths, 'WBTCBTC')
        if btc_depth is None or wbtc_depth is None:
            return 0, 0, 0, 0
        btc_buy_price = float(btc_depth['asks'][1][0])
        btc_sell_price = float(btc_depth['bids'][1][0])
        wbtc_buy_price = float(wbtc_depth['asks'][index][0])
        wbtc_sell_price = float(wbtc_depth['bids'][index][0])
        buy_volume = 0
        for i in range(index + 1):
            buy_volume += float(wbtc_depth["asks"][i][1])
        sell_volume = 0
        for i in range(index + 1):
            sell_volume += float(wbtc_depth["bids"][i][1])
        buy_price = btc_buy_price * wbtc_buy_price * 1.001
        sell_price = btc_sell_price * wbtc_sell_price * 0.999
        return buy_price, buy_volume, sell_price, sell_volume

    depth = get_valid_depth(depths, symbol)
    if depth is None:
        return 0, 0, 0, 0
    buy_price = float(depth['asks'][index][0])
    sell_price = float(depth['bids'][index][0])
    buy_volume = 0
    for i in range(index + 1):
        buy_volume += float(depth["asks"][i][1])
    sell_volume = 0
    for i in range(index + 1):
        sell_volume += float(depth["bids"][i][1])
    return buy_price, buy_volume, sell_price, sell_volume


log = Logger('all.log',level='info')
dex_swap = DexSwap(log)
binance = BinanceMarket(log)

total_profit = 0
trx_buy_price = 0.062

def new_arbitrage(dex_side, base_asset, quote_asset, amount_in, output_amount):
    global total_profit
    global trx_buy_price
    gasfee = 0
    try:
        if dex_side == 'buy':
            ret, real_output_amount, gasfee = dex_swap.buy(base_asset, quote_asset, amount_in)
            if not ret:
                total_profit -= gasfee * trx_buy_price
                log.logger.info('dex buy fail, gasfee is {0:.4f}, total_profit is {1:.4f}'.format(gasfee * trx_buy_price, total_profit))
                return
            cex_base_sell_amount = output_amount / 10 ** dex_swap.precisions[base_asset]
            cex_quote_buy_amount = amount_in / 10 ** dex_swap.precisions[quote_asset]
            cex_sell_price = 1
            if base_asset != 'USDT':
                if base_asset == 'WBTC':
                    base_asset = 'BTC'
                _, _, cex_sell_price, _ = get_depth_volume_price(4, binance.depths, base_asset+'USDT')
                if base_asset != 'USDC':
                    binance.sell(base_asset, cex_base_sell_amount, cex_sell_price)
            quote_buy_price, _, _, _ = get_depth_volume_price(4, binance.depths, quote_asset+'USDT')
            profit = cex_base_sell_amount * cex_sell_price * (1 - fee) - cex_quote_buy_amount * quote_buy_price * (1 + fee) - gasfee * trx_buy_price
            binance.buy(quote_asset, cex_quote_buy_amount, quote_buy_price)
            total_profit += profit
        elif dex_side == 'sell':
            ret, real_output_amount, gasfee = dex_swap.sell(base_asset, quote_asset, amount_in)
            if not ret:
                total_profit -= gasfee * trx_buy_price
                log.logger.info('dex sell fail, gasfee is {0:.4f}, total_profit is {1:.4f}'.format(gasfee * trx_buy_price, total_profit))                        
                return
            cex_quote_sell_amount = output_amount / 10 ** dex_swap.precisions[quote_asset]
            cex_base_buy_amount = amount_in / 10 ** dex_swap.precisions[base_asset]
            cex_buy_price = 1
            if base_asset != 'USDT':
                if base_asset == 'WBTC':
                    base_asset = 'BTC'
                cex_buy_price, _, _, _ = get_depth_volume_price(4, binance.depths, base_asset+'USDT')
                if base_asset != 'USDC':
                    binance.buy(base_asset, cex_base_buy_amount, cex_buy_price)
            _, _, quote_sell_price, _ = get_depth_volume_price(4, binance.depths, quote_asset+'USDT')
            profit = cex_quote_sell_amount * quote_sell_price * (1 - fee) - cex_base_buy_amount * cex_buy_price * (1 + fee) - gasfee * trx_buy_price
            binance.sell(quote_asset, cex_quote_sell_amount, quote_sell_price)
            total_profit += profit
        
        gas_info = 'gasfee: {}'.format(gasfee * trx_buy_price)
        print(gas_info, flush=True)
        log.logger.info(gas_info)
        profit_info = 'this arbitrage profit is: {0:.4f} USDT, total profit is: {1:.4f} USDT'.format(profit, total_profit)
        print(profit_info, flush=True)
        log.logger.info(profit_info)
        print('{} dex {} end'.format(base_asset, dex_side), flush=True)
    except func_timeout.exceptions.FunctionTimedOut:
        print('new_arbitrage time out')
    except Exception as e:
        print(e)

def clear_complete_task(tasks):
    for key in list(tasks.keys()):
        if tasks[key].done():
            del tasks[key]
    return len(list(tasks.keys()))

thread_count = 4
threadpool = ThreadPoolExecutor(max_workers=thread_count)
tasks = {}

def asset_arbitrage():
    global trx_buy_price
    global min_profit
    try:
        trx_buy_price, _, _, _ = get_depth_volume_price(4, binance.depths, 'TRXUSDT')
        if trx_buy_price == 0:
            print('trx depth is none')
            return
        for asset in assets[1:]:
            if asset == 'USDJ' or asset == 'TUSD':
                continue
            symbols = [asset, 'TRX']
            base_buy_price, base_buy_volume, base_sell_price, base_sell_volume = get_depth_volume_price(4, binance.depths, asset+'USDT')
            quote_buy_price, quote_buy_volume, quote_sell_price, quote_sell_volume = get_depth_volume_price(4, binance.depths, 'TRXUSDT')
            if base_buy_price == 0 or quote_buy_price == 0:
                print('base_buy_price or quote_buy_price is 0!')
                return
            # 同一个交易对只能有一个线程，防止重复交易
            l = clear_complete_task(tasks)
            # 超过10个线程后，会有线程被阻塞，影响实时成交，降低成功率
            if l > thread_count:
                print('working task > {}'.format(thread_count))
                return
            if asset in tasks:
                continue
            base_min_amount = 200 / base_buy_price
            quote_min_amount = 200 / quote_buy_price
            dex_buy_price = dex_swap.get_price(symbols[0], symbols[1], 'buy', quote_min_amount * 10 ** dex_swap.precisions[symbols[1]])
            dex_sell_price = dex_swap.get_price(symbols[0], symbols[1], 'sell', base_min_amount * 10 ** dex_swap.precisions[symbols[0]])
            cex_buy_price = base_buy_price / quote_sell_price
            cex_sell_price = base_sell_price / quote_buy_price
            if cex_sell_price > dex_buy_price * (1 + price_percent_difference_threshold):
                dex_quote_bal = dex_swap.asset_balance(symbols[1])
                cex_base_bal = binance.get_balance_with_borrow(symbols[0])
                dex_base_bal = dex_swap.asset_balance(symbols[0])
                if asset == 'BTC' and dex_base_bal / 10 ** dex_swap.precisions[asset] > 2:
                    continue
                if asset == 'ETH' and dex_base_bal / 10 ** dex_swap.precisions[asset] > 30:
                    continue
                if asset == 'USDC' and dex_base_bal / 10 ** dex_swap.precisions[asset] > 100000:
                    continue
                if asset == 'WBTC' and dex_base_bal / 10 ** dex_swap.precisions[asset] > 2:
                    continue
                max_quote_trade_amount = min(dex_quote_bal, (max_usdt_trade_amount / quote_buy_price) * 10 ** dex_swap.precisions[symbols[1]])
                max_cex_trade_amount = min(min(cex_base_bal, base_sell_volume) * cex_sell_price, quote_buy_volume) * 10 ** dex_swap.precisions[symbols[1]]
                dex_trade_amount = min(max_quote_trade_amount, max_cex_trade_amount) * 99 / 100
                price_limit = (cex_sell_price / (1 + price_percent_difference_threshold))
                if dex_trade_amount * quote_buy_price / (10 ** dex_swap.precisions[symbols[1]]) < 200:
                    # print('dex trade amount is {:.4f} USDT, too low'.format(dex_trade_amount * quote_buy_price / (10 ** dex_swap.precisions[symbols[1]])))
                    continue
                price, dex_quote_trade_amount = dex_swap.binary_search(symbols[0], symbols[1], dex_trade_amount, 'buy', price_limit)
                cex_base_sell_amount = dex_quote_trade_amount / price / 10 ** dex_swap.precisions[symbols[1]]
                cex_quote_buy_amount = dex_quote_trade_amount / 10 ** dex_swap.precisions[symbols[1]]
                profit = cex_base_sell_amount * base_sell_price * (1 - fee) - cex_quote_buy_amount * quote_buy_price * (1 + fee)
                print('\n', '-'*30, '\n{} arbitrage profit is {:.4f}, cex sell price is {:.4f}, amount is {:.4f}, dex buy price is {:.4f}'.format(asset, profit, cex_sell_price, cex_base_sell_amount, price))
                if profit < min_profit:
                    print('{} trade amount is {:.4f}, profit is {:.4f} USDT, too low!'.format(asset, cex_quote_buy_amount, profit))
                    continue
                tasks[asset] = threadpool.submit(new_arbitrage, 'buy', symbols[0], symbols[1], dex_quote_trade_amount, cex_base_sell_amount * 10 ** dex_swap.precisions[symbols[0]])
                continue
            elif cex_buy_price < dex_sell_price / (1 + price_percent_difference_threshold):
                dex_base_bal = dex_swap.asset_balance(symbols[0])
                cex_quote_bal = binance.get_balance_with_borrow(symbols[1])
                max_base_trade_amount = (max_usdt_trade_amount / base_buy_price) * 10 ** dex_swap.precisions[symbols[0]]
                max_cex_trade_amount = min(min(cex_quote_bal, quote_sell_volume) / cex_buy_price, base_buy_volume) * 10 ** dex_swap.precisions[symbols[0]]
                dex_trade_amount = min(dex_base_bal, max_base_trade_amount, max_cex_trade_amount) * 99 / 100
                price_limit = cex_buy_price * (1 + price_percent_difference_threshold)
                if dex_trade_amount * base_buy_price / (10 ** dex_swap.precisions[symbols[0]]) < 200:
                    # print('dex trade amount is {:.4f} USDT, too low'.format(dex_trade_amount * base_buy_price / (10 ** dex_swap.precisions[symbols[0]])))
                    continue
                price, dex_base_trade_amount = dex_swap.binary_search(symbols[0], symbols[1], dex_trade_amount, 'sell', price_limit)
                cex_quote_sell_amount = (dex_base_trade_amount * price) / 10 ** dex_swap.precisions[symbols[0]]
                cex_base_buy_amount = dex_base_trade_amount / 10 ** dex_swap.precisions[symbols[0]]
                profit = cex_quote_sell_amount * quote_sell_price * (1 - fee) - cex_base_buy_amount * base_buy_price * (1 + fee)
                print('\n', '-'*30, '\n{} arbitrage profit is {:.4f}, cex buy price is {:.4f}, amount is {:.4f}, dex sell price is {:.4f}'.format(asset, profit, cex_buy_price, cex_base_buy_amount, dex_sell_price))
                if profit < min_profit:
                    print('{} trade amount is {:.4f}, profit is {:.4f} USDT, too low!'.format(asset, cex_quote_sell_amount, profit))
                    continue
                tasks[asset] = threadpool.submit(new_arbitrage, 'sell', symbols[0], symbols[1], dex_base_trade_amount, cex_quote_sell_amount * 10 ** dex_swap.precisions[symbols[1]])
                continue
    except func_timeout.exceptions.FunctionTimedOut:
        print('main_pair_arbitrage time out')
    except Exception as e:
        print(e)


def new_stable_arbitrage(dex_side, base_asset, quote_asset, amount_in, output_amount):
    global total_profit
    global trx_buy_price
    gasfee = 0
    try:
        if dex_side == 'buy':
            ret, real_output_amount, gasfee = dex_swap.buy_stable_coin(base_asset, quote_asset, amount_in)
            if not ret:
                total_profit -= gasfee * trx_buy_price
                log.logger.info('dex buy fail, gasfee is {0:.4f}, total_profit is {1:.4f}'.format(gasfee * trx_buy_price, total_profit))
                return
            usdt_output_amount = (output_amount / 10 ** dex_swap.precisions[base_asset]) * dex_swap.stable_prices[base_asset + '_SELL']
            cex_quote_buy_amount = amount_in / 10 ** dex_swap.precisions[quote_asset]
            quote_buy_price, _, _, _ = get_depth_volume_price(4, binance.depths, quote_asset+'USDT')
            profit = usdt_output_amount - cex_quote_buy_amount * quote_buy_price * (1 + fee) - gasfee * trx_buy_price
            binance.buy(quote_asset, cex_quote_buy_amount, quote_buy_price)
            total_profit += profit
        elif dex_side == 'sell':
            ret, real_output_amount, gasfee = dex_swap.sell_stable_coin(base_asset, quote_asset, amount_in)
            if not ret:
                total_profit -= gasfee * trx_buy_price
                log.logger.info('dex sell fail, gasfee is {0:.4f}, total_profit is {1:.4f}'.format(gasfee * trx_buy_price, total_profit))                        
                return
            cex_quote_sell_amount = output_amount / 10 ** dex_swap.precisions[quote_asset]
            usdt_input_amount = amount_in * dex_swap.stable_prices[base_asset + '_BUY'] / 10 ** dex_swap.precisions[base_asset]
            _, _, quote_sell_price, _ = get_depth_volume_price(4, binance.depths, quote_asset+'USDT')
            profit = cex_quote_sell_amount * quote_sell_price * (1 - fee) - usdt_input_amount - gasfee * trx_buy_price
            binance.sell(quote_asset, cex_quote_sell_amount, quote_sell_price)
            total_profit += profit
        
        gas_info = 'gasfee: {}'.format(gasfee * trx_buy_price)
        print(gas_info, flush=True)
        log.logger.info(gas_info)
        profit_info = 'this arbitrage profit is: {0:.4f} USDT, total profit is: {1:.4f} USDT'.format(profit, total_profit)
        print(profit_info, flush=True)
        log.logger.info(profit_info)
        print('{} dex {} end'.format(base_asset, dex_side), flush=True)
    except func_timeout.exceptions.FunctionTimedOut:
        print('new_arbitrage time out')
    except Exception as e:
        print(e)

def stable_asset_arbitrage():
    global trx_buy_price
    global min_profit
    try:
        trx_buy_price, _, _, _ = get_depth_volume_price(4, binance.depths, 'TRXUSDT')
        if trx_buy_price == 0:
            print('trx depth is none')
            return
        # stable_assets = ['USDJ', 'TUSD']
        stable_assets = ['TUSD']
        for asset in stable_assets:
            symbols = [asset, 'TRX']
            quote_buy_price, quote_buy_volume, quote_sell_price, quote_sell_volume = get_depth_volume_price(4, binance.depths, 'TRXUSDT')
            if quote_buy_price == 0:
                print('quote_buy_price is 0!')
                return
            # 同一个交易对只能有一个线程，防止重复交易
            l = clear_complete_task(tasks)
            # 超过10个线程后，会有线程被阻塞，影响实时成交，降低成功率
            if l > thread_count:
                print('working task > {}'.format(thread_count))
                return
            if asset in tasks:
                continue
            base_min_amount = 2000
            quote_min_amount = 2000 / quote_buy_price
            dex_buy_price = dex_swap.get_price(symbols[0], symbols[1], 'buy', quote_min_amount * 10 ** dex_swap.precisions[symbols[1]])
            dex_sell_price = dex_swap.get_price(symbols[0], symbols[1], 'sell', base_min_amount * 10 ** dex_swap.precisions[symbols[0]])
            base_buy_price = dex_swap.stable_prices[asset+'_BUY']
            base_sell_price = dex_swap.stable_prices[asset+'_SELL']
            cex_buy_price = base_buy_price / quote_sell_price
            cex_sell_price = base_sell_price / quote_buy_price
            
            if cex_sell_price > dex_buy_price * (1 + price_percent_difference_threshold):
                dex_quote_bal = dex_swap.asset_balance(symbols[1])
                max_quote_trade_amount = min(dex_quote_bal, (max_usdt_trade_amount / quote_buy_price) * 10 ** dex_swap.precisions[symbols[1]])
                max_cex_trade_amount = quote_buy_volume * 10 ** dex_swap.precisions[symbols[1]]
                dex_trade_amount = min(max_quote_trade_amount, max_cex_trade_amount) * 99 / 100
                price_limit = (cex_sell_price / (1 + price_percent_difference_threshold))
                if dex_trade_amount * quote_buy_price / (10 ** dex_swap.precisions[symbols[1]]) < 500:
                    print('dex trx amount in is {:.4f}, too low'.format(dex_trade_amount / (10 ** dex_swap.precisions[symbols[1]])))
                    continue
                price, dex_quote_trade_amount = dex_swap.binary_search(symbols[0], symbols[1], dex_trade_amount, 'buy', price_limit)
                cex_base_sell_amount = dex_quote_trade_amount / price / 10 ** dex_swap.precisions[symbols[1]]
                cex_quote_buy_amount = dex_quote_trade_amount / 10 ** dex_swap.precisions[symbols[1]]
                profit = cex_base_sell_amount * base_sell_price * (1 - fee) - cex_quote_buy_amount * quote_buy_price * (1 + fee)
                print('\n', '-'*30, '\n{} arbitrage profit is {:.4f}, cex sell price is {:.4f}, amount is {:.4f}, dex buy price is {:.4f}'.format(asset, profit, cex_sell_price, cex_base_sell_amount, price))
                if profit < min_profit:
                    print('{} trade amount is {:.4f}, profit is {:.4f} USDT, too low!'.format(asset, cex_quote_buy_amount, profit))
                    continue
                tasks[asset] = threadpool.submit(new_stable_arbitrage, 'buy', symbols[0], symbols[1], dex_quote_trade_amount, cex_base_sell_amount * 10 ** dex_swap.precisions[symbols[0]])
                continue
            elif cex_buy_price < dex_sell_price / (1 + price_percent_difference_threshold):
                dex_base_bal = dex_swap.asset_balance('USDT') * 0.9 * 10 ** 18 / 10 ** 6
                dex_trade_amount = min(dex_base_bal, max_usdt_trade_amount * 10 ** 18)
                print(dex_trade_amount / 10 ** 18)
                price_limit = cex_buy_price * (1 + price_percent_difference_threshold)
                if dex_trade_amount * base_buy_price / (10 ** dex_swap.precisions[symbols[0]]) < 500:
                    print('dex {} amount in is {:.4f}, too low'.format(symbols[0], dex_trade_amount / (10 ** dex_swap.precisions[symbols[0]])))
                    continue
                price, dex_base_trade_amount = dex_swap.binary_search(symbols[0], symbols[1], dex_trade_amount, 'sell', price_limit)
                cex_quote_sell_amount = (dex_base_trade_amount * price) / 10 ** dex_swap.precisions[symbols[0]]
                cex_base_buy_amount = dex_base_trade_amount / 10 ** dex_swap.precisions[symbols[0]]
                profit = cex_quote_sell_amount * quote_sell_price * (1 - fee) - cex_base_buy_amount * base_buy_price * (1 + fee)
                print('\n', '-'*30, '\n{} arbitrage profit is {:.4f}, cex buy price is {:.4f}, amount is {:.4f}, dex sell price is {:.4f}'.format(asset, profit, cex_buy_price, cex_base_buy_amount, dex_sell_price))
                if profit < min_profit:
                    print('{} trade amount is {:.4f}, profit is {:.4f} USDT, too low!'.format(asset, cex_quote_sell_amount, profit))
                    continue
                tasks[asset] = threadpool.submit(new_stable_arbitrage, 'sell', symbols[0], symbols[1], dex_base_trade_amount, cex_quote_sell_amount * 10 ** dex_swap.precisions[symbols[1]])
                continue
    except func_timeout.exceptions.FunctionTimedOut:
        print('main_pair_arbitrage time out')
    except Exception as e:
        print(e)

# egld_swap = EgldSwap()
egld_total_profit = 0
def egld_asset_arbitrage():
    global egld_total_profit
    try:
        egld_price_percent_difference_threshold = 0.004
        dex_sell_price = egld_swap.get_price('sell')
        dex_buy_price = egld_swap.get_price('buy')
        cex_buy_price, cex_buy_volume, cex_sell_price, cex_sell_volume = get_depth_volume_price(4, binance.depths, 'EGLDUSDT')
        # print(dex_sell_price, cex_buy_price, (dex_sell_price - cex_buy_price) / dex_sell_price)
        # print(cex_sell_price, dex_buy_price, (cex_sell_price - dex_buy_price) / dex_buy_price)
        if cex_sell_price > dex_buy_price * (1 + egld_price_percent_difference_threshold):
            wegld_bal = egld_swap.asset_balance('WEGLD')
            usdc_bal = egld_swap.asset_balance('USDC')
            if usdc_bal > 5000:
                usdc_bal = 5000
            if usdc_bal < 500:
                return
            wegld_buy_amount = (usdc_bal / cex_buy_price) * 0.95
            print('EGLD: cex sell amount is {:.4f}, cex sell price is {:.4f}, dex buy price is {:.4f}'.format(wegld_buy_amount, cex_sell_price, dex_buy_price))
            ret, used_usdc_amount = egld_swap.buy(wegld_buy_amount, dex_buy_price)
            if not ret:
                return
            binance.sell('EGLD', wegld_buy_amount, cex_sell_price)
            profit = (wegld_buy_amount * cex_sell_price) * (1 - fee) - used_usdc_amount
            egld_total_profit += profit
            print('EGLD：this arbitrage profit is {:.4f}, total profit is {:.4f}'.format(profit, egld_total_profit))
        elif cex_buy_price < dex_sell_price / (1 + egld_price_percent_difference_threshold):
            wegld_bal = egld_swap.asset_balance('WEGLD')
            usdc_bal = egld_swap.asset_balance('USDC')
            if wegld_bal * dex_sell_price > 5000:
                wegld_bal = 5000 / dex_sell_price
            if wegld_bal < 2:
                return
            wegld_sell_amount = wegld_bal * 0.95
            print('EGLD: cex buy amount is {:.4f}, cex buy price is {:.4f}, dex buy price is {:.4f}'.format(wegld_sell_amount, cex_buy_price, dex_sell_price))
            ret, get_usdc_amount = egld_swap.sell(wegld_sell_amount, dex_sell_price)
            if not ret:
                return
            binance.buy('EGLD', wegld_sell_amount, cex_buy_price)
            profit = get_usdc_amount - wegld_sell_amount * cex_buy_price * (1 - fee)
            egld_total_profit += profit
            print('EGLD：this arbitrage profit is {:.4f}, total profit is {:.4f}'.format(profit, egld_total_profit))
    except func_timeout.exceptions.FunctionTimedOut:
        print('egld arbitrage time out')
    except Exception as e:
        print(e)


def set_working_flag(status: str):
    file_path =  os.path.dirname(os.path.dirname(os.path.realpath(__file__))) + '/tools/flag'
    with open(file_path, 'w') as f:
        f.write(status)

def egld_work_thread():
    while(True):
        egld_asset_arbitrage()
        time.sleep(3)

def main():
    binance.start_update_depth()
    # t = threading.Thread(target=egld_work_thread)
    # t.start()
    while True:
        try:
            dex_swap.check_status()
            dex_swap.update_information()
            l = clear_complete_task(tasks)
            if l == 0:
                binance.reset_bal_reduce()
                dex_swap.reset_bal_reduce()
            asset_arbitrage()
            stable_asset_arbitrage()
            l = clear_complete_task(tasks)
            if l > 0:
                set_working_flag('true')
            else:
                set_working_flag('false')
        except Exception as e:
            print(e)
        except func_timeout.exceptions.FunctionTimedOut:
            print('main update_information time out')
        time.sleep(2)


if __name__ == '__main__':
    main()

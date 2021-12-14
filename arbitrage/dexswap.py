import math
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import os
from os import path
import sys
file_path = os.path.dirname(os.path.realpath(__file__))
parent_path = os.path.dirname(file_path)
sys.path.append(parent_path)
from arbitrage.abi import *
from arbitrage.config import *
import json
import func_timeout
from func_timeout import func_set_timeout
from tronpy import Tron
from tronpy.tron import Trx
from tronpy import keys
from tronpy.providers import HTTPProvider

from arbitrage.logger import Logger
from arbitrage.calladmin import *

from Crypto.Cipher import AES
from binascii import b2a_hex, a2b_hex
from  Crypto import Random
import getpass

class PrpCrypt(object):
    
    def __init__(self, key):
        self.key = self.get16(key)
        self.mode = AES.MODE_CBC

    def get16(self, s):
        while len(s) % 16 != 0:
            s += '\0'
        return str.encode(s)

    # 加密函数，如果text不足16位就用空格补足为16位，
    # 如果大于16当时不是16的倍数，那就补足为16的倍数。
    def encrypt(self, text):
        text = text.encode('utf-8')

        cryptor = AES.new(self.key, self.mode,self.key)
        # 这里密钥key 长度必须为16（AES-128）,
        # 24（AES-192）,或者32 （AES-256）Bytes 长度
        # 目前AES-128 足够目前使用
        length = 16
        count = len(text)
        if count < length:
            add = (length - count)
            # \0 backspace
            # text = text + ('\0' * add)
            text = text + ('\0' * add).encode('utf-8')
        elif count > length:
            add = (length - (count % length))
            # text = text + ('\0' * add)
            text = text + ('\0' * add).encode('utf-8')
        self.ciphertext = cryptor.encrypt(text)
        # 因为AES加密时候得到的字符串不一定是ascii字符集的，输出到终端或者保存时候可能存在问题
        # 所以这里统一把加密后的字符串转化为16进制字符串
        return b2a_hex(self.ciphertext)

    # 解密后，去掉补足的空格用strip() 去掉
    def decrypt(self, text):
        cryptor = AES.new(self.key, self.mode, self.key)
        plain_text = cryptor.decrypt(a2b_hex(text))
        # return plain_text.rstrip('\0')
        return bytes.decode(plain_text).rstrip('\0')

def timestamp():
    return int(time.time())

class DexSwap(object):
    def __init__(self, _log):
        login = True
        if _log is None:
            login = False
        self.init(login)
        self.log = _log
        self.precisions = self.get_precision()
        self.balances = {}
        self.reserves = {}
        self.update_balances = True
        self.bal_reduced = {}
        self.stable_prices = {}
        self.last_order_time = int(time.time())

    def init(self, login):
        self.from_addr = 'TZFUe7XD2Di4G4pha8uhQnAXfstfMbRTp6'
        enc_priv = '27cefa28528c6782b4e0a0d409bba950f74a579e6fe1cd8e44285a26c88271487da7d1f8f3c43b1ffc66c70475cd130ab6e6a2184edd6f9d47a3719a7f0d5b810acefab33924b7641d130ee50fe6f3ca'
        passwd = getpass.getpass("请输入你的密码：")
        pc = PrpCrypt(passwd)
        priv = pc.decrypt(enc_priv)
        self.priv_key = keys.PrivateKey.fromhex(priv)
        self.client = Tron(HTTPProvider(api_key=["8514e76d-0956-48d4-8bbd-3dc7993b966c", '07260169-2bfa-44fc-bfa1-fdfc1f8f7fca', 
            '76ca8b14-d6ca-46cc-817e-abd676093344', 'd5150c11-3d41-4596-b49d-7cfb5dc1d261', 'f8649359-73b3-41dd-b327-9be9cad7bed1', 
            'dc607e4b-a6d4-473d-9ef8-34b32378010b']))
        self.exchanges = dict()
        swap_abi = json.loads(justswap_abi)
        for asset in assets[1:]:
            self.exchanges[asset] = self.client.get_contract(eval(asset+'_TRX'))
            self.exchanges[asset].abi = swap_abi
            # time.sleep(1)
            # print(asset)
        q_abi = json.loads(query_abi)
        self.query = self.client.get_contract(query_contract)
        self.query.abi = q_abi
        self.stable_exchange = self.client.get_contract(stable_exchange_contract)
        s_ex_abi = json.loads(stable_exchange_abi)
        self.stable_exchange.abi = s_ex_abi

        time.sleep(1)
        print('init finished')
        
    def get_precision(self):
        precisions = {}
        precisions['TRX'] = 6
        abi = json.loads(trc20_abi)
        for asset in assets[1:]:
            token = self.client.get_contract(eval(asset))
            precisions[asset] = token.functions.decimals()
        return precisions

    def asset_balance(self, asset):
        if asset == 'TRX':
            return self.balances[asset] - self.bal_reduced[asset] - 1000 * 10 ** self.precisions['TRX']
        return self.balances[asset] - self.bal_reduced[asset]

    def reset_bal_reduce(self):
        for asset in assets:
            self.bal_reduced[asset] = 0


    def update_information(self):
        asset_addrs = [eval(asset) for asset in assets[1:]]
        pairs = [eval(asset+'_TRX') for asset in assets[1:]]
        (reserves, balances, sun_outs) = self.query.functions.get_all_information(self.from_addr, asset_addrs, pairs, 15000)
        for i in range(len(assets)):
            self.balances[assets[i]] = balances[i]
        i = 0
        for asset in assets[1:]:
            self.reserves[asset+'_TRX'] = (reserves[i][0], reserves[i][1])
            i += 1
        # self.stable_prices['USDJ_BUY'] = (10 ** 18 * 15000) / sun_outs[1]
        self.stable_prices['TUSD_BUY'] = (10 ** 18 * 15000) / sun_outs[3]
        # self.stable_prices['USDJ_SELL'] = sun_outs[0] / (10 ** 6 * 15000)
        self.stable_prices['TUSD_SELL'] = sun_outs[2] / (10 ** 6 * 15000)


    def getOutputAmount(self, amountIn, tokenIn, tokenOut):
        pair = tokenIn + tokenOut
        if tokenIn+'_'+tokenOut in self.reserves:
            reserve = self.reserves[tokenIn+'_'+tokenOut]
            reserveIn = reserve[0]
            reserveOut = reserve[1]
        elif tokenOut+'_'+tokenIn in self.reserves:
            reserve = self.reserves[tokenOut+'_'+tokenIn]
            reserveIn = reserve[1]
            reserveOut = reserve[0]
        else:
            return 0
        assert amountIn > 0 and reserveIn > 0 and reserveOut > 0
        amountInWithFee = amountIn * 997
        numerator = amountInWithFee * reserveOut
        denominator = reserveIn * 1000 + amountInWithFee
        amountOut = numerator // denominator
        return amountOut

    def get_price(self, base_asset, quote_asset, side, input_amount):
        if side.lower() == 'buy':
            output_amt = self.getOutputAmount(input_amount, quote_asset, base_asset)
            return (input_amount / 10 ** self.precisions[quote_asset]) / (output_amt / 10 ** self.precisions[base_asset])
        elif side.lower() == 'sell':
            output_amt = self.getOutputAmount(input_amount, base_asset, quote_asset)
            return (output_amt / 10 ** self.precisions[quote_asset]) / (input_amount / 10 ** self.precisions[base_asset])

    @func_set_timeout(28)
    def sell(self, base_asset, quote_asset, amount_in):
        amount_in = int(amount_in)
        org_amount_in = amount_in
        amount_out = 0
        gasfee = 0
        succeed = False
        try:
            amount_out = self.getOutputAmount(amount_in, base_asset, quote_asset)
            org_amount_out = amount_out
            amount_out = int(amount_out * slippage_numerator / slippage_senominator)
            txn = (
                self.exchanges[base_asset].functions.tokenToTrxSwapInput(amount_in, amount_out, timestamp() + 10)
                .with_owner(self.from_addr)
                .fee_limit(1_000_000_000)
                .build()
                .sign(self.priv_key)
            )
            print("dex sell {} txid={}".format(base_asset, txn.txid))
            ret=txn.broadcast()
            tx = ret.wait()
            gasfee = tx['fee'] / 10 ** self.precisions['TRX']
            if tx['receipt']['result'] != 'SUCCESS':
                self.log.logger.info('dex sell fail')
                raise Exception(tx['receipt']['result'])
            amount_out = org_amount_out / 10 ** self.precisions[quote_asset]
            self.log.logger.info('dex sell txid: {}'.format(tx['id']))
            self.log.logger.info('dex sell {} for {}: amount_in={:.4f}, amount_out={:.4f}'.format(base_asset, quote_asset, org_amount_in / 10 ** self.precisions[base_asset], amount_out))
            succeed = True
            self.last_order_time = int(time.time())
        except Exception as e:
            self.log.logger.info('dex sell fail: {}'.format(str(e)))
            gasfee = 0
            amount_out = 0
            succeed = False
        finally:
            self.update_balances = True
            return succeed, amount_out, gasfee
            
    @func_set_timeout(28)
    def buy(self, base_asset, quote_asset, amount_in):
        amount_in = int(amount_in)
        amount_out = 0
        gasfee = 0
        succeed = False
        try:
            amount_out = self.getOutputAmount(amount_in, quote_asset, base_asset)
            org_amount_out = amount_out
            amount_out = int(amount_out * slippage_numerator / slippage_senominator)
            txn = (
                self.exchanges[base_asset].functions.trxToTokenSwapInput.with_transfer(amount_in)(amount_out, timestamp() + 10)
                .with_owner(self.from_addr)
                .fee_limit(1_000_000_000)
                .build()
                .sign(self.priv_key)
            )
            print("dex buy {} txid={}".format(base_asset, txn.txid))
            ret=txn.broadcast()
            tx = ret.wait()
            gasfee = tx['fee'] / 10 ** self.precisions['TRX']
            if tx['receipt']['result'] != 'SUCCESS':
                self.log.logger.info('dex buy fail')
                raise Exception(tx['receipt']['result'])
            amount_out = org_amount_out / 10 ** self.precisions[base_asset]
            self.log.logger.info('dex buy txid: {}'.format(tx['id']))
            self.log.logger.info('dex buy {} used {}: amount_in={:.4f}, amount_out={:.4f}'.format(base_asset, quote_asset, amount_in / 10 ** self.precisions['TRX'], amount_out))
            succeed = True
            self.last_order_time = int(time.time())
        except Exception as e:
            self.log.logger.info('dex buy fail: {}'.format(str(e)))
            gasfee = 0
            amount_out = 0
            succeed = False
        finally:
            self.update_balances = True
            return succeed, amount_out, gasfee

    @func_set_timeout(28)
    def sell_stable_coin(self, base_asset, quote_asset, amount_in):
        amount_in = int(amount_in)
        org_amount_in = amount_in
        amount_out = 0
        gasfee = 0
        succeed = False
        try:
            amount_out = self.getOutputAmount(amount_in, base_asset, quote_asset)
            org_amount_out = amount_out
            amount_out = int(amount_out * slippage_numerator / slippage_senominator)
            u_amount_in = int((amount_in / 10 ** 12) * self.stable_prices[base_asset+'_BUY'])
            print('sell stable coin {}, USDT amount in is {}'.format(base_asset, u_amount_in / 10 ** 6))
            # if base_asset == 'USDJ':
            #     jpair = USDJ_TRX
            #     mid_coin_id = 0
            if base_asset == 'TUSD':
                jpair = TUSD_TRX
                mid_coin_id = 1
            txn = (
                self.stable_exchange.functions.uToTrx(jpair, mid_coin_id, u_amount_in, 1, amount_out, timestamp() + 10)
                .with_owner(self.from_addr)
                .fee_limit(1_000_000_000)
                .build()
                .sign(self.priv_key)
            )
            print("dex sell {} txid={}".format(base_asset, txn.txid))
            ret=txn.broadcast()
            tx = ret.wait()
            gasfee = tx['fee'] / 10 ** self.precisions['TRX']
            if tx['receipt']['result'] != 'SUCCESS':
                self.log.logger.info('dex sell fail')
                raise Exception(tx['receipt']['result'])
            amount_out = org_amount_out / 10 ** self.precisions[quote_asset]
            self.log.logger.info('dex sell txid: {}'.format(tx['id']))
            self.log.logger.info('dex sell {} for {}: amount_in={:.4f}, amount_out={:.4f}'.format(base_asset, quote_asset, org_amount_in / 10 ** self.precisions[base_asset], amount_out))
            succeed = True
            self.last_order_time = int(time.time())
        except Exception as e:
            self.log.logger.info('dex sell fail: {}'.format(str(e)))
            gasfee = 0
            amount_out = 0
            succeed = False
        finally:
            self.update_balances = True
            return succeed, amount_out, gasfee
            
    @func_set_timeout(28)
    def buy_stable_coin(self, base_asset, quote_asset, amount_in):
        amount_in = int(amount_in)
        amount_out = 0
        gasfee = 0
        succeed = False
        try:
            amount_out = self.getOutputAmount(amount_in, quote_asset, base_asset)
            org_amount_out = amount_out
            amount_out = int(amount_out * slippage_numerator / slippage_senominator)
            u_amount_out = int((amount_out / 10 ** 12) / self.stable_prices[base_asset + '_SELL'])
            print('buy stable coin {}, USDT amount out is {}'.format(base_asset, u_amount_out / 10 ** 6))
            # if base_asset == 'USDJ':
            #     jpair = USDJ_TRX
            #     mid_coin_id = 0
            if base_asset == 'TUSD':
                jpair = TUSD_TRX
                mid_coin_id = 1
            txn = (
                self.stable_exchange.functions.trxToU.with_transfer(amount_in)(jpair, mid_coin_id, 1, u_amount_out, timestamp() + 10)
                .with_owner(self.from_addr)
                .fee_limit(1_000_000_000)
                .build()
                .sign(self.priv_key)
            )
            print("dex buy {} txid={}".format(base_asset, txn.txid))
            ret=txn.broadcast()
            tx = ret.wait()
            gasfee = tx['fee'] / 10 ** self.precisions['TRX']
            if tx['receipt']['result'] != 'SUCCESS':
                self.log.logger.info('dex buy fail')
                raise Exception(tx['receipt']['result'])
            amount_out = org_amount_out / 10 ** self.precisions[base_asset]
            self.log.logger.info('dex buy txid: {}'.format(tx['id']))
            self.log.logger.info('dex buy {} used {}: amount_in={:.4f}, amount_out={:.4f}'.format(base_asset, quote_asset, amount_in / 10 ** self.precisions['TRX'], amount_out))
            succeed = True
            self.last_order_time = int(time.time())
        except Exception as e:
            self.log.logger.info('dex buy fail: {}'.format(str(e)))
            gasfee = 0
            amount_out = 0
            succeed = False
        finally:
            self.update_balances = True
            return succeed, amount_out, gasfee


    def binary_search(self, base_asset, quote_asset, current_commitment, side, price_limit):
        max_search = 100
        max_current_commitment = current_commitment
        next_step_size = int(current_commitment / 2)
        price = price_limit
        ret_current_commitment = current_commitment
        for i in range(max_search):
            if next_step_size < 10000:
                break
            if side == 'buy':
                price = self.get_price(base_asset, quote_asset, side, current_commitment)
                if price > price_limit:
                    current_commitment = current_commitment - next_step_size
                    next_step_size = int(next_step_size / 2)
                    continue
                elif price < search_stop_threshold * price_limit:
                    current_commitment = current_commitment + next_step_size
                    next_step_size = int(next_step_size / 2)
                    continue
                else:
                    break
            else:
                price = self.get_price(base_asset, quote_asset, side, current_commitment)
                if price < price_limit:
                    current_commitment = current_commitment - next_step_size
                    next_step_size = int(next_step_size / 2)
                    continue
                elif price > price_limit / search_stop_threshold:
                    current_commitment = current_commitment + next_step_size
                    next_step_size = int(next_step_size / 2)
                    continue
                else:
                    break
        ret_current_commitment = min(max_current_commitment, current_commitment)
        return price, ret_current_commitment
    
    def approve(self, asset):
        try:
            abi = json.loads(trc20_abi)
            print(eval(asset))
            token = self.client.get_contract(eval(asset))
            token.abi = abi
            txn = (
                token.functions.approve(eval(asset+'_TRX'), 2**256-1)
                .with_owner(self.from_addr)
                .fee_limit(1_000_000_000)
                .build()
                .sign(self.priv_key)
            )
            txn.broadcast().wait()
        except Exception as e:
            print(e)
            time.sleep(1)
            return self.approve(asset)

    def stable_exchange_approve(self, asset, spender):
        print(eval(asset))
        txn = (
            self.stable_exchange.functions.approveSpender(eval(asset), spender, 2**256-1)
            .with_owner(self.from_addr)
            .fee_limit(1_000_000_000)
            .build()
            .sign(self.priv_key)
        )
        txn.broadcast().wait()

    # @func_set_timeout(20)
    def transfer(self, asset, to, amount):
        amount = int(amount)
        print(asset, to, amount)
        if asset == 'TRX':
            trx = Trx(self.client)
            txn = trx.transfer(self.from_addr, to, amount).build().sign(self.priv_key)
            tx=txn.broadcast().wait()
            return tx['id']
        # elif asset == 'BTT':
        else:
            assert asset != 'BTT'
            abi = json.loads(trc20_abi)
            token = self.client.get_contract(eval(asset))
            token.abi = abi
            txn = (
                token.functions.transfer(to, amount)
                .with_owner(self.from_addr)
                .fee_limit(1_000_000_000)
                .build()
                .sign(self.priv_key)
            )
            tx=txn.broadcast().wait()
            return tx['id']

    def transfer_btt(self, to, amount):
        amount = int(amount)
        trx = Trx(self.client)
        txn = trx.asset_transfer(self.from_addr, to, amount, 1002000).build().sign(self.priv_key)
        tx=txn.broadcast().wait()
        return tx['id']

    def deposit_btt(self, amount):
        amount = int(amount)
        abi = json.loads(wbtt_abi)
        wbtt_address = 'TKfjV9RNKJJCqPvBtK8L7Knykh7DNWvnYt'
        token = self.client.get_contract(wbtt_address)
        token.abi = abi
        txn = (
            token.functions.deposit
            .with_asset_transfer(amount, 1002000)
            .call()
            .with_owner(self.from_addr)
            .fee_limit(1_000_000_000)
            .build()
            .sign(self.priv_key)
        )
        tx=txn.broadcast().wait()
        return tx['id']
    
    def withdraw_btt(self, amount):
        amount = int(amount)
        abi = json.loads(wbtt_abi)
        wbtt_address = 'TKfjV9RNKJJCqPvBtK8L7Knykh7DNWvnYt'
        token = self.client.get_contract(wbtt_address)
        token.abi = abi
        txn = (
            token.functions.withdraw(amount)
            .with_owner(self.from_addr)
            .fee_limit(1_000_000_000)
            .build()
            .sign(self.priv_key)
        )
        tx=txn.broadcast().wait()
        return tx['id']

    def get_btt_balance(self):
        balance = self.client.get_account_asset_balance(self.from_addr, token_id=1002000)
        return balance

    def check_status(self):
        return
        now = int(time.time())
        if now - self.last_order_time > 800:
            self.last_order_time = now
            call_admin()

    def approve_mexchange(self, asset):
        try:
            abi = json.loads(trc20_abi)
            print(eval(asset))
            token = self.client.get_contract(eval(asset))
            token.abi = abi
            txn = (
                token.functions.approve(stable_exchange_contract, 2**256-1)
                .with_owner(self.from_addr)
                .fee_limit(1_000_000_000)
                .build()
                .sign(self.priv_key)
            )
            txn.broadcast().wait()
        except Exception as e:
            print(e)
            time.sleep(1)
            return self.approve(asset)

if __name__ == "__main__":
    log = Logger('all.log',level='info')
    dex_swap = DexSwap(log)
    # dex_swap.approve('USDC')
    print(dex_swap.precisions)
    # dex_swap.stable_exchange_approve('USDJ', sun_stable_exchange)
    # dex_swap.stable_exchange_approve('TUSD', sun_stable_exchange)
    # dex_swap.stable_exchange_approve('USDT', sun_stable_exchange)

    # dex_swap.stable_exchange_approve('USDJ', USDJ_TRX)
    # dex_swap.stable_exchange_approve('TUSD', TUSD_TRX)
    # dex_swap.stable_exchange_approve('USDT', USDT_TRX)
    
    # print(dex_swap.precisions)
    # for asset in assets[1:]:
    #     dex_swap.approve(asset)
    #     time.sleep(1)
    # dex_swap.get_pairs()
    # dex_swap.update_information()
    # print(dex_swap.stable_prices)
    # print(dex_swap.reserves)
    # print(dex_swap.reserves)
    # print(dex_swap.precisions)
    # print(dex_swap.buy('USDT', 'TRX', 10**6))
    # print(dex_swap.sell('USDT', 'TRX', 0.2 * 10 ** dex_swap.precisions['USDT']))
    # amount = dex_swap.getOutputAmount(10000 * 10 ** 6, 'HUSD', 'BTC')
    # print(amount)
    # print(dex_swap.reserves)
    # print(dex_swap.balances)
    # for asset in assets:
    #     print('{} balance={}'.format(asset, dex_swap.balances[asset] / 10 ** dex_swap.precisions[asset]))
    # pairs = [asset+'_TRX' for asset in assets[1:]]
    # for asset in assets[1:]:
    #     pair = asset+'_TRX'
    #     buy_price = 0.061418 * dex_swap.get_price(asset, 'TRX', 'buy', 100 * 10 ** dex_swap.precisions['TRX'])
    #     sell_price = 0.061418 * dex_swap.get_price(asset, 'TRX', 'sell', 100 / buy_price * 10 ** dex_swap.precisions[asset])
    #     print('{} = {}, {}'.format(pair, buy_price, sell_price))

    # dex_swap.get_pairs()
    # dex_swap.buy('LTC', 'USDT', 10**18)

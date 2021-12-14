import time
import os
from os import path
import sys
file_path = os.path.dirname(os.path.realpath(__file__))
parent_path = os.path.dirname(file_path)
sys.path.append(parent_path)
from arbitrage.logger import Logger
from arbitrage.calladmin import *
from arbitrage.erdsdk.tools.client import *
import func_timeout
from func_timeout import func_set_timeout

def timestamp():
    return int(time.time())

token_ids = {'WEGLD': 'WEGLD-bd4d79', 'USDC': 'USDC-c76f1f'}
USDC_EGLD = 'erd1qqqqqqqqqqqqqpgqeel2kumf0r8ffyhth7pqdujjat9nx0862jpsg2pqaq'

class EgldSwap(object):
    def __init__(self):
        self.precisions = self.get_precision()
        self.balances = {}
        init_egld_client()
        self.account = 'erd1gx76al98vt25tvndwemr6z34zv94xaj44le7a4zmzzr69mpzp8gsv3m403'
        self.update_esdt_token_balances()

    def get_precision(self):
        precisions = {'WEGLD': 18, 'USDC': 6}
        return precisions

    def asset_balance(self, asset):
        return self.balances[asset] / 10 ** self.precisions[asset]

    def update_esdt_token_balances(self):
        balances = proxy_get_account_esdt_balance(self.account)
        self.balances['WEGLD'] = int(balances[token_ids['WEGLD']]['balance'])
        self.balances['USDC'] = int(balances[token_ids['USDC']]['balance'])

    def get_amount_out(self, token_in, amount):
        pair_address = USDC_EGLD
        token_in_id = token_ids[token_in]
        return get_amount_out(token_in_id, int(amount), pair_address)

    def get_price(self, side):
        if side.lower() == 'buy':
            output_amt = self.get_amount_out('USDC', 10000 * 10 ** 6)
            return 10000 / (output_amt / 10 ** self.precisions['WEGLD'])
        elif side.lower() == 'sell':
            output_amt = self.get_amount_out('WEGLD', 40 * 10 ** 18)
            return (output_amt / 10 ** self.precisions['USDC']) / 40

    # @func_set_timeout(28)
    def sell(self, wegld_amount, price):
        min_amount_out = int(wegld_amount * price * 0.999 * 10 ** self.precisions['USDC'])
        amount_in = int(wegld_amount * 10 ** self.precisions['WEGLD'])
        succeed = False
        try:
            resp_obj = swap(self.account, token_ids['WEGLD'], amount_in, token_ids['USDC'], token_out_min_amount = min_amount_out)
            if resp_obj['type'] != 'normal' or resp_obj['status'] != 'success':
                succeed = False
                print('sell failed')
                print(ret)
                return
            contract_result = resp_obj['smartContractResults'][0]
            if 'returnMessage' in contract_result:
                succeed = False
                print('sell failed')
                print(contract_result['returnMessage'])
                return
            print('dex sell wgld success: sell wegld={:.4f}, get usdc={:.4f}'.format(wegld_amount, wegld_amount * price * 0.999))
            succeed = True
        except Exception as e:
            print('dex sell fail: {}'.format(str(e)))
            succeed = False
        finally:
            return succeed, min_amount_out
            
    # @func_set_timeout(28)
    def buy(self, wegld_amount, price):
        amount_in = int(wegld_amount * price * 1.001 * 10 ** self.precisions['USDC'])
        min_amount_out = int(wegld_amount * 10 ** self.precisions['WEGLD'])
        succeed = False
        try:
            resp_obj = swap(self.account, token_ids['USDC'], amount_in, token_ids['WEGLD'], token_out_min_amount = min_amount_out)
            if resp_obj['type'] != 'normal' or resp_obj['status'] != 'success':
                succeed = False
                print('buy failed')
                print(ret)
                return
            contract_result = resp_obj['smartContractResults'][0]
            if 'returnMessage' in contract_result:
                succeed = False
                print('buy failed')
                print(contract_result['returnMessage'])
                return
            print('dex buy wgld success: buy wegld={:.4f}, used usdc={:.4f}'.format(wegld_amount, wegld_amount * price * 1.001))
            succeed = True
        except Exception as e:
            print('dex buy fail: {}'.format(str(e)))
            succeed = False
        finally:
            return succeed, amount_in
    
    def show_account_all_balance(self):
        self.update_esdt_token_balances()
        egld_bal = proxy_get_account_balance(self.account)
        price = self.get_price('buy')
        print('WEGLD: {:.4f}'.format(self.balances['WEGLD'] / 10 ** self.precisions['WEGLD']))
        print('EGLD: {:.4f}'.format(egld_bal / 10 ** self.precisions['WEGLD']))
        print('USDC: {:.4f}'.format(self.balances['USDC'] / 10 ** self.precisions['USDC']))
        total = self.balances['USDC'] / 10 ** self.precisions['USDC'] + price * (egld_bal + self.balances['WEGLD']) / 10 ** self.precisions['WEGLD']
        print('total value: {:.1f} USDT'.format(total))

    def transfer_2_cex(self, amount):
        send_platform_token(self.account, 'erd1gqq3y40vq95dmahcgttz9hdwru4tjl8eflyaz4gx0ph27yaz4e6s6pve8c', amount)

    def wrap_egld(self, amount):
        wrap_egld(self.account, amount)

if __name__ == "__main__":
    egld_swap = EgldSwap()
    # egld_swap.wrap_egld(int(3 * 10 ** 18))
    # egld_swap.show_account_all_balance()
    # egld_swap.transfer_2_cex(int(0.01 * 10 ** 18))
    price_sell = egld_swap.get_price('sell')
    # print(price_sell)
    egld_swap.sell(0.001, price_sell * 1.1)
    # egld_swap.update_esdt_token_balances()
    # get_pair_address()
    # egld_swap.get_amount_out('USDC', 10 ** 6)
    # egld_swap.get_amount_out('WEGLD', 10 ** 18)
    # new_wallet()
    # show_all_accounts()
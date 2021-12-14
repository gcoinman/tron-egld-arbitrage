#encoding=‘utf-8’
from common import *
import time
import requests
import json

def check_failed_reiled_record():
    response = client.get_withdraw_history(status=6)
    withdraw_list = response['withdrawList']
    print('total withdraw count is {}'.format(len(withdraw_list)))
    for item in withdraw_list:
        txid = item['txId']
        if item['network'] != 'TRX' or 'Internal transfer' in txid:
            continue
        print(txid)
        url = "https://apilist.tronscan.org/api/transaction-info?hash=" + txid
        r = requests.get(url)
        resp = json.loads(r.text)
        if resp['confirmed'] and not resp['revert']:
            print('pass')
        else:
            assert False
# check_failed_reiled_record()

response = client.get_withdraw_history(status=2, startTime = int(time.time() * 1000) - 40000 * 1000)
withdraw_list = response['withdrawList']
response = client.get_withdraw_history(status=6, startTime = int(time.time() * 1000) - 40000 * 1000)
withdraw_list += response['withdrawList']
print(withdraw_list)

# deposit_list = client.get_deposit_history(status=1, startTime = int(time.time() * 1000) - 40000 * 1000)
# print(deposit_list['depositList'])
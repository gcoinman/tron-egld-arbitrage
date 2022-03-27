#encoding=‘utf-8’
from common import *
from arbitrage.egldswap import EgldSwap


if __name__ == "__main__":
    egld_swap = EgldSwap()
    deposit_amount_str = input("input deposit amount:")
    deposit_amount2_str = input("input deposit amount again:")
    deposit_amount = float(deposit_amount_str)
    deposit_amount2 = float(deposit_amount2_str)
    assert deposit_amount == deposit_amount2
    egld_swap.transfer_2_cex(int(deposit_amount2 * 10 ** 18))
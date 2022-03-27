#encoding=‘utf-8’
from common import *
from arbitrage.egldswap import EgldSwap


if __name__ == "__main__":
    egld_swap = EgldSwap()
    wrap_amount_str = input("input wrap amount:")
    wrap_amount = float(wrap_amount_str)
    egld_swap.unwrap_egld(int(wrap_amount * 10 ** 18))
#encoding=‘utf-8’
from common import *
from arbitrage.egldswap import EgldSwap


if __name__ == "__main__":
    egld_swap = EgldSwap()
    egld_swap.show_account_all_balance()
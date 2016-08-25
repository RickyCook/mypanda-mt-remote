#!/usr/bin/env python
"""
A super dumb example server that ensures a buy order after an up bar, a sell
order after a down bar, and closes all trades after a bar with no change in
open/close
"""
import logging

from functools import partial

from mt_remote.order import Order, OrderSignal
from mt_remote.source import MtEventSource

source = MtEventSource()

@source.on_bar
def bar_handler(bar):
    logging.debug("Got bar %s", bar)
    if source.order_in_progress:
        logging.error("Order in progress: %s", source.order)
    else:
        if bar.close > bar.open:
            logging.info("Placing BUY because close (%s) > open (%s)",
                         bar.close, bar.open)
            source.update_order(Order(signal=OrderSignal.buy, volume=2))
        elif bar.close < bar.open:
            logging.info("Placing SELL because close (%s) < open (%s)",
                         bar.close, bar.open)
            source.update_order(Order(signal=OrderSignal.sell, volume=2))
        else:
            logging.info("Closing trades because close (%s) = open (%s)",
                         bar.close, bar.open)
            source.update_order(Order())


@source.on_tick
def tick_handler(tick):
    logging.debug("Got tick %s", tick)


@source.on_balance
def balance_handler(balance):
    logging.debug("Got balance %s", balance)


logging.basicConfig(level=logging.DEBUG)
source.start()

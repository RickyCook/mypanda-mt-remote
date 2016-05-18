""" Orders to be fulfilled by the event source """
from enum import Enum

from .util import repr_str


class OrderSignal(Enum):
    """ Order signal to send to MT for fulfillment """
    buy = 'buy'
    sell = 'sell'
    out = 'out'


class Order(object):
    """ Basic order to place with MT """
    def __init__(self, signal=None, volume=None):
        """
        :param OrderSignal signal: type of order to place
        :param int volume: amount the order should trade

        :raises ValueError: If ``signal`` isn't out, and volume isn't set

        Examples:
          >>> Order()
          <Order: signal=out>
          >>> Order(signal=OrderSignal.out)
          <Order: signal=out>

          >>> Order(signal=OrderSignal.buy, volume=1)
          <Order: volume=1, signal=buy>

          >>> Order(signal=OrderSignal.sell, volume=1)
          <Order: volume=1, signal=sell>

          Exceptions:

            >>> Order(signal=OrderSignal.buy)
            Traceback (most recent call last):
            ...
            ValueError: Orders other than 'out' must have volume

            >>> Order(signal=OrderSignal.sell)
            Traceback (most recent call last):
            ...
            ValueError: Orders other than 'out' must have volume

            >>> Order(volume=1)
            Traceback (most recent call last):
            ...
            ValueError: Orders of type 'out' must not have volume
            >>> Order(signal=OrderSignal.out, volume=1)
            Traceback (most recent call last):
            ...
            ValueError: Orders of type 'out' must not have volume
        """
        self._signal = signal
        self.volume = volume

        if self.signal == OrderSignal.out:
            if volume is not None:
                raise ValueError("Orders of type 'out' must not have volume")
        else:
            if volume is None:
                raise ValueError("Orders other than 'out' must have volume")

    def __repr__(self):
        """
        Examples:

          >>> Order(signal=OrderSignal.buy, volume=1)
          <Order: volume=1, signal=buy>
          >>> Order(signal=OrderSignal.sell, volume=20)
          <Order: volume=20, signal=sell>
          >>> Order()
          <Order: signal=out>
        """
        def updater(props):
            """ Updater for ``repr_str`` to add ``signal`` text """
            if self.signal is not None:
                props.append(('signal', self.signal.value))

            return props

        return repr_str(self, ('volume',), updater)

    @property
    def signal(self):
        """ Type of order to place. In case this is set to ``None``, this
        will always default to ``OrderSignal.out``

        Examples:

          >>> Order(signal=OrderSignal.buy, volume=1).signal
          <OrderSignal.buy...>

          >>> order = Order()
          >>> order.signal = OrderSignal.sell
          >>> order.signal
          <OrderSignal.sell...>

          When signal is ``None``:

            >>> Order(signal=None).signal
            <OrderSignal.out...>

            >>> Order().signal
            <OrderSignal.out...>

            >>> order = Order()
            >>> order.signal = OrderSignal.sell
            >>> order.signal = None
            >>> order.signal
            <OrderSignal.out...>
        """
        if self._signal is None:
            return OrderSignal.out
        return self._signal

    @signal.setter
    def signal(self, value):
        """ Set the signal """
        self._signal = value

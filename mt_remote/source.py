""" Event sources that give ticks, bars, and fulfill orders """
import csv

from flask import Flask, request

from .bar import Bar
from .exceptions import OrderQueueError
from .order import OrderSignal
from .promise import Promise
from .tick import Tick


class BaseEventSource(object):
    """ HTTP server that responds to MT pushes and triggers events """
    def __init__(self):
        self._tick_handlers = []
        self._bar_handlers = []
        self._balance_handlers = []

        self._order = None
        self._order_promise = None

    def on_tick(self, func):
        """ Decorator to call the function when tick is pushed

        Examples:

          Setup:

            >>> from .tick import Tick

          >>> server = BaseEventSource()
          >>> @server.on_tick
          ... def my_tick_handler(tick):
          ...     print("Tick: '%s'" % tick)
          >>> server._add_tick(Tick(price=20))
          Tick: '<Tick: price=20.0>'
        """
        self._tick_handlers.append(func)
        return func

    def on_bar(self, func):
        """ Decorator to call the function when bar is pushed

        Examples:

          >>> server = BaseEventSource()
          >>> @server.on_bar
          ... def my_bar_handler(tick):
          ...     print("Bar: '%s'" % tick)
          >>> server._add_bar(Bar(open_=20, close=30))
          Bar: '<Bar: open=20.0, close=30.0>'
        """
        self._bar_handlers.append(func)
        return func

    def on_balance(self, func):
        """ Decorator to call the function when balance is pushed

        Examples:

          >>> server = BaseEventSource()
          >>> @server.on_balance
          ... def my_balance_handler(balance):
          ...     print("Balance: '%s'" % balance)
          >>> server._update_balance('test')
          Balance: 'test'
        """
        self._balance_handlers.append(func)
        return func

    _current_price = None

    def _add_tick(self, tick):
        """ Trigger tick handlers """
        if tick.price is not None:
            self._current_price = tick.price

        for func in self._tick_handlers:
            func(tick)

    def _add_bar(self, bar):
        """ Trigger bar handlers

        Examples:

          Setup:

            >>> source = BaseEventSource()

          Updates the current price with close where possible:

            >>> source._add_bar(Bar(open_=10, close=20))
            >>> source._current_price
            20.0

          Updates the current price with open where close is not available:

            >>> source._add_bar(Bar(open_=30))
            >>> source._current_price
            30.0
        """
        if bar.close is not None:
            self._current_price = bar.close
        elif bar.open is not None:
            self._current_price = bar.open

        for func in self._bar_handlers:
            func(bar)

    def _update_balance(self, balance):
        """ Trigger balance update handlers """
        for func in self._balance_handlers:
            func(balance)

    _order = None

    @property
    def order(self):
        """ The current order in the queue, or ``None`` """
        return self._order

    @property
    def order_promise(self):
        """ The currently active order promise, or ``None`` """
        return self._order_promise

    @property
    def order_in_progress(self):
        """ Check if an order is currently being fulfilled """
        return self._order_promise is not None

    def update_order(self, order):
        """ Send an order to the event source for fulfillment ASAP

        :param Order order: Order to start fulfilling

        :raises mt_remote.OrderQueueError: If an order is already queued

        Examples:

          Setup:

            >>> from .order import Order

          Ensure orders are cleared on success:

            >>> source = BaseEventSource()
            >>> promise = source.update_order(Order())
            >>> source.order
            <Order: signal=out>
            >>> source.order_in_progress
            True
            >>> promise.accept()
            >>> source.order
            >>> source.order_in_progress
            False

          Ensure orders are cleared on failure:

            >>> source = BaseEventSource()
            >>> promise = source.update_order(Order())
            >>> source.order
            <Order: signal=out>
            >>> source.order_in_progress
            True
            >>> promise.reject()
            >>> source.order
            >>> source.order_in_progress
            False

          Trying to create multiple orders doesn't send second order, and
          raises an exception:

            >>> source = BaseEventSource()
            >>> source.update_order(Order())
            <mt_remote.promise.Promise...>
            >>> source.update_order(Order())
            Traceback (most recent call last):
            ...
            mt_remote.exceptions.OrderQueueError: Order already being fulfilled
        """
        if self.order_in_progress:
            raise OrderQueueError("Order already being fulfilled")

        def clear_order():
            """ Clear the internal order state; hopefully after order has been
            closed successfully """
            self._order = None
            self._order_promise = None

        promise = Promise().always(lambda *args: clear_order())
        self._order = order
        self._order_promise = promise

        return promise

    def start(self):  # pylint:disable=no-self-use
        """ Start accepting events from the source """
        raise NotImplementedError("Must override start")


class MtEventSource(BaseEventSource):
    """ An event source that gets data, and fills commands on a live MetaTrader
    client

    Examples:

      Setup:

        >>> source = MtEventSource()
        >>> source.APP.config['TESTING'] = True
        >>> client = source.APP.test_client()

      Setup for simple handlers:

        >>> @source.on_tick
        ... def handle_tick(tick):
        ...   print('TICK:', tick)

        >>> @source.on_bar
        ... def handle_bar(bar):
        ...   print('BAR:', bar)

      Gets ticks:

        >>> response = client.post('/report?type=tick', data={
        ...   'tick_ts': '2016.01.02 03:02:00',
        ...   'price': 1.2345,
        ... })
        TICK: <Tick: price=1.2345, tick_ts=2016-01-02T03:02:00+00:00>

        >>> assert response.status_code == 201


      Gets bars:

        >>> response = client.post('/report?type=bar', data={
        ...   'start_ts': '2016.01.02 03:02:00',
        ...   'open_': 1.2345,
        ...   'high': 2.3456,
        ...   'low': 0.1234,
        ...   'close': 1.2468,
        ...   'volume': 20,
        ... })
        BAR: <Bar: open=1.2345, high=2.3456, low=0.1234, close=1.2468, volume=20, start_ts=2016-01-02T03:02:00+00:00>

        >>> assert response.status_code == 201

      No report type is a connection check for MetaTrader init:

        >>> client.get('/report').status_code
        200
    """

    def __init__(self):
        super(MtEventSource, self).__init__()
        self.APP = Flask(__name__)

        @self.APP.route('/report', methods=['GET', 'POST'])
        def report():
            """ All-in-one URL for information from MetaTrader """
            report_type = request.args.get('type', None)

            if report_type == 'bar':
                self._add_bar(
                    Bar(**{
                        key: request.form.get(key, None)
                        for key in (
                            'start_ts',
                            'open_',
                            'high',
                            'low',
                            'close',
                            'volume',
                        )
                    })
                )
                return 'Reported', 201

            elif report_type == 'tick':
                tick = Tick(**{
                    key: request.form.get(key, None)
                    for key in (
                        'tick_ts',
                        'price',
                    )
                })
                self._add_tick(tick)
                return 'Reported', 201

            elif report_type == None:
                return 'Connected', 200

            return 'Invalid type', 400

    def start(self):
        """ Start the server for MetaTrader to connect to """
        self.APP.run(host='0.0.0.0', port=80)


DEFAULT_CSV_COLS = ('start_ts', 'open_', 'high', 'low', 'close', 'volume')


class CsvEventSource(BaseEventSource):
    """ An event source that gets ``Bar`` data from a CSV file

    :param str path: Path to the CSV file to load
    :param handle: File-like handle object to read from
    :param float balance: Initial account balance
    :param cols: Attribute names for the columns in the CSV
    :type cols: tuple, list
    :param dict reader_kwargs: Additional kwargs for the ``csv.reader``

    :raises ValueError: If both ``path``, and ``handle`` are given
    :raises ValueError: If neither ``path``, nor ``handle`` are given

    Examples:

      Setup:

        >>> from io import StringIO
        >>> from .order import Order

      The ``on_bar`` decorator marks a function to receive every bar in the
      CSV file:

        >>> source_1 = CsvEventSource(handle=StringIO('''
        ... 2016-01-01T12:00:00,10,12,9,11,1000
        ... 2016-01-01T12:10:00,11,13,10,12,1001
        ... 2016-01-01T12:20:00,12,13,11,13,1002
        ... '''))
        >>> @source_1.on_bar
        ... def bar_handler_1(bar):
        ...     print(bar)
        >>> source_1.start()
        <Bar: o...10.0, h...12.0, l...9.0, c...11.0, v...1000, s...12:00...>
        <Bar: o...11.0, h...13.0, l...10.0, c...12.0, v...1001, s...12:10...>
        <Bar: o...12.0, h...13.0, l...11.0, c...13.0, v...1002, s...12:20...>

      Trading example:

        Successful buy:

          >>> source_trade = CsvEventSource(balance=1000, handle=StringIO('''
          ... 2016-01-01T12:00:00,10,,,20
          ... 2016-01-01T12:10:00,20,,,30
          ... 2016-01-01T12:10:00,30,,,40
          ... '''))

          Trade on the first bar, close on the last, print balance each new
          tick and bar:

            >>> @source_trade.on_bar
            ... def bar_handler_trade(bar):
            ...     if bar.close == 20:
            ...         source_trade.update_order(Order(
            ...             volume=2, signal=OrderSignal.buy,
            ...         ))
            ...     if bar.close == 40:
            ...         source_trade.update_order(Order())
            ...
            ...     print("Bar balance:", source_trade.balance)

            >>> @source_trade.on_tick
            ... def tick_trade_handler(tick):
            ...     print("Tick balance:", source_trade.balance)

          Trade decisions are made on the tick, or bar AFTER you place them:

            >>> source_trade.start()
            Bar balance: 1000.0
            Tick balance: 960.0
            Bar balance: 960.0
            Tick balance: 960.0
            Bar balance: 960.0
            Tick balance: 1040.0

        Successful sell:

          >>> source_trade = CsvEventSource(balance=1000, handle=StringIO('''
          ... 2016-01-01T12:00:00,40,,,30
          ... 2016-01-01T12:10:00,30,,,20
          ... 2016-01-01T12:10:00,20,,,10
          ... '''))

          Trade on the first bar, close on the last, print balance each new
          tick and bar:

            >>> @source_trade.on_bar
            ... def bar_handler_trade(bar):
            ...     if bar.close == 30:
            ...         source_trade.update_order(Order(
            ...             volume=2, signal=OrderSignal.sell,
            ...         ))
            ...     if bar.close == 10:
            ...         source_trade.update_order(Order())
            ...
            ...     print("Bar balance:", source_trade.balance)

            >>> @source_trade.on_tick
            ... def tick_trade_handler(tick):
            ...     print("Tick balance:", source_trade.balance)

            >>> source_trade.start()
            Bar balance: 1000.0
            Tick balance: 940.0
            Bar balance: 940.0
            Tick balance: 940.0
            Bar balance: 940.0
            Tick balance: 1040.0

        Unsuccessful buy:

          >>> source_trade = CsvEventSource(balance=1000, handle=StringIO('''
          ... 2016-01-01T12:00:00,40,,,30
          ... 2016-01-01T12:10:00,30,,,20
          ... 2016-01-01T12:10:00,20,,,10
          ... '''))

          Trade on the first bar, close on the last, print balance each new
          tick and bar:

            >>> @source_trade.on_bar
            ... def bar_handler_trade(bar):
            ...     if bar.close == 30:
            ...         source_trade.update_order(Order(
            ...             volume=2, signal=OrderSignal.buy,
            ...         ))
            ...     if bar.close == 10:
            ...         source_trade.update_order(Order())
            ...
            ...     print("Bar balance:", source_trade.balance)

            >>> @source_trade.on_tick
            ... def tick_trade_handler(tick):
            ...     print("Tick balance:", source_trade.balance)

            >>> source_trade.start()
            Bar balance: 1000.0
            Tick balance: 940.0
            Bar balance: 940.0
            Tick balance: 940.0
            Bar balance: 940.0
            Tick balance: 960.0

        Unsuccessful sell:

          >>> source_trade = CsvEventSource(balance=1000, handle=StringIO('''
          ... 2016-01-01T12:00:00,10,,,20
          ... 2016-01-01T12:10:00,20,,,30
          ... 2016-01-01T12:10:00,30,,,40
          ... '''))

          Trade on the first bar, close on the last, print balance each new
          tick and bar:

            >>> @source_trade.on_bar
            ... def bar_handler_trade(bar):
            ...     if bar.close == 20:
            ...         source_trade.update_order(Order(
            ...             volume=2, signal=OrderSignal.sell,
            ...         ))
            ...     if bar.close == 40:
            ...         source_trade.update_order(Order())
            ...
            ...     print("Bar balance:", source_trade.balance)

            >>> @source_trade.on_tick
            ... def tick_trade_handler(tick):
            ...     print("Tick balance:", source_trade.balance)

            >>> source_trade.start()
            Bar balance: 1000.0
            Tick balance: 960.0
            Bar balance: 960.0
            Tick balance: 960.0
            Bar balance: 960.0
            Tick balance: 960.0

        Switch signal:

          >>> source_trade = CsvEventSource(balance=1000, handle=StringIO('''
          ... 2016-01-01T12:00:00,10,,,20
          ... 2016-01-01T12:10:00,20,,,30
          ... 2016-01-01T12:10:00,30,,,40
          ... '''))

          Trade on the first bar, close on the last, print balance each new
          tick and bar:

            >>> @source_trade.on_bar
            ... def bar_handler_trade(bar):
            ...     if bar.close == 20:
            ...         source_trade.update_order(Order(
            ...             volume=2, signal=OrderSignal.sell,
            ...         ))
            ...     if bar.close == 30:
            ...         source_trade.update_order(Order(
            ...             volume=2, signal=OrderSignal.buy,
            ...         ))
            ...     if bar.close == 40:
            ...         source_trade.update_order(Order())
            ...
            ...     print("Bar balance:", source_trade.balance)

            >>> @source_trade.on_tick
            ... def tick_trade_handler(tick):
            ...     print("Tick balance:", source_trade.balance)

            >>> source_trade.start()
            Bar balance: 1000.0
            Tick balance: 960.0
            Bar balance: 960.0
            Tick balance: 920.0
            Bar balance: 920.0
            Tick balance: 1000.0

        For more info on how orders are fulfilled in ``CsvEventSource``, see
        ``CsvEventSource._fulfill_order`` docs.

      Can't place an order without balance:

        >>> source_bal = CsvEventSource(path='.', balance=9)
        >>> source_bal._add_tick(Tick(price=10))
        >>> source_bal.update_order(
        ...     Order(volume=1, signal=OrderSignal.buy)
        ... ).catch(lambda msg: print("Rejected:", msg))
        <mt_remote.promise.Promise...>
        >>> source_bal._add_tick(Tick(price=10))
        Rejected: Account balance too low

      Bar creation rules are applied:

        >>> source_2 = CsvEventSource(handle=StringIO('''
        ... 2016-01-01T12:00:00,10,9,12,11,1000
        ... '''))
        >>> @source_2.on_bar
        ... def bar_handler_2(bar):
        ...     print(bar)
        >>> source_2.start()
        Traceback (most recent call last):
        ...
        ValueError: High (9) is less than low (12)

      Exceptions:

        >>> CsvEventSource(path='', handle=StringIO(''))
        Traceback (most recent call last):
        ...
        ValueError: Must give only path, or handle

        >>> CsvEventSource()
        Traceback (most recent call last):
        ...
        ValueError: Must give either path, or handle

    """
    def __init__(self,
                 path=None,
                 handle=None,
                 balance=0,
                 cols=DEFAULT_CSV_COLS,
                 **reader_kwargs):

        super(CsvEventSource, self).__init__()

        if path is not None and handle is not None:
            raise ValueError("Must give only path, or handle")
        if path is None and handle is None:
            raise ValueError("Must give either path, or handle")

        self._path = path
        self._handle = handle
        self._reader_kwargs = reader_kwargs
        self._cols = cols

        self.on_tick(self.handle_tick)
        self.on_bar(self.handle_bar)
        self.on_balance(self.handle_balance)

        self._update_balance(balance)

    @property
    def path(self):
        """ Path to the CSV file being read """
        return self._path

    @property
    def balance(self):
        """ Internally tracked account balance """
        return self._balance

    __balance = None

    @property
    def _balance(self):
        """ Update the internal balance

        Examples:

          Setup:

            >>> source = CsvEventSource(path='', balance=10.0)

          >>> source._balance = 2000.0
          >>> source.balance
          2000.0

          >>> source._balance = 1000.0
          >>> source.balance
          1000.0

          >>> source._balance = 500
          >>> source.balance
          500.0

          >>> source._balance = '200'
          >>> source.balance
          200.0

          >>> source._balance = '100.0'
          >>> source.balance
          100.0

          Exceptions:

            >>> source._balance = 'test'
            Traceback (most recent call last):
            ...
            ValueError: could not convert string to float: 'test'
        """
        return self.__balance

    @_balance.setter
    def _balance(self, value):
        """ Set the internal balance value, ensuring float """
        self.__balance = float(value)

    @property
    def balance_total(self):
        """ Total account value including both balance, and open trades

        Examples:

          >>> from .order import Order

          Balance total is the same as balance if no trades in place:

            >>> source = CsvEventSource(path='', balance=1000)
            >>> source.balance_total
            1000.0

          Total doesn't change just because of a tick:

            >>> source._add_tick(Tick(price=10.0))
            >>> source.balance_total
            1000.0

          Total doesn't change just because of a bar:

            >>> source._add_bar(Bar(close=20.0))
            >>> source.balance_total
            1000.0

          Placing a buy order updates balance, but total remains the same:

            >>> source.update_order(Order(signal=OrderSignal.buy, volume=3))
            <mt_remote.promise.Promise...>
            >>> source._add_bar(Bar(close=20.0))
            >>> source.balance
            940.0
            >>> source.balance_total
            1000.0

          If the trade goes well, total increases (balance remains fixed):

            >>> source._add_bar(Bar(close=30.0))
            >>> source.balance
            940.0
            >>> source.balance_total
            1030.0

          If the trade goes badly, total decreases (balance remains fixed):

            >>> source._add_bar(Bar(close=10.0))
            >>> source.balance
            940.0
            >>> source.balance_total
            970.0

          Placing a sell order updates balance, but total remains the same:

            >>> source = CsvEventSource(path='', balance=1000)
            >>> source.update_order(Order(signal=OrderSignal.sell, volume=3))
            <mt_remote.promise.Promise...>
            >>> source._add_bar(Bar(close=20.0))
            >>> source.balance
            940.0
            >>> source.balance_total
            1000.0

          If the trade goes well, total increases (balance remains fixed):

            >>> source._add_bar(Bar(close=10.0))
            >>> source.balance
            940.0
            >>> source.balance_total
            1030.0

          If the trade goes badly, total decreases (balance remains fixed):

            >>> source._add_bar(Bar(close=30.0))
            >>> source.balance
            940.0
            >>> source.balance_total
            970.0

        """
        if self._curr_order is None:
            return self.balance

        return self.balance + self._curr_order.volume * order_single(
            self._curr_order.signal,
            self._curr_order_price,
            self._price,
        )

    def start(self):
        """ Open and read the CSV file, sending events for each row """
        if self._handle is not None:
            return self._start_read(self._handle)

        with open(self.path, 'r') as handle:
            return self._start_read(handle)

    def _start_read(self, handle):
        """ Read, and parse CSV file from the given handle, triggering events
        for each line as needed

        :param handle: File-like handle object to read from
        """
        reader = csv.reader(handle, **self._reader_kwargs)
        for row in reader:
            if len(row) == 0:
                continue
            self.handle_row(row)

    def handle_row(self, row):
        """ Handle a row in the CSV file

        Examples:

          Each row gives a bar, and a tick

            >>> source = CsvEventSource(path='')
            >>> @source.on_tick
            ... def handle_tick(tick):
            ...     print("Tick:", tick)
            >>> @source.on_bar
            ... def handle_bar(bar):
            ...     print("Bar:", bar)
            >>> source.handle_row((None, 20))
            Bar: <Bar: open=20.0>
            Tick: <Tick: price=20.0>
        """
        bar = Bar(**dict(zip(self._cols, row)))
        tick = Tick(price=bar.open if bar.close is None else bar.close)
        self._add_bar(bar)
        self._add_tick(tick)

    _price = None

    def handle_tick(self, tick):
        """ Set the current price to the tick price, and fulfill the order
        queue at that price

        Examples:

          Setup:

            >>> source = CsvEventSource(path='')

          >>> source.handle_tick(Tick(price=55))
          >>> source._price
          55.0
        """
        self._price = tick.price
        self._fulfill_order()

    def handle_bar(self, bar):
        """ Set the current price to the latest available price on the bar,
        and fulfill the order queue at that price

        Examples:

          Setup:

            >>> source = CsvEventSource(path='')

          >>> source.handle_bar(Bar(open_=20))
          >>> source._price
          20.0

          >>> source.handle_bar(Bar(close=30))
          >>> source._price
          30.0

          >>> source.handle_bar(Bar(open_=40, close=50))
          >>> source._price
          50.0
        """
        self._price = bar.close if bar.close is not None else bar.open
        self._fulfill_order()

    def handle_balance(self, balance):
        """ Update the internal balance

        Examples:

          Setup:

            >>> source = CsvEventSource(path='', balance=10.0)

          >>> source.handle_balance(500)
          >>> source.balance
          500.0

          >>> source.handle_balance('100.0')
          >>> source.balance
          100.0

          Exceptions:

            >>> source.handle_balance('test')
            Traceback (most recent call last):
            ...
            ValueError: could not convert string to float: 'test'
        """
        self._balance = balance

    _curr_order = None
    _curr_order_price = None

    def _fulfill_order(self):
        """ Update the internal order ledger, and balance

        Examples:

          Setup:

            >>> from .order import Order

          Order takes ``volume * price`` from balance:

            >>> source = CsvEventSource(balance=1000, path='')
            >>> source._price = 10.0
            >>> source.update_order(Order(OrderSignal.buy, volume=3))
            <mt_remote.promise.Promise...>
            >>> source._fulfill_order()
            >>> source.balance
            970.0

          Closing a positive buy order calculates new balance correctly:

            >>> source._price = 20.0
            >>> source.update_order(Order())
            <mt_remote.promise.Promise...>
            >>> source._fulfill_order()
            >>> source.balance
            1030.0

          Order takes ``volume * price`` from balance:

            >>> source = CsvEventSource(balance=1000, path='')
            >>> source._price = 20.0
            >>> source.update_order(Order(OrderSignal.sell, volume=3))
            <mt_remote.promise.Promise...>
            >>> source._fulfill_order()
            >>> source.balance
            940.0

          Closing a positive sell order calculates new balance correctly:

            >>> source._price = 10.0
            >>> source.update_order(Order())
            <mt_remote.promise.Promise...>
            >>> source._fulfill_order()
            >>> source.balance
            1030.0

          Buy orders that lose also work:

            >>> source = CsvEventSource(balance=1000, path='')
            >>> source._price = 20.0
            >>> source.update_order(Order(OrderSignal.buy, volume=3))
            <mt_remote.promise.Promise...>
            >>> source._fulfill_order()
            >>> source._price = 10.0
            >>> source.update_order(Order())
            <mt_remote.promise.Promise...>
            >>> source._fulfill_order()
            >>> source.balance
            970.0

          Sell orders that lose also work:

            >>> source = CsvEventSource(balance=1000, path='')
            >>> source._price = 10.0
            >>> source.update_order(Order(OrderSignal.sell, volume=3))
            <mt_remote.promise.Promise...>
            >>> source._fulfill_order()
            >>> source._price = 20.0
            >>> source.update_order(Order())
            <mt_remote.promise.Promise...>
            >>> source._fulfill_order()
            >>> source.balance
            970.0

          Doesn't fail if there's no order:

            >>> source = CsvEventSource(balance=1000, path='')
            >>> source._fulfill_order()

          Rejects if no balance:

            >>> source = CsvEventSource(balance=10, path='')
            >>> source._price = 20.0
            >>> source.update_order(
            ...     Order(OrderSignal.buy, volume=3)
            ... ).catch(lambda msg: print("Rejected:", msg))
            <mt_remote.promise.Promise...>
            >>> source._fulfill_order()
            Rejected: Account balance too low

        """
        if self.order is None:
            return

        if self.order.signal == OrderSignal.out:
            self._fulfill_order_out()
        else:
            self._fulfill_order_in()

    def _fulfill_order_out(self, clear_order=True):
        """ Fulfill an order for out """
        if self._curr_order is None:
            self.order_promise.reject("No open order")
            return

        balance_total = self.balance_total

        if clear_order:
            self._curr_order = None
            self._curr_order_price = None

        # TODO Wait for next signal to update balance
        self._update_balance(balance_total)

    def _fulfill_order_in(self):
        """ Fulfill an order for buy/sell """
        if (
            self._curr_order is not None and
            self.order.signal != self._curr_order.signal
        ):
            self._fulfill_order_out(clear_order=False)

        order_total = self._price * self.order.volume
        if order_total > self.balance:
            self.order_promise.reject("Account balance too low")
            return

        self._curr_order = self.order
        self._curr_order_price = self._price

        self._update_balance(self.balance - order_total)

        self.order_promise.accept()


def order_single(signal, in_price, out_price):
    """ Get the amount from getting out of an order

    :param OrderSignal signal: Trade signal type
    :param float in_price: Price on order create
    :param float out_price: Price on order close

    Examples:

      >>> order_single(OrderSignal.buy, 50.0, 60.0)
      60.0

      >>> order_single(OrderSignal.buy, 60.0, 50.0)
      50.0

      >>> order_single(OrderSignal.sell, 60.0, 50.0)
      70.0

      >>> order_single(OrderSignal.sell, 50.0, 60.0)
      40.0

      >>> order_single(OrderSignal.sell, 20.0, 40.0)
      0.0
    """
    return in_price + order_gain(signal, in_price, out_price)


def order_gain(signal, in_price, out_price):
    """ Get the amount gained from an order

    :param OrderSignal signal: Trade signal type
    :param float in_price: Price on order create
    :param float out_price: Price on order close

    Examples:

      >>> order_gain(OrderSignal.buy, 50.0, 60.0)
      10.0

      >>> order_gain(OrderSignal.buy, 60.0, 50.0)
      -10.0

      >>> order_gain(OrderSignal.sell, 50.0, 60.0)
      -10.0

      >>> order_gain(OrderSignal.sell, 60.0, 50.0)
      10.0

      Exceptions:

        >>> order_gain(OrderSignal.out, 20, 10)
        Traceback (most recent call last):
        ...
        AssertionError: Can't handle order type 'OrderSignal.out'

        >>> order_gain(None, 20, 10)
        Traceback (most recent call last):
        ...
        AssertionError: Can't handle order type 'None'
    """
    assert signal in (OrderSignal.buy, OrderSignal.sell), (
        "Can't handle order type '%s'" % signal
    )
    if signal == OrderSignal.buy:
        return out_price - in_price
    else:
        return in_price - out_price

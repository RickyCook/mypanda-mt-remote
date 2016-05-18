""" Classes and functions dealing trade data in the form of ticks """
from .util import repr_str, ts_setter


class Tick(object):
    """ Instrument tick, with price at a point in time """
    def __init__(self, tick_ts=None, price=None):
        """
        :param tick_ts: Time that the tick occurred at, formatted in ISO8601
        :type tick_ts: datetime.datetime, str

        :param price: Price of the instrument when the tick occurred
        :type price: float, str

        :raises ValueError: If price can't be parsed as numbers

        Examples:

          >>> Tick(price=15)
          <Tick: price=15.0>
          >>> Tick(price='1')
          <Tick: price=1.0>
          >>> Tick(price='12')
          <Tick: price=12.0>

          >>> Tick(price='test')
          Traceback (most recent call last):
          ...
          ValueError: could not convert string to float: 'test'

          >>> Tick(tick_ts='2016-01-01').tick_ts
          datetime.datetime(2016, 1, 1, 0, 0, tzinfo=<iso8601.Utc>)
        """
        self.price = None if price is None else float(price)
        self.tick_ts = None if tick_ts is None else tick_ts

    def __repr__(self):
        """
        Examples:

          All simple values:

            >>> Tick(price=10)
            <Tick: price=10.0>

          Python stringify:

            >>> str(Tick(price=10))
            '<Tick: price=10.0>'

          Tick time formatting:

            >>> Tick(tick_ts='2016-01-01', price=20)
            <Tick: price=20.0, tick_ts=2016-01-01T00:00:00+00:00>
        """
        def updater(props):
            """ Updater for ``repr_str`` to add ``tick_ts`` """
            if self.tick_ts is not None:
                props.append(('tick_ts', self.tick_ts.isoformat()))

            return props

        return repr_str(
            self,
            ('price',),
            updater,
        )

    _start_ts = None

    @property
    def tick_ts(self):
        """ Time that the tick occurred at

        :param value: Pre-parsed, or ISO8601 string date
        :type value: None, datetime.datetime, str

        :raises iso8601.iso8601.ParseError: If unparseable date string

        Examples:

          >>> Tick(tick_ts='2016-01-01 12:22:22').tick_ts
          datetime.datetime(2016, 1, 1, 12, 22, 22, tzinfo=<iso8601.Utc>)
        """
        return self._start_ts

    @tick_ts.setter
    @ts_setter
    def tick_ts(self, value):
        """ Setter for ``tick_ts`` that parses ISO8601 automatically """
        self._start_ts = value

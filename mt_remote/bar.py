""" Classes and functions dealing trade data in the form of O/H/L/C/V bars """
import re

from enum import Enum

from .util import parse_int, repr_str, ts_setter


PERIOD_SPLIT_RE = re.compile(r'([0-9]+)(.*)')


class BarPeriod(Enum):
    """ Units for a ``Bar`` period """
    seconds = 'seconds'
    minutes = 'minutes'
    hours = 'hours'
    days = 'days'
    weeks = 'weeks'
    months = 'months'
    years = 'years'


class Bar(object):
    """ Instrument bar with O/H/L/C/V, period, and start time """

    def __init__(
        self,
        start_ts=None,
        period=None,
        open_=None,
        high=None,
        low=None,
        close=None,
        volume=None,
    ):
        """
        :param start_ts: Time that the bar started at, formatted in ISO8601
        :type start_ts: datetime.datetime, str

        :param period: Period of the bar (eg '1m', '4h')
        :type period: str, tuple

        :param open_: Price of the instrument at bar open
        :type open_: float, str
        :param high: Maximum price of the instrument over the bar
        :type high: float, str
        :param low: Minimum price of the instrument over the bar
        :type low: float, str
        :param close: Price of the instrument at bar close
        :type close: float, str
        :param volume: Trade volume of the instrument over the bar
        :type volume: int, str

        :raises ValueError: If ``high`` is less than ``low``
        :raises ValueError: If O/H/L/C/V can't be parsed as numbers

        Examples:

          >>> Bar(high=1)
          <Bar: high=1.0>
          >>> Bar(low=1)
          <Bar: low=1.0>

          >>> Bar(high='1')
          <Bar: high=1.0>
          >>> Bar(low='1')
          <Bar: low=1.0>
          >>> Bar(open_='12')
          <Bar: open=12.0>

          Start timestamp is parsed in format from MetaTrader CSV:

            >>> Bar(start_ts='2016-01-01').start_ts
            datetime.datetime(2016, 1, 1, 0, 0, tzinfo=<iso8601.Utc>)

            >>> Bar(start_ts='2016-01-02 03:04:05').start_ts
            datetime.datetime(2016, 1, 2, 3, 4, 5, tzinfo=<iso8601.Utc>)

          Start timestamp parsed in format from MetaTrader Time[] array

            >>> Bar(start_ts='2016.01.02 03:04:05').start_ts
            datetime.datetime(2016, 1, 2, 3, 4, 5, tzinfo=<iso8601.Utc>)

          Blanks are considered None:

            >>> str(Bar(open_='').open)
            'None'
            >>> str(Bar(high='').high)
            'None'
            >>> str(Bar(low='').low)
            'None'
            >>> str(Bar(close='').close)
            'None'
            >>> str(Bar(volume='').volume)
            'None'
            >>> str(Bar(start_ts='').start_ts)
            'None'
            >>> str(Bar(period='').period)
            'None'

          Exceptions:

            High and low are checked for sanity:

              >>> Bar(high=5, low=10)
              Traceback (most recent call last):
              ...
              ValueError: High (5) is less than low (10)

              >>> Bar(high='5', low='10')
              Traceback (most recent call last):
              ...
              ValueError: High (5) is less than low (10)

            Errors occur when OHLCV aren't numbers:

              >>> Bar(open_='test')
              Traceback (most recent call last):
              ...
              ValueError: could not convert string to float: 'test'
        """

        self.open = None if open_ is None or open_ is '' else float(open_)
        self.high = None if high is None or high is '' else float(high)
        self.low = None if low is None or low is '' else float(low)
        self.close = None if close is None or close is '' else float(close)
        self.volume = None if volume is None or volume is '' else int(volume)

        if (
            self.high is not None and
            self.low is not None and
            self.high < self.low
        ):
            raise ValueError("High (%s) is less than low (%s)" % (
                high, low,
            ))

        self.period = None if period is '' else period
        self.start_ts = None if start_ts is '' else start_ts

    def __repr__(self):
        """
        Examples:

          All simple values:

            >>> Bar(open_=10)
            <Bar: open=10.0>
            >>> Bar(high=10)
            <Bar: high=10.0>
            >>> Bar(low=10)
            <Bar: low=10.0>
            >>> Bar(close=10)
            <Bar: close=10.0>
            >>> Bar(volume=10)
            <Bar: volume=10>

          Multiple simple values:

            >>> Bar(open_=10, close=20, volume=1000)
            <Bar: open=10.0, close=20.0, volume=1000>

          Python stringify:

            >>> str(Bar(open_=10, close=20, volume=1000))
            '<Bar: open=10.0, close=20.0, volume=1000>'

          Period formatting:

            >>> Bar(period='5m', volume=2000)
            <Bar: volume=2000, period=5 minutes>

          Start time formatting:

            >>> Bar(start_ts='2016-01-01', volume=3000)
            <Bar: volume=3000, start_ts=2016-01-01T00:00:00+00:00>
        """
        def updater(props):
            """ Updater for ``repr_str`` to add ``period`` text, and
            ``start_ts``
            """
            if self.period is not None:
                props.append(('period', '%d %s' % (
                    self.period[0],
                    self.period[1].value,
                )))
            if self.start_ts is not None:
                props.append(('start_ts', self.start_ts.isoformat()))

            return props

        return repr_str(
            self,
            ('open', 'high', 'low', 'close', 'volume'),
            updater,
        )

    @property
    def oh_delta(self):
        """ Delta (absolute change) between the open and the close

        Examples:

          >>> Bar(open_=5, close=10).oh_delta
          5.0
          >>> Bar(open_=10, close=5).oh_delta
          5.0
        """
        return abs(self.oh_change)

    @property
    def oh_change(self):
        """ Change between the open and the close

        Examples:

          >>> Bar(open_=5, close=10).oh_change
          5.0
          >>> Bar(open_=10, close=5).oh_change
          -5.0
        """
        return self.close - self.open

    @property
    def size(self):
        """ Difference between the high, and the low

        Examples:

          >>> Bar(high=10, low=7).size
          3.0
        """
        return self.high - self.low

    _period = None

    @property
    def period(self):
        """ Time period of this ``Bar``

        :return tuple: of the parsed duration value, and the ``BarPeriod``
                       representing what the unit of the value is
        :return None: if period is unset, or ``None``

        :raise ValueError: Period string is unparseable
        :raise TypeError: Unknown value type

        Examples:

          Seconds:

            >>> Bar(period='1s').period
            (1, <BarPeriod.seconds...>)
            >>> Bar(period='30 seconds').period
            (30, <BarPeriod.seconds...>)
            >>> Bar(period='15sec').period
            (15, <BarPeriod.seconds...>)

          Minutes:

            >>> Bar(period='30m').period
            (30, <BarPeriod.minutes...>)
            >>> Bar(period='30minutes').period
            (30, <BarPeriod.minutes...>)
            >>> Bar(period='  15      minutes   ').period
            (15, <BarPeriod.minutes...>)
            >>> Bar(period='15MINutes').period
            (15, <BarPeriod.minutes...>)

          Hours:

            >>> Bar(period='4hours').period
            (4, <BarPeriod.hours...>)
            >>> Bar(period='4h').period
            (4, <BarPeriod.hours...>)
            >>> Bar(period='4hrs').period
            (4, <BarPeriod.hours...>)
            >>> Bar(period='4hr').period
            (4, <BarPeriod.hours...>)

          Days:

            >>> Bar(period='7day').period
            (7, <BarPeriod.days...>)
            >>> Bar(period='7days').period
            (7, <BarPeriod.days...>)

          Weeks:

            >>> Bar(period='4w').period
            (4, <BarPeriod.weeks...>)
            >>> Bar(period='4week').period
            (4, <BarPeriod.weeks...>)
            >>> Bar(period='4weeks').period
            (4, <BarPeriod.weeks...>)
            >>> Bar(period='4wks').period
            (4, <BarPeriod.weeks...>)

          Months:

            >>> Bar(period='2months').period
            (2, <BarPeriod.months...>)
            >>> Bar(period='2mn').period
            (2, <BarPeriod.months...>)
            >>> Bar(period='2mns').period
            (2, <BarPeriod.months...>)
            >>> Bar(period='2mnth').period
            (2, <BarPeriod.months...>)
            >>> Bar(period='2mnths').period
            (2, <BarPeriod.months...>)

          Years:

            >>> Bar(period='5years').period
            (5, <BarPeriod.years...>)
            >>> Bar(period='5yrs').period
            (5, <BarPeriod.years...>)
            >>> Bar(period='5yr').period
            (5, <BarPeriod.years...>)
            >>> Bar(period='5y').period
            (5, <BarPeriod.years...>)

          Pre-parsed:

            >>> Bar(period=(1, BarPeriod.seconds)).period
            (1, <BarPeriod.seconds...>)
            >>> Bar(period=[1, BarPeriod.seconds]).period
            (1, <BarPeriod.seconds...>)

          Incorrect pre-parsed length:

            >>> Bar(period=(1, BarPeriod.seconds, 2)).period
            Traceback (most recent call last):
            ...
            ValueError: Must have exactly 2 elements in period

          Pre-parsed non-base-10 string:

            >>> Bar(period=('0xff', BarPeriod.seconds)).period
            Traceback (most recent call last):
            ...
            ValueError: invalid literal for int() with base 10: '0xff'

          Incorrect type for pre-parsed unit:

            >>> Bar(period=(1, 'second')).period
            Traceback (most recent call last):
            ...
            TypeError: Second period tuple element must be a BarPeriod value

          Unparsable values:

            >>> Bar(period='fake')
            Traceback (most recent call last):
            ...
            ValueError: Couldn't parse period 'fake'

            >>> Bar(period='1fake')
            Traceback (most recent call last):
            ...
            ValueError: Unknown time unit 'fake'

            >>> Bar(period=1)
            Traceback (most recent call last):
            ...
            TypeError: Unknown period value type 'int'
        """
        return self._period

    @period.setter
    def period(self, new_value):  # pylint:disable=too-many-branches
        """ Set, and parse the string ``Bar`` period """

        if new_value is None:
            self._period = None

        elif isinstance(new_value, str):
            match = PERIOD_SPLIT_RE.search(new_value)
            if not match:
                raise ValueError(
                    "Couldn't parse period '%s'" % new_value,
                )

            value, unit = match.groups()
            value = parse_int(value)
            unit = unit.lower().strip()

            if 'seconds'.startswith(unit):
                unit = BarPeriod.seconds
            elif 'minutes'.startswith(unit):
                unit = BarPeriod.minutes
            elif 'hours'.startswith(unit) or 'hrs'.startswith(unit):
                unit = BarPeriod.hours
            elif 'days'.startswith(unit):
                unit = BarPeriod.days
            elif 'weeks'.startswith(unit) or 'wks'.startswith(unit):
                unit = BarPeriod.weeks
            elif (
                'months'.startswith(unit) or
                'mnths'.startswith(unit) or
                'mns'.startswith(unit)
            ):
                unit = BarPeriod.months
            elif 'years'.startswith(unit) or 'yrs'.startswith(unit):
                unit = BarPeriod.years
            else:
                raise ValueError("Unknown time unit '%s'" % unit)

            self._period = (value, unit)

        elif isinstance(new_value, (tuple, list)):
            if len(new_value) != 2:
                raise ValueError("Must have exactly 2 elements in period")

            value, unit = new_value

            if not isinstance(unit, BarPeriod):
                raise TypeError(
                    "Second period tuple element must be a BarPeriod value"
                )

            self._period = (parse_int(value), unit)

        else:
            raise TypeError(
                "Unknown period value type '%s'" % (
                    new_value.__class__.__name__,
                )
            )

    _start_ts = None

    @property
    def start_ts(self):
        """ Time that the bar started at

        :param value: Pre-parsed, or ISO8601 string date
        :type value: None, datetime.datetime, str

        :raises iso8601.iso8601.ParseError: If unparseable date string

        Examples:

          >>> Bar(start_ts='2016-01-01 12:22:22').start_ts
          datetime.datetime(2016, 1, 1, 12, 22, 22, tzinfo=<iso8601.Utc>)
        """
        return self._start_ts

    @start_ts.setter
    @ts_setter
    def start_ts(self, value):
        """ Setter for ``start_ts`` that parses ISO8601 automatically """
        self._start_ts = value

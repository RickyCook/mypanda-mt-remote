""" Utils for MT Remote """
import datetime
import re

from functools import wraps

import iso8601


def repr_str(obj, attrs, update=None):
    """ Generic attr to string mappings for repr functions

    Examples:

      Setup:

        >>> class ReprTest(object):
        ...     pass

      Simple values:

        >>> obj = ReprTest()
        >>> obj.test_a = 10
        >>> obj.test_b = None
        >>> obj.test_c = 'test'
        >>> repr_str(obj, ('test_a', 'test_b', 'test_c'))
        '<ReprTest: test_a=10, test_c=test>'

      Custom updater:

        >>> obj = ReprTest()
        >>> obj.test_a = 10
        >>> obj.test_b = 'test'
        >>> repr_str(
        ...     obj,
        ...     ('test_a', 'test_b'),
        ...     lambda attrs: attrs + [('extra', 'val')]
        ... )
        '<ReprTest: test_a=10, test_b=test, extra=val>'
    """
    props = [
        (attr, value)
        for attr, value in (
            (attr, getattr(obj, attr))
            for attr in attrs
        )
        if value is not None
    ]

    if update is not None:
        props = update(props)

    props_str = ', '.join('%s=%s' % (attr, value) for attr, value in props)
    return "<{klass}: {props_str}>".format(
        klass=obj.__class__.__name__,
        props_str=props_str,
    )


TS_SETTER_NUM_RE = r'(?P<{name}>[0-9]+)'
TS_SETTER_TRANSFORM_RE = re.compile(
    r'^{year}{sep}{month}{sep}{day}'.format(
        sep=r'[./]',
        year=TS_SETTER_NUM_RE.format(name='Y'),
        month=TS_SETTER_NUM_RE.format(name='M'),
        day=TS_SETTER_NUM_RE.format(name='D'),
    )
)
TS_SETTER_TRANSFORM_REPL = r'\g<Y>-\g<M>-\g<D>'


def ts_setter(func):
    """ Decorator for setters that parses ISO8601 (and ISO8601-like)
    automatically

    :param value: Pre-parsed, or ISO8601 string date
    :type value: None, datetime.datetime, str

    :raises iso8601.iso8601.ParseError: If unparseable date string

    Examples:

      >>> @ts_setter
      ... def mysetter(self, value):
      ...     print('V:', value)
      >>> self_ = None

      >>> mysetter(self_, '2016-01-01T12:22:22')
      V: 2016-01-01 12:22:22+00:00

      >>> mysetter(self_, '2016.01.02 03:04:05')
      V: 2016-01-02 03:04:05+00:00

      >>> mysetter(self_, None)
      V: None

      >>> mysetter(self_, datetime.datetime(2016, 1, 1, 12, 22, 22))
      V: 2016-01-01 12:22:22

      >>> mysetter(self_, 'test')
      Traceback (most recent call last):
      ...
      iso8601.iso8601.ParseError: Unable to parse date string 'test'
    """

    @wraps(func)
    def inner(self, value):
        """ Parse input value as ISO8601 date """
        if value is None:
            return func(self, None)
        elif isinstance(value, datetime.datetime):
            return func(self, value)
        else:
            value = TS_SETTER_TRANSFORM_RE.sub(TS_SETTER_TRANSFORM_REPL, value)
            return func(self, iso8601.parse_date(value))

    return inner


def parse_int(value):
    """ Force base 10 on ``str`` to ``int`` parsing

    Examples:

      >>> parse_int('200')
      200

      >>> parse_int(200.5)
      200

      >>> parse_int('0xff')
      Traceback (most recent call last):
      ...
      ValueError: invalid literal for int() with base 10: '0xff'
    """
    if isinstance(value, (int, float)):
        return int(value)
    else:
        return int(value, base=10)

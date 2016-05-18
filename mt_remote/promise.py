""" Rough imlementation of promise pattern for async actions """


class Promise(object):
    """ Roughly mimick the promise pattern for async actions """

    def __init__(self):
        self._then_handlers = []
        self._catch_handlers = []
        self._always_handlers = []

    _done_success = None
    _done_args = None
    _done_kwargs = None

    def then(self, func):
        """ Add success handler

        Examples:

          >>> prom = Promise().then(
          ...     lambda v: print('1', v)
          ... ).then(
          ...     lambda v: print('2', v)
          ... )
          >>> prom.accept('test')
          1 test
          2 test

          >>> prom.then(lambda v: print('3', v))
          3 test
          ...

          >>> prom = Promise().then(lambda v: print('1', v))
          >>> prom.reject('nothing')
        """
        self._then_handlers.append(func)
        if self._done_success is True:
            func(*self._done_args, **self._done_kwargs)
        return self

    def catch(self, func):
        """ Add failure handler

        Examples:

          >>> prom = Promise().catch(
          ...     lambda v: print('1', v)
          ... ).catch(
          ...     lambda v: print('2', v)
          ... )
          >>> prom.reject('test')
          1 test
          2 test

          >>> prom.catch(lambda v: print('3', v))
          3 test
          ...

          >>> prom = Promise().catch(lambda v: print('1', v))
          >>> prom.accept('nothing')
        """
        self._catch_handlers.append(func)
        if self._done_success is False:
            func(*self._done_args, **self._done_kwargs)
        return self

    def always(self, func):
        """ Add success handler

        Examples:

          >>> prom = Promise().always(
          ...     lambda v: print('1', v)
          ... ).always(
          ...     lambda v: print('2', v)
          ... ).then(
          ...     lambda v: print('then', v)
          ... )
          >>> prom.accept('test')
          then test
          1 test
          2 test

          >>> prom.always(lambda v: print('3', v))
          3 test
          ...

          >>> prom = Promise().always(
          ...     lambda v: print('1', v)
          ... ).always(
          ...     lambda v: print('2', v)
          ... ).catch(
          ...     lambda v: print('catch', v)
          ... )
          >>> prom.reject('test')
          catch test
          1 test
          2 test

          >>> prom.always(lambda v: print('3', v))
          3 test
          ...
        """
        self._always_handlers.append(func)
        if self._done_success is not None:
            func(*self._done_args, **self._done_kwargs)
        return self

    def accept(self, *args, **kwargs):
        """ Successfully complete

        :raises AssertionError: if already completed

        Examples:

          >>> prom = Promise()
          >>> prom.accept()
          >>> prom.accept()
          Traceback (most recent call last):
          ...
          AssertionError: Can't complete multiple times

          >>> prom = Promise()
          >>> prom.reject()
          >>> prom.accept()
          Traceback (most recent call last):
          ...
          AssertionError: Can't complete multiple times
        """
        assert self._done_success is None, "Can't complete multiple times"

        self._done_success = True
        self._done_args = args
        self._done_kwargs = kwargs

        for func in self._then_handlers + self._always_handlers:
            func(*args, **kwargs)

    def reject(self, *args, **kwargs):
        """ Error trying to complete

        :raises AssertionError: if already completed

        Examples:

          >>> prom = Promise()
          >>> prom.reject()
          >>> prom.reject()
          Traceback (most recent call last):
          ...
          AssertionError: Can't complete multiple times

          >>> prom = Promise()
          >>> prom.accept()
          >>> prom.reject()
          Traceback (most recent call last):
          ...
          AssertionError: Can't complete multiple times
        """
        assert self._done_success is None, "Can't complete multiple times"

        self._done_success = False
        self._done_args = args
        self._done_kwargs = kwargs

        for func in self._catch_handlers + self._always_handlers:
            func(*args, **kwargs)

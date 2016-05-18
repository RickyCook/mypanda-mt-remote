""" Custom exceptions from MT Remote """


class OrderQueueError(Exception):
    """ Raised in case there's an error adding an order to the queue """
    pass

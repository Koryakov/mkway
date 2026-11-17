"""Helper of card MW-098: the two calls the hermetic guard refuses, one function each, so that a test names no socket or sleep
itself. Each function only makes the call; the guard raises before anything runs."""
import socket
import time


def open_socket():
    return socket.socket()


def sleep_zero():
    time.sleep(0)

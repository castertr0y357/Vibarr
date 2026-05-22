import logging
import sys

class SafeFileHandler(logging.FileHandler):
    def __init__(self, filename, mode='a', encoding=None, delay=False, errors=None):
        self.fallback = False
        try:
            super().__init__(filename, mode, encoding, delay, errors)
        except (PermissionError, OSError):
            self.fallback = True
            logging.StreamHandler.__init__(self, sys.stdout)

    def _open(self):
        if getattr(self, 'fallback', False):
            return sys.stdout
        try:
            return super()._open()
        except (PermissionError, OSError):
            self.fallback = True
            return sys.stdout

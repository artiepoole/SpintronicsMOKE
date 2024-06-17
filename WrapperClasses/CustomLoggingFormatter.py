from PyQt5 import QtGui, QtWidgets
import logging

ATTENTION_LEVEL = 25
logging.addLevelName(ATTENTION_LEVEL, "ATTENTION")
logging.ATTENTION = ATTENTION_LEVEL


class CustomLoggingFormatter(logging.Formatter):
    """
    A logging formatter which outputs HTML messages which include colour infromation for use with HTMLBasedColorLogger
    """
    FORMATS = {
        logging.ERROR: ("[%(levelname)s] %(module)s [%(filename)s:%(lineno)d] - %(message)s", QtGui.QColor("red")),
        logging.DEBUG: ("[%(levelname)s] [%(filename)s:%(lineno)d] - %(message)s", QtGui.QColor("green")),
        logging.INFO: ("[%(levelname)s] %(module)s - %(message)s", QtGui.QColor("black")),
        logging.WARNING: (
            '[%(levelname)s] %(asctime)s %(name)s %(levelname)s - %(message)s',
            QtGui.QColor("orange")
        ),
        logging.ATTENTION: ('[%(levelname)s] %(message)s', QtGui.QColor("darkGreen"))
    }

    def format(self, record):
        last_fmt = self._style._fmt
        opt = CustomLoggingFormatter.FORMATS.get(record.levelno)
        if opt:
            fmt, color = opt
            self._style._fmt = "<font color=\"{}\">{}</font>".format(QtGui.QColor(color).name(), fmt)
        res = logging.Formatter.format(self, record)
        self._style._fmt = last_fmt
        return res


class HTMLBasedColorLogger(logging.Handler):
    """
    A logging handler which expands PyQt to enable a textedit to act as a log box, but which also handles colour using
    html
    """
    def __init__(self, parent=None):
        super().__init__()
        self.widget = QtWidgets.QPlainTextEdit(parent)
        self.widget.setReadOnly(True)

    def emit(self, record):
        msg = self.format(record)
        self.widget.appendHtml(msg)
        # move scrollbar
        scrollbar = self.widget.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

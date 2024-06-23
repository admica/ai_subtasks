# highlighter.py

from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor
from PyQt5.QtCore import QRegExp

class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super(PythonHighlighter, self).__init__(parent)

        keywordFormat = QTextCharFormat()
        keywordFormat.setForeground(QColor("blue"))
        keywordPatterns = ["and", "as", "assert", "break", "class", "continue", "def",
                   "del", "elif", "else", "except", "False", "finally", "for", "from",
                   "global", "if", "import", "in", "is", "lambda", "None", "nonlocal",
                   "not", "or", "pass", "raise", "return", "True", "try", "while",
                   "with", "yield"]

        self.highlightingRules = [(QRegExp(pattern), keywordFormat)
                                  for pattern in keywordPatterns]

    def highlightBlock(self, text):
        for pattern, format in self.highlightingRules:
            expression = QRegExp(pattern)
            index = expression.indexIn(text)
            while index >= 0:
                length = expression.matchedLength()
                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length)

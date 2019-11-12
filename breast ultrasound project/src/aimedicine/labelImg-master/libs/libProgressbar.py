try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except ImportError:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *


class libProgressbar(QWidget):
    finished_notify = pyqtSignal(bool)

    def set_limit_object(self, limit_object):
        self.limit_object = limit_object

    def __init__(self, parent=None):

        super(QWidget, self).__init__(parent)
        self.setWindowFlags(self.windowFlags()| Qt.Dialog )
        self.setFixedSize(270, 45)

        self.limit_object = None

        #self.location_on_the_screen()
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, False)
        self.setWindowFlag(Qt.WindowMinimizeButtonHint, False)

        self.parent = parent
        self.pbar = QProgressBar(self)
        self.pbar.setGeometry(20, 10, 240, 25)

        self.status = QLabel(self)
        self.status.setText("Load AI Model")
        self.status.setGeometry(20, 10, 240, 25)
        self.status.setAlignment(Qt.AlignCenter)

        self.timer = QBasicTimer()

        self.setGeometry(self.parent.width() / 2 + self.width() / 2, 100 , 280, 170)

        #self.setGeometry(self.parent.width()/2+ self.width()/2, self.parent.height()/2 + self.height()/2, 280, 170)
        self.setWindowTitle('AI Analyzing')
        #self.show()

    def showProgressbar(self):
        self.step = 0
        self.timer.start(30, self)
        self.setVisible(True)

    def timerEvent(self, e):
        if self.step >= 100:
            self.timer.stop()
            self.pbar.setValue(0)
            self.status.setText("Load AI Model")
            self.setVisible(False)
            self.finished_notify.emit(True)
            return
        elif self.step >=95 and self.limit_object is not None:
            if not self.limit_object.is_completed():
                return
        elif self.step >= 80:
            self.status.setText('Generate report')

        elif self.step>= 30:
            self.status.setText('Analyze interest region')

        self.step = self.step + 1
        self.pbar.setValue(self.step)
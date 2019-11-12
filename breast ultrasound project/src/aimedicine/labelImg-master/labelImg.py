#!/usr/bin/env python
# -*- coding: utf-8 -*-
import codecs
import distutils.spawn
import os.path
import platform
import re
import sys
import subprocess
import cv2
from functools import partial
from collections import defaultdict
import threading
from time import strftime, gmtime
from os import path, mkdir
import numpy as np
import qimage2ndarray.qimageview_python as qp
import cv2
import matplotlib.pyplot as plt

try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except ImportError:
    # needed for py3+qt4
    # Ref:
    # http://pyqt.sourceforge.net/Docs/PyQt4/incompatible_apis.html
    # http://stackoverflow.com/questions/21217399/pyqt4-qtcore-qvariant-object-instead-of-a-string
    if sys.version_info.major >= 3:
        import sip
        sip.setapi('QVariant', 2)
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

import resources

# Add internal libs
from libs.constants import *
from libs.lib import struct, newAction, newIcon, addActions, fmtShortcut, generateColorByText
from libs.settings import Settings
from libs.shape import Shape, DEFAULT_LINE_COLOR, DEFAULT_FILL_COLOR
from libs.stringBundle import StringBundle
from libs.canvas import Canvas
from libs.zoomWidget import ZoomWidget
from libs.labelDialog import LabelDialog
from libs.colorDialog import ColorDialog
from libs.labelFile import LabelFile, LabelFileError
from libs.toolBar import ToolBar
from libs.pascal_voc_io import PascalVocReader
from libs.pascal_voc_io import XML_EXT
from libs.yolo_io import YoloReader
from libs.yolo_io import TXT_EXT
# add by yuan ==> modfy pascal voc io add segmentation
from libs.pascal_vrc_io import PascalVrcReader
from libs.pascal_vrc_io import XML_EXT
from libs.libProgressbar import libProgressbar

from libs.ustr import ustr
from libs.version import __version__
from libs.hashableQListWidgetItem import HashableQListWidgetItem
import tensorflow as tf
import aimedicine.USDicom as USDicom
import aimedicine.BUModel as BUModel
import qimage2ndarray.qimageview_python as qp
import libs.convertqtimage as convertqtimage
from libs.detectedshape import DetectedShape

import time

__appname__ = "AI Medicine For Breast " #'labelImg'

# Utility functions and classes.

def have_qstring():
    '''p3/qt5 get rid of QString wrapper as py3 has native unicode str type'''
    return not (sys.version_info.major >= 3 or QT_VERSION_STR.startswith('5.'))

def util_qt_strlistclass():
    return QStringList if have_qstring() else list


class WindowMixin(object):
    def menu(self, title, actions=None):
        menu = self.menuBar().addMenu(title)
        if actions:
            addActions(menu, actions)
        return menu

    def toolbar(self, title, actions=None):
        toolbar = ToolBar(title)
        toolbar.setObjectName(u'%sToolBar' % title)
        # toolbar.setOrientation(Qt.Vertical)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        if actions:
            addActions(toolbar, actions)
        self.addToolBar(Qt.LeftToolBarArea, toolbar)
        return toolbar


class MainWindow(QMainWindow, WindowMixin):
    FIT_WINDOW, FIT_WIDTH, MANUAL_ZOOM = list(range(3))

    def __init__(self, defaultFilename=None, defaultPrefdefClassFile=None, defaultSaveDir=None):
        super(MainWindow, self).__init__()
        self.setWindowTitle(__appname__)

        self.bu_model = BUModel.BUModelClass()
        self.bu_model.loading_AI_Mode()

        # Load setting in the main thread
        self.settings = Settings()
        self.settings.load()
        settings = self.settings

        # Load string bundle for i18n
        self.stringBundle = StringBundle.getBundle()
        getStr = lambda strId: self.stringBundle.getString(strId)

        # Save as Pascal voc xml
        self.defaultSaveDir = defaultSaveDir
        self.usingPascalVocFormat = True
        self.usingYoloFormat = False

        # For loading all image under a directory
        self.mImgList = []
        self.dirname = None
        self.labelHist = []
        self.lastOpenDir = None

        # Whether we need to save or not.
        self.dirty = False

        self._noSelectionSlot = False
        self._beginner = True
        self.screencastViewer = self.getAvailableScreencastViewer()
        self.screencast = "https://youtu.be/p0nR2YsCY_U"

        # Load predefined classes to the list
        #self.loadPredefinedClasses(defaultPrefdefClassFile)

        # Main widgets and related state.
        #self.labelDialog = LabelDialog(parent=self, listItem=self.labelHist)
        self.BUModeProgressbar = libProgressbar(parent=self)
        #self.BUModeProgressbar.showProgressbar()
        #self.BUModeProgressbar.finished_notify.connect(self.ai_anaylize_completed)

        self.itemsToShapes = {}
        self.shapesToItems = {}
        self.prevLabelText = ''

        listLayout = QVBoxLayout()
        listLayout.setContentsMargins(0, 0, 0, 0)

        # Create a widget for using default label
        #self.useDefaultLabelCheckbox = QCheckBox(getStr('useDefaultLabel'))
        #self.useDefaultLabelCheckbox.setChecked(False)
        #self.defaultLabelTextLine = QLineEdit()

        #useDefaultLabelQHBoxLayout = QHBoxLayout()
        #useDefaultLabelQHBoxLayout.addWidget(self.useDefaultLabelCheckbox)
        #useDefaultLabelQHBoxLayout.addWidget(self.defaultLabelTextLine)

        #useDefaultLabelContainer = QWidget()
        #useDefaultLabelContainer.setLayout(useDefaultLabelQHBoxLayout)

        # Create a widget for edit and diffc button
        #self.diffcButton = QCheckBox(getStr('useDifficult'))
        #self.diffcButton.setChecked(False)
        #self.diffcButton.stateChanged.connect(self.btnstate)

        #self.editButton = QToolButton()
        #self.editButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        # Add some of widgets to listLayout
        #listLayout.addWidget(self.editButton)
        #listLayout.addWidget(self.diffcButton)
        #listLayout.addWidget(useDefaultLabelContainer)

        # Create and add a widget for showing current label items

        self.labelList = QListWidget()
        labelListContainer = QWidget()
        labelListContainer.setLayout(listLayout)
        #self.labelList.itemActivated.connect(self.labelSelectionChanged)
        #self.labelList.itemSelectionChanged.connect(self.labelSelectionChanged)

        # self.labelList.itemDoubleClicked.connect(self.editLabel)

        # Connect to itemChanged to detect checkbox changes.
        #self.labelList.itemChanged.connect(self.labelItemChanged)
        #listLayout.addWidget(self.labelList)


        self.PropertyTable = QTableWidget()
        listLayout.addWidget(self.PropertyTable)

        font = QFont('Times New Roman', 12)
        font.setBold(True)  # 设置字体加粗
        self.PropertyTable.horizontalHeader().setFont(font)  # 设置表头字体为font设置的字体样式
        #self.PropertyTable.setFrameShape(QFrame.NoFrame)  ##设置无表格的外框
        self.PropertyTable.horizontalHeader().setFixedHeight(26)  ##设置表头高度
        self.PropertyTable.horizontalHeader().setStyleSheet("QHeaderView::section { background-color:gray }");
        self.PropertyTable.horizontalHeader().setSectionResizeMode(7, QHeaderView.Stretch)  # 设置第五列宽度自动调整，充满屏幕
        self.PropertyTable.horizontalHeader().setStretchLastSection(True)  ##设置最后一列拉伸至最大
        self.PropertyTable.setSelectionMode(QAbstractItemView.SingleSelection)  # 设置只可以单选，可以使用ExtendedSelection进行多选
        self.PropertyTable.setSelectionBehavior(QAbstractItemView.SelectRows)  # 设置 不可选择单个单元格，只可选择一行。

        self.PropertyTable.setColumnCount(2)  ##设置表格一共有五列
        self.PropertyTable.setHorizontalHeaderLabels(['名稱', '值'])  # 设置表头文字
        self.PropertyTable.setEditTriggers(QAbstractItemView.NoEditTriggers)  # 设置表格不可更改
        self.PropertyTable.verticalHeader().setHidden(True) # hide index column
        self.PropertyTable.horizontalHeader().resizeSection(0, 110)  # 设置第一列的宽度为200

        self.initial_property_table([])

        #print ('boxLabelText : ', getStr('boxLabelText'))
        self.dock = QDockWidget('AI Analyze Information' , self) #getStr('boxLabelText')
        #print('labels : ', getStr('labels'))
        self.dock.setObjectName(getStr('labels'))
        self.dock.setWidget(labelListContainer)

        """ file list
        self.fileListWidget = QListWidget()
        self.fileListWidget.itemDoubleClicked.connect(self.fileitemDoubleClicked)
        filelistLayout = QVBoxLayout()
        filelistLayout.setContentsMargins(0, 0, 0, 0)
        filelistLayout.addWidget(self.fileListWidget)
        fileListContainer = QWidget()
        fileListContainer.setLayout(filelistLayout)
        self.filedock = QDockWidget(getStr('fileList'), self)
        self.filedock.setObjectName(getStr('files'))
        self.filedock.setWidget(fileListContainer)
        """
        self.test_range_image = None
        self.zoomWidget = ZoomWidget()
        self.colorDialog = ColorDialog(parent=self)

        self.canvas = Canvas(parent=self)
        self.canvas.zoomRequest.connect(self.zoomRequest)
        self.canvas.setDrawingShapeToSquare(settings.get(SETTING_DRAW_SQUARE, False))

        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
        scroll.setWidgetResizable(True)
        self.scrollBars = {
            Qt.Vertical: scroll.verticalScrollBar(),
            Qt.Horizontal: scroll.horizontalScrollBar()
        }

        self.scrollArea = scroll
        self.canvas.scrollRequest.connect(self.scrollRequest)
        self.canvas.newShape.connect(self.newShape)
        self.canvas.shapeMoved.connect(self.setDirty)
        self.canvas.selectionChanged.connect(self.shapeSelectionChanged)
        self.canvas.drawingPolygon.connect(self.toggleDrawingSensitive)

        self.setCentralWidget(scroll)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock)

        #self.addDockWidget(Qt.RightDockWidgetArea, self.filedock)

        #self.filedock.setFeatures(QDockWidget.DockWidgetFloatable)

        self.dockFeatures = QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetFloatable
        self.dock.setFeatures(self.dock.features() ^ self.dockFeatures)

        # menu Actions
        action = partial(newAction, self)
        quit = action(getStr('quit'), self.close,
                      'Ctrl+Q', 'quit', getStr('quitApp'))

        open = action(getStr('openFile'), self.openFile,
                      'Ctrl+O', 'open', getStr('openFileDetail'))

        opendir = action(getStr('openDir'), self.openDirDialog,
                         'Ctrl+u', 'open', getStr('openDir'))

        changeSavedir = action(getStr('changeSaveDir'), self.changeSavedirDialog,
                               'Ctrl+r', 'open', getStr('changeSavedAnnotationDir'))

       # openAnnotation = action(getStr('openAnnotation'), self.openAnnotationDialog,
       #                         'Ctrl+Shift+O', 'open', getStr('openAnnotationDetail'))

        openNextImg = action(getStr('nextImg'), self.openNextImg,
                             'd', 'next', getStr('nextImgDetail'))

        openPrevImg = action(getStr('prevImg'), self.openPrevImg,
                             'a', 'prev', getStr('prevImgDetail'))

        #verify = action(getStr('verifyImg'), self.verifyImg,
        #                'space', 'verify', getStr('verifyImgDetail'))

        save = action(getStr('save'), self.saveFile,
                      'Ctrl+S', 'save', getStr('saveDetail'), enabled=False)

        save_format = action('&PascalVOC', self.change_format,
                      'Ctrl+', 'format_voc', getStr('changeSaveFormat'), enabled=True)

        saveAs = action(getStr('saveAs'), self.saveFileAs,
                        'Ctrl+Shift+S', 'save-as', getStr('saveAsDetail'), enabled=False)

        close = action(getStr('closeCur'), self.closeFile, 'Ctrl+W', 'close', getStr('closeCurDetail'))

        resetAll = action(getStr('resetAll'), self.resetAll, None, 'resetall', getStr('resetAllDetail'))

        color1 = action(getStr('boxLineColor'), self.chooseColor1,
                        'Ctrl+L', 'color_line', getStr('boxLineColorDetail'))

        createMode = action(getStr('crtBox'), self.setCreateMode,
                            'w', 'new', getStr('crtBoxDetail'), enabled=False)
        editMode = action('&Edit\nRectBox', self.setEditMode,
                          'Ctrl+J', 'edit', u'Move and edit Boxs', enabled=False)

        create = action(getStr('crtBox'), self.createShape,
                        'w', 'new', getStr('crtBoxDetail'), enabled=False)

        delete = action(getStr('delBox'), self.deleteSelectedShape,
                        'Delete', 'delete', getStr('delBoxDetail'), enabled=False)
        copy = action(getStr('dupBox'), self.copySelectedShape,
                      'Ctrl+D', 'copy', getStr('dupBoxDetail'),
                      enabled=False)

        DispRect = action(u'&Display Rectangle', self.setDisplayRect,
                            'Ctrl+W', 'rect', u'Display Delect Rectangle', enabled=False)

        DispAxis = action(u'&Display Axis', self.setDisplayAxis,
                          'Ctrl+J', 'axis', u'Display Axis', enabled=False)


        # yuan add ==> create region menu
        region = action(getStr('segmentregion'), self.createRegion, '',
                        icon='region', tip=getStr('segmentregionDetial'), enabled=False)

       # splitimg = action(getStr('genSplitImage'), self.createsplitimg, '',
       #                 icon='splitimg', tip=getStr('generateSplitImageDetial'), enabled=False)

        startaipredict = action(getStr('toAIAnalyze'), self.startToPredict, '',
                           icon='splitimg', tip=u'Start to AI Analyze', enabled=True)

        #aipredict = action(u'Detect Position', self.toAIPredict, '',
        #               icon='splitimg', tip=u'Select detect position' , enabled=True)
        aipredict = action(getStr('toAIAnalyze'), self.toAIPredict, '',
                       icon='splitimg', tip=u'Start to AI Analyze' , enabled=True)

        savedicom = action(getStr('saveToDICOM'), self.saveAsDICOM, '',
                          icon='splitimg', tip=getStr('saveToDICOMDetial'), enabled=True)

        advancedMode = action(getStr('advancedMode'), self.toggleAdvancedMode,
                              'Ctrl+Shift+A', 'expert', getStr('advancedModeDetail'),
                              checkable=True)

        hideAll = action('&Hide\nRectBox', partial(self.togglePolygons, False),
                         'Ctrl+H', 'hide', getStr('hideAllBoxDetail'),
                         enabled=False)
        showAll = action('&Show\nRectBox', partial(self.togglePolygons, True),
                         'Ctrl+A', 'hide', getStr('showAllBoxDetail'),
                         enabled=False)

        help = action(getStr('tutorial'), self.showTutorialDialog, None, 'help', getStr('tutorialDetail'))
        showInfo = action(getStr('info'), self.showInfoDialog, None, 'help', getStr('info'))

        # view menu
        zoom = QWidgetAction(self)
        zoom.setDefaultWidget(self.zoomWidget)
        self.zoomWidget.setWhatsThis(
            u"Zoom in or out of the image. Also accessible with"
            " %s and %s from the canvas." % (fmtShortcut("Ctrl+[-+]"),
                                             fmtShortcut("Ctrl+Wheel")))
        self.zoomWidget.setEnabled(False)

        zoomIn = action(getStr('zoomin'), partial(self.addZoom, 10),
                        'Ctrl++', 'zoom-in', getStr('zoominDetail'), enabled=False)
        zoomOut = action(getStr('zoomout'), partial(self.addZoom, -10),
                         'Ctrl+-', 'zoom-out', getStr('zoomoutDetail'), enabled=False)
        zoomOrg = action(getStr('originalsize'), partial(self.setZoom, 100),
                         'Ctrl+=', 'zoom', getStr('originalsizeDetail'), enabled=False)
        fitWindow = action(getStr('fitWin'), self.setFitWindow,
                           'Ctrl+F', 'fit-window', getStr('fitWinDetail'),
                           checkable=True, enabled=False)
        fitWidth = action(getStr('fitWidth'), self.setFitWidth,
                          'Ctrl+Shift+F', 'fit-width', getStr('fitWidthDetail'),
                          checkable=True, enabled=False)

        # Group zoom controls into a list for easier toggling.
        zoomActions = (self.zoomWidget, zoomIn, zoomOut,
                       zoomOrg, fitWindow, fitWidth)
        self.zoomMode = self.MANUAL_ZOOM
        self.scalers = {
            self.FIT_WINDOW: self.scaleFitWindow,
            self.FIT_WIDTH: self.scaleFitWidth,
            # Set to one to scale to 100% when loading files.
            self.MANUAL_ZOOM: lambda: 1,
        }

        #edit = action(getStr('editLabel'), self.editLabel,
        #              'Ctrl+E', 'edit', getStr('editLabelDetail'),
        #              enabled=False)
        #self.editButton.setDefaultAction(edit)

        shapeLineColor = action(getStr('shapeLineColor'), self.chshapeLineColor,
                                icon='color_line', tip=getStr('shapeLineColorDetail'),
                                enabled=False)

        shapeFillColor = action(getStr('shapeFillColor'), self.chshapeFillColor,
                                icon='color', tip=getStr('shapeFillColorDetail'),
                                enabled=False)

        labels = self.dock.toggleViewAction()
        labels.setText(getStr('showHide'))
        labels.setShortcut('Ctrl+Shift+L')

        # Lavel list context menu. mouse lef menu
        labelMenu = QMenu()
        #addActions(labelMenu, (edit, splitimg, delete))
        #addActions(labelMenu, (edit, delete))
        self.labelList.setContextMenuPolicy(Qt.CustomContextMenu)
        self.labelList.customContextMenuRequested.connect(
            self.popLabelListMenu)

        # Draw squares/rectangles
        self.drawSquaresOption = QAction('Draw Squares', self)
        self.drawSquaresOption.setShortcut('Ctrl+Shift+R')
        self.drawSquaresOption.setCheckable(True)
        self.drawSquaresOption.setChecked(settings.get(SETTING_DRAW_SQUARE, False))
        self.drawSquaresOption.triggered.connect(self.toogleDrawSquare)

        # Store actions for further handling. edit=edit,
        # yuan add region struct to here and add region to onLoadActive and beginnerContext splitimg=splitimg,
        self.actions = struct(save=save, save_format=save_format, saveAs=saveAs, open=open, close=close, resetAll=resetAll,
                              lineColor=color1, create=create, region=region, aipredict=aipredict, savedicom=savedicom,
                              delete=delete,  copy=copy,DispRect=DispRect, DispAxis=DispAxis,
                              startaipredict=startaipredict,
                              createMode=createMode, editMode=editMode, advancedMode=advancedMode,
                              shapeLineColor=shapeLineColor, shapeFillColor=shapeFillColor,
                              zoom=zoom, zoomIn=zoomIn, zoomOut=zoomOut, zoomOrg=zoomOrg,
                              fitWindow=fitWindow, fitWidth=fitWidth,
                              zoomActions=zoomActions,
                              fileMenuActions=(open, opendir, save, saveAs, close, resetAll, quit),
                              beginner=(), advanced=(),
                              # menu = mouse left key in press
                              #editMenu=(edit, splitimg, delete,
                              #          None, color1),
                              # editMenu=(edit, delete,
                              #          None, color1),
                              #editMenu=(edit, copy, delete,
                              #          None, color1, self.drawSquaresOption),
                              # beginnerContext=(create, region, edit, copy, delete),
                              #beginnerContext=(create, region, None, splitimg, edit, delete),
                              #create, region, None, edit,
                              beginnerContext=(delete, None, aipredict, savedicom),
                              beginner2Context=(delete, None, startaipredict, savedicom),
                              #advancedContext=(createMode, editMode, edit, copy,
                              #                 delete, shapeLineColor, shapeFillColor),

                              onLoadActive=(
                                    close, create, region, createMode, editMode),

                              onShapesPresent=(saveAs, hideAll, showAll))


        # add by yuan
        self.menus = struct(
            file=self.menu('&File'),
            #edit=self.menu('&Edit'),
            help=self.menu('&Help'),
            #recentFiles=QMenu('Open &Recent'),
            labelList=labelMenu)

        """
        self.menus = struct(
            file=self.menu('&File'),
            edit=self.menu('&Edit'),
            view=self.menu('&View'),
            help=self.menu('&Help'),
            recentFiles=QMenu('Open &Recent'),
            labelList=labelMenu)
        """

        # Auto saving : Enable auto saving if pressing next
        self.autoSaving = QAction(getStr('autoSaveMode'), self)
        self.autoSaving.setCheckable(True)
        self.autoSaving.setChecked(settings.get(SETTING_AUTO_SAVE, False))

        # Sync single class mode from PR#106
        self.singleClassMode = QAction(getStr('singleClsMode'), self)
        self.singleClassMode.setShortcut("Ctrl+Shift+S")
        self.singleClassMode.setCheckable(True)
        self.singleClassMode.setChecked(settings.get(SETTING_SINGLE_CLASS, False))
        self.lastLabel = None

        # Add option to enable/disable labels being displayed at the top of bounding boxes
        self.displayLabelOption = QAction(getStr('displayLabel'), self)
        self.displayLabelOption.setShortcut("Ctrl+Shift+P")
        self.displayLabelOption.setCheckable(True)
        self.displayLabelOption.setChecked(settings.get(SETTING_PAINT_LABEL, False))
        self.displayLabelOption.triggered.connect(self.togglePaintLabelsOption)

        addActions(self.menus.file, (open, opendir,  save, saveAs, close, quit))

        """
        addActions(self.menus.file,
                   (open, opendir, save, saveAs,
                    close, quit))
        """
        addActions(self.menus.help, (help, showInfo))

        """
        addActions(self.menus.file,
                   (open, opendir, changeSavedir, openAnnotation, self.menus.recentFiles, save, save_format, saveAs, close, resetAll, quit))
        addActions(self.menus.help, (help, showInfo))
        addActions(self.menus.view, (
            self.autoSaving,
            self.singleClassMode,
            self.displayLabelOption,
            labels, advancedMode, None,
            hideAll, showAll, None,
            zoomIn, zoomOut, zoomOrg, None,
            fitWindow, fitWidth))
        """
        self.menus.file.aboutToShow.connect(self.updateFileMenu)

        # Custom context menu for the canvas widget:
        addActions(self.canvas.menus[0], self.actions.beginnerContext)
        #addActions(self.canvas.menus[1], (
        #    action('&Copy here', self.copyShape),
        #    action('&Move here', self.moveShape)))

        self.tools = self.toolbar('Tools')

        # create , copy , delete is draw recttage box option
        self.actions.beginner = (open, save, delete, None, DispRect, DispAxis)

        """
        self.actions.beginner = (
            open, opendir, changeSavedir, openNextImg, openPrevImg, verify, save, save_format, None, create,  delete, copy, None,
            zoomIn, zoom, zoomOut, fitWindow, fitWidth)
        """

        self.actions.advanced = (
            open, opendir, changeSavedir, openNextImg, openPrevImg, save, save_format, None,
            createMode, editMode, None,
            hideAll, showAll)

        self.statusBar().showMessage('%s started.' % __appname__)
        self.statusBar().show()

        # Application state.
        self.image = QImage()
        self.filePath = ustr(defaultFilename)
        self.recentFiles = []
        self.maxRecent = 7
        self.lineColor = None
        self.fillColor = None
        self.zoom_level = 100
        self.fit_window = False

        # Add Chris
        self.difficult = False

        ## Fix the compatible issue for qt4 and qt5. Convert the QStringList to python list
        if settings.get(SETTING_RECENT_FILES):
            if have_qstring():
                recentFileQStringList = settings.get(SETTING_RECENT_FILES)
                self.recentFiles = [ustr(i) for i in recentFileQStringList]
            else:
                self.recentFiles = recentFileQStringList = settings.get(SETTING_RECENT_FILES)

        size = settings.get(SETTING_WIN_SIZE, QSize(600, 500))
        position = QPoint(0, 0)
        saved_position = settings.get(SETTING_WIN_POSE, position)
        # Fix the multiple monitors issue
        for i in range(QApplication.desktop().screenCount()):
            if QApplication.desktop().availableGeometry(i).contains(saved_position):
                position = saved_position
                break

        self.resize(size)
        self.move(position)
        saveDir = ustr(settings.get(SETTING_SAVE_DIR, None))
        self.lastOpenDir = ustr(settings.get(SETTING_LAST_OPEN_DIR, None))

        if self.defaultSaveDir is None and saveDir is not None and os.path.exists(saveDir):
            self.defaultSaveDir = saveDir
            self.statusBar().showMessage('%s started. Annotation will be saved to %s' %
                                         (__appname__, self.defaultSaveDir))
            self.statusBar().show()

        self.restoreState(settings.get(SETTING_WIN_STATE, QByteArray()))

        #Shape.line_color = self.lineColor = QColor(settings.get(SETTING_LINE_COLOR, DEFAULT_LINE_COLOR))
        #Shape.fill_color = self.fillColor = QColor(settings.get(SETTING_FILL_COLOR, DEFAULT_FILL_COLOR))
        #self.canvas.setDrawingColor(self.lineColor)


        # Add chris
        #Shape.difficult = self.difficult

        def xbool(x):
            if isinstance(x, QVariant):
                return x.toBool()
            return bool(x)

        if xbool(settings.get(SETTING_ADVANCE_MODE, False)):
            self.actions.advancedMode.setChecked(True)
            self.toggleAdvancedMode()

        # Populate the File menu dynamically.
        self.updateFileMenu()

        # Since loading the file may take some time, make sure it runs in the background.
        if self.filePath and os.path.isdir(self.filePath):
            self.queueEvent(partial(self.importDirImages, self.filePath or ""))
        elif self.filePath:
            self.queueEvent(partial(self.loadFile, self.filePath or ""))

        # Callbacks:
        self.zoomWidget.valueChanged.connect(self.paintCanvas)

        self.populateModeActions()

        # Display cursor coordinates at the right of status bar
        self.labelCoordinates = QLabel('')
        self.statusBar().addPermanentWidget(self.labelCoordinates)

        # Open Dir if deafult file
        if self.filePath and os.path.isdir(self.filePath):
            self.openDirDialog(dirpath=self.filePath)

    def initial_property_table(self, value_list):
        ##下面六行用于生成居中的checkbox，不知道有没有别的好方法
        property_name = ['BI-RADS', '偵測框的左上座標','偵測框的右下座標' ,'腫瘤尺寸',
                         '長軸座標', '長軸長度', '短軸座標', '短軸長度']
        self.PropertyTable.setRowCount(len(property_name))
        self.PropertyTable.setIconSize(QSize(32, 32))
        for index, item in enumerate(property_name):
            if index == 4 or index == 5:
                item= QTableWidgetItem(QIcon('./resources/icons/VIRTICAL_LINE.png'), item)
            elif index == 6 or index == 7:
                item = QTableWidgetItem(QIcon('./resources/icons/HORIZONTAL_LINE.png'), item)
            else:
                item = QTableWidgetItem(item)
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.PropertyTable.setItem(index, 0, item)
            self.PropertyTable.setItem(index, 1, QTableWidgetItem(''))

        if value_list is not None:
            for index , item in enumerate(value_list):
                self.PropertyTable.setItem(index, 1, QTableWidgetItem(item))

        #self.PropertyTable.move(0, 0)
        # self.lines.append([id, ck, name, score, add])

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Control:
            self.canvas.setDrawingShapeToSquare(False)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Control:
            # Draw rectangle if Ctrl is pressed
            self.canvas.setDrawingShapeToSquare(True)

    ## Support Functions ##
    def set_format(self, save_format):
        if save_format == FORMAT_PASCALVOC:
            self.actions.save_format.setText(FORMAT_PASCALVOC)
            self.actions.save_format.setIcon(newIcon("format_voc"))
            self.usingPascalVocFormat = True
            self.usingYoloFormat = False
            LabelFile.suffix = XML_EXT

        elif save_format == FORMAT_YOLO:
            self.actions.save_format.setText(FORMAT_YOLO)
            self.actions.save_format.setIcon(newIcon("format_yolo"))
            self.usingPascalVocFormat = False
            self.usingYoloFormat = True
            LabelFile.suffix = TXT_EXT

    def change_format(self):
        if self.usingPascalVocFormat: self.set_format(FORMAT_YOLO)
        elif self.usingYoloFormat: self.set_format(FORMAT_PASCALVOC)

    def noShapes(self):
        return not self.itemsToShapes

    def toggleAdvancedMode(self, value=True):
        self._beginner = not value
        self.canvas.setEditing(True)
        self.populateModeActions()
        self.editButton.setVisible(not value)
        if value:
            self.actions.createMode.setEnabled(True)
            self.actions.editMode.setEnabled(False)
            self.dock.setFeatures(self.dock.features() | self.dockFeatures)
        else:
            self.dock.setFeatures(self.dock.features() ^ self.dockFeatures)

    # add by yuan : modify popup menu when user click right key on mouse
    def populateModeActions(self):
        if self.beginner():
            if self.test_range_image is None:
                tool, menu = self.actions.beginner, self.actions.beginnerContext
            else:
                tool, menu = self.actions.beginner, self.actions.beginner2Context
        else:
            tool, menu = self.actions.advanced, self.actions.advancedContext

        self.tools.clear()
        addActions(self.tools, tool)

        self.canvas.menus[0].clear()
        addActions(self.canvas.menus[0], menu)
       # self.menus.edit.clear()

        # add by yuan ==> add region
        actions = (self.actions.create, self.actions.region, ) if self.beginner()\
            else (self.actions.createMode, self.actions.editMode)

        """
        actions = (self.actions.create, ) if self.beginner()\
            else (self.actions.createMode, self.actions.editMode)
        """
        # addActions(self.menus.edit, actions + self.actions.editMenu)

    def setBeginner(self):
        self.tools.clear()
        addActions(self.tools, self.actions.beginner)

    def setAdvanced(self):
        self.tools.clear()
        addActions(self.tools, self.actions.advanced)

    def setDirty(self):
        self.dirty = True
        self.actions.save.setEnabled(True)

    def setClean(self):
        self.dirty = False
        self.actions.save.setEnabled(False)
        self.actions.create.setEnabled(True)
        self.actions.region.setEnabled(True)

    def toggleActions(self, value=True):
        """Enable/Disable widgets which depend on an opened image."""
        for z in self.actions.zoomActions:
            z.setEnabled(value)
        for action in self.actions.onLoadActive:
            action.setEnabled(value)

        self.actions.DispRect.setEnabled(True)
        self.actions.DispAxis.setEnabled(False)

    def queueEvent(self, function):
        QTimer.singleShot(0, function)

    def status(self, message, delay=5000):
        self.statusBar().showMessage(message, delay)

    def resetState(self):
        self.itemsToShapes.clear()
        self.shapesToItems.clear()
        self.labelList.clear()
        self.filePath = None
        self.imageData = None
        self.labelFile = None
        self.canvas.resetState()
        self.labelCoordinates.clear()

    def currentItem(self):
        items = self.labelList.selectedItems()
        if items:
            return items[0]
        return None

    def addRecentFile(self, filePath):
        if filePath in self.recentFiles:
            self.recentFiles.remove(filePath)
        elif len(self.recentFiles) >= self.maxRecent:
            self.recentFiles.pop()
        self.recentFiles.insert(0, filePath)

    def beginner(self):
        return self._beginner

    def advanced(self):
        return not self.beginner()

    def getAvailableScreencastViewer(self):
        osName = platform.system()

        if osName == 'Windows':
            return ['C:\\Program Files\\Internet Explorer\\iexplore.exe']
        elif osName == 'Linux':
            return ['xdg-open']
        elif osName == 'Darwin':
            return ['open', '-a', 'Safari']

    ## Callbacks ##
    def showTutorialDialog(self):
        subprocess.Popen(self.screencastViewer + [self.screencast])

    def showInfoDialog(self):
        msg = u'Name:{0} \nApp Version:{1} \n{2} '.format(__appname__, __version__, sys.version_info)
        QMessageBox.information(self, u'Information', msg)

    def createShape(self):
        assert self.beginner()
        self.canvas.setEditing(False)
        self.canvas.setDrawRegion(False)
        self.actions.create.setEnabled(False)
        self.actions.region.setEnabled(True) # add by yuan => Disable

    # yuan add ==> add region shape function action
    def createRegion(self):
        assert self.beginner()
        self.canvas.setEditing(False)
        self.canvas.setDrawRegion(True)
        self.actions.region.setEnabled(False)
        self.actions.create.setEnabled(True) # add by yuan => Disable

    # add by yuan ==> split image when user select shape

    def saveAsDICOM(self):
        assert self.beginner()
        try:
            self.setClean()
            print('start saveAsDICOM')
            filename = self.canvas.fileName.split('.')
            us_dicom = USDicom.USDicomClass(os.path.join(os.path.abspath('.')+"//DICOM",filename[0] +'.dcm'), True)
            img = self.canvas.getImageArray()
            # save ultrasound image
            us_dicom.setUSImage(img , img.shape[1], img.shape[0])

            # save rectangle
            rect_list= self.canvas.get_tissue_rect_list()
            for i, rect in enumerate(rect_list):
                us_dicom.setRegion(rect, 0x01)  # tissue

            rect_list = self.canvas.findRectanglePointforshape()
            for i, rect in enumerate(rect_list):
                if rect is not None:
                    us_dicom.setRegion(rect, 0x02)  # color


            us_dicom.setPrivateCreator(self.canvas.get_shape_property(),
                                       self.canvas.get_axis_property(),
                                       self.canvas.get_shapes_points())

            us_dicom.save()

            print('end saveAsDICOM')
        except:
            print('catch error')

    def ai_anaylize_completed(self):
        if self.bu_model is None:
            return

        r = self.bu_model.get_result()
        if (r is not None and len(r['class_ids']) > 0):
            print(r['class_ids'])
            check_point = self.canvas.get_check_point()
            print('check point : ', check_point)

            rect_point = self.canvas.get_rect_point()
            print('rect point : ', rect_point)

            if self.bu_model.region_of_interests(r, check_point, rect_point):
                self.canvas.set_detect_shape(self.bu_model.bi_rads, rect_point[0],
                                             self.bu_model.get_all_side_points())

                self.canvas.set_tumor_area(self.bu_model.get_all_region_area())
                self.canvas.set_axis_information(rect_point[0],
                                                 self.bu_model.hv_axis,
                                                 self.bu_model.horizontal_len,
                                                 self.bu_model.vertical_len)

                self.canvas.set_detected_rectangle(rect_point[0], self.bu_model.get_all_roi_rect())

                self.canvas.UnselectedShape()

                #for shape in self
                self.shapeSelectionChanged(True)
                self.setDirty()

            """
            if self.bu_model.region_of_interest(r, check_point, rect_point):
                self.canvas.set_detect_shape(self.bu_model.bi_rads, rect_point[0], self.bu_model.get_side_points())

                self.canvas.set_tumor_area(self.bu_model.get_region_area())
                self.canvas.set_axis_information(rect_point[0],
                                                 self.bu_model.hv_axis,
                                                 self.bu_model.horizontal_len,
                                                 self.bu_model.vertical_len)

                self.canvas.set_detected_rectangle(rect_point[0], self.bu_model.get_roi_rect())
                self.setDirty()
            """

        self.canvas.clear_detect_rect()

    def startToPredict(self):
        try:
            if not self.test_range_image is None:
                self.bu_model.analyze_image([self.test_range_image])
                self.BUModeProgressbar.set_limit_object(self.bu_model)
                self.BUModeProgressbar.showProgressbar()
                self.BUModeProgressbar.finished_notify.connect(self.ai_anaylize_completed)

        except Exception as e:
            print(str(e))
        finally:
            self.canvas.clear_detect_rect()
            self.populateModeActions()

    def saveSplitHSImage(self, splitimg, serial_num):
        print("begin - saveSplitHSImage")

        # self.fileName
        img_file = '{}.jpg'.format(serial_num)
        hsimg_file = '{}_HS.jpg'.format(serial_num)
        afimg_file = '{}_after.jpg'.format(serial_num)
        beimg_file = '{}_before.jpg'.format(serial_num)
        img_path = path.abspath('breast dataset/train HSdataset')
        if not path.exists(img_path):
            mkdir(img_path)

        # print (splitimg)
        min_gray = np.min(splitimg)
        max_gray = np.max(splitimg)
        # print (img[0][:10])
        print('min:', min_gray, 'max:', max_gray)
        x_axis = list(range(0, 255))
        # y_axis = splitimg.flatten().tolist()
        plt.figure()
        plt.hist(splitimg.flatten().tolist(), bins=x_axis)
        plt.title('Original Histogram - Min:{} Max:{}'.format(min_gray, max_gray))
        plt.savefig(path.join(img_path, beimg_file))

        scale = 255 / (max_gray - min_gray)
        print(scale)
        trasfor_img = (splitimg - min_gray)
        splitimg = trasfor_img * scale
        splitimg = splitimg.astype(int)

        # splitimg.save(path.join(img_path, img_file), 'JPG', 100)
        cv2.imwrite(path.join(img_path, img_file), splitimg, [cv2.IMWRITE_JPEG_QUALITY, 100])
        cv2.imwrite(path.join(img_path, hsimg_file), splitimg, [cv2.IMWRITE_JPEG_QUALITY, 100])

        min_gray = np.min(splitimg)
        max_gray = np.max(splitimg)
        print('min:', min_gray, 'max:', max_gray)

        plt.figure()
        plt.hist(splitimg.flatten().tolist(), bins=x_axis)
        plt.title('Histogram Stretching - Min:{} Max:{}'.format(min_gray, max_gray))
        plt.savefig(path.join(img_path, afimg_file))

        print("end - saveHSSplitImage ")

    def initial_job(self, thread_event,split_img):
        print('begin - saveSelectedShape')
        str_time = strftime("%m%d%H%M%S", gmtime())
        self.saveSplitHSImage(split_img, str_time)
        print("end - findContainRegion")

    def toAIPredict(self):
        try:
            self.test_range_image = None
            if not self.bu_model.is_initial_completed():
                reply = QMessageBox.information(self,  # 使用infomation信息框
                                                "AI Analyze",
                                                "模組尚未載入完成，請稍候",
                                                QMessageBox.Yes)
                return

            print('start toAIPredict')

            # time.sleep(5)

            test_range_image = self.canvas.capture_predict_area()

            #self.actions.copy.setEnabled
            if not test_range_image is None:
            #    test_range_image
                #if self.bu_model is None:
                #     self.bu_model = BUModel.BUModelClass()
                #     self.bu_model.loading_AI_Mode()

                #print(type(test_range_image), test_range_image.shape)
                #print("1 : ",test_range_image[0:10])
                #cv2.imwrite('d://test2.jpg', test_range_image)

                #test_range_image2 = cv2.imread('C://Users//Yuan//Desktop//Tibame//aimedicine//labelImg-master//aimedicine//test.jpg')
                #test_range_image2 = cv2.resize(test_range_image2, (192, 192))
                #print (type(test_range_image2), test_range_image2.shape)
                #print ("2 : ", test_range_image2[0:10])
                #results =  self.bu_model.predict_model([test_range_image])
                #r = results[0]
                #print (r['class_ids'])

                self.bu_model.analyze_image([test_range_image])
                self.BUModeProgressbar.set_limit_object(self.bu_model)
                self.BUModeProgressbar.showProgressbar()
                self.BUModeProgressbar.finished_notify.connect(self.ai_anaylize_completed)

                #t = threading.Thread(target=self.initial_job, args=(Null, test_range_image))
                #t.setDaemon(True)
                #t.start()
                self.canvas.saveSelectedShape(test_range_image)

        except Exception as e:
            print(str(e))
        finally:
            #self.populateModeActions()
            print('end toAIPredict')

    # add by yuan ==> add region when user cancel select
    def toggleDrawingSensitive(self, drawing=True):
        """In the middle of drawing, toggling between modes should be disabled."""
        self.actions.editMode.setEnabled(not drawing)
        if not drawing and self.beginner():
            # Cancel creation.
            print('Cancel creation.')
            self.canvas.setEditing(True)
            self.canvas.restoreCursor()
            self.actions.create.setEnabled(True)
            self.actions.region.setEnabled(True)

    def toggleDrawMode(self, edit=True):
        #self.canvas.setEditing(edit)
        self.actions.createMode.setEnabled(edit)
        self.actions.editMode.setEnabled(not edit)

    def setDisplayRect(self):
        self.actions.DispRect.setEnabled(False)
        self.actions.DispAxis.setEnabled(True)
        self.canvas.setSelectDisplay(0x02)
        #assert self.advanced()
        #self.toggleDrawMode(False)

    def setDisplayAxis(self):
        self.actions.DispRect.setEnabled(True)
        self.actions.DispAxis.setEnabled(False)
        self.canvas.setSelectDisplay(0x01)

    def setCreateMode(self):
        assert self.advanced()
        self.toggleDrawMode(False)

    def setEditMode(self):
        assert self.advanced()
        self.toggleDrawMode(True)
        self.labelSelectionChanged()

    def updateFileMenu(self):
        currFilePath = self.filePath

        def exists(filename):
            return os.path.exists(filename)
        """ mark by yuan
        menu = self.menus.recentFiles
        menu.clear()
        files = [f for f in self.recentFiles if f !=
                 currFilePath and exists(f)]
        for i, f in enumerate(files):
            icon = newIcon('labels')
            action = QAction(
                icon, '&%d %s' % (i + 1, QFileInfo(f).fileName()), self)
            action.triggered.connect(partial(self.loadRecent, f))
            menu.addAction(action)
        """

    def popLabelListMenu(self, point):
        self.menus.labelList.exec_(self.labelList.mapToGlobal(point))

    """
    def editLabel(self):
        #if not self.canvas.editing():
        #    return        
        item = self.currentItem()
        text = self.labelDialog.popUp(item.text())
        if text is not None:
            item.setText(text)
            item.setBackground(generateColorByText(text))
            self.setDirty()
    """

    # Tzutalin 20160906 : Add file list and dock to move faster
    def fileitemDoubleClicked(self, item=None):
        currIndex = self.mImgList.index(ustr(item.text()))
        if currIndex < len(self.mImgList):
            filename = self.mImgList[currIndex]
            if filename:
                self.loadFile(filename)

    # Add chris
    def btnstate(self, item= None):
        """ Function to handle difficult examples
        Update on each object """
        # if not self.canvas.editing():
        #    return

        item = self.currentItem()
        if not item: # If not selected Item, take the first one
            item = self.labelList.item(self.labelList.count()-1)

        # difficult = self.diffcButton.isChecked()

        try:
            shape = self.itemsToShapes[item]
        except:
            pass

        # Checked and Update
        """
        try:
            if difficult != shape.difficult:
                shape.difficult = difficult
                self.setDirty()
            else:  # User probably changed item visibility
                self.canvas.setShapeVisible(shape, item.checkState() == Qt.Checked)
        except:
            pass
        """

    # React to canvas signals.
    # yuan: change exist rect size event
    def shapeSelectionChanged(self, selected=False):
        #if self._noSelectionSlot:
        #    self._noSelectionSlot = False
        #else:
        #    shape = self.canvas.selectedShape
            #if shape:
            #    self.shapesToItems[shape].setSelected(True)
            #else:
            #    self.labelList.clearSelection()
        if selected:
            info_list = self.canvas.get_selected_shape_information()
            self.initial_property_table(info_list)
        else:
            self.initial_property_table(None)

        if self.canvas.selectedShape is not None:
            self.actions.delete.setEnabled(selected)
        else:
            self.actions.delete.setEnabled(False)


        #self.actions.copy.setEnabled(selected)
        #self.actions.edit.setEnabled(selected)
        #self.actions.shapeLineColor.setEnabled(selected)
        #self.actions.shapeFillColor.setEnabled(selected)
        #self.actions.splitimg.setEnabled(selected)

    # yuan: when user select area and write label after generate event
    def addLabel(self, shape):
        shape.paintLabel = self.displayLabelOption.isChecked()
        item = HashableQListWidgetItem(shape.label)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)

        if not shape.label is None:
            item.setBackground(generateColorByText(shape.label))

        self.itemsToShapes[item] = shape
        self.shapesToItems[shape] = item
        self.labelList.addItem(item)
        for action in self.actions.onShapesPresent:
            action.setEnabled(True)

    def remLabel(self, shape):
        if shape is None:
            # print('rm empty label')
            return
        item = self.shapesToItems[shape]
        self.labelList.takeItem(self.labelList.row(item))
        del self.shapesToItems[shape]
        del self.itemsToShapes[item]

    """
    def loadRegionType(self, shape_list, rect_list, region_type):
        
       # line_color = QColor(204, 255, 204)
       if region_type == 0x02:   #tissue        
       #     line_color = QColor(255, 204, 204)

        for rect in rect_list:
            shape = DetectedShape ()         
            shape.addPoint(QPointF(rect[0][0], rect[0][1]))
            shape.addPoint(QPointF(rect[0][0], rect[1][1]))
            shape.addPoint(QPointF(rect[1][0], rect[1][1]))
            shape.addPoint(QPointF(rect[1][0], rect[0][1]))
            shape.addPoint(QPointF(rect[0][0], rect[0][1]))
            shape.close()
            shape_list.append(shape)
    """

    def loadLabels(self, shapes):
        s = []
        for label, points, line_color, fill_color, difficult in shapes:
            shape = Shape(label=label)
            for x, y in points:
                shape.addPoint(QPointF(x, y))
            shape.difficult = difficult
            shape.close()
            s.append(shape)

            if line_color:
                shape.line_color = QColor(*line_color)
            else:
                shape.line_color = generateColorByText(label)

            if fill_color:
                shape.fill_color = QColor(*fill_color)
            else:
                shape.fill_color = generateColorByText(label)

            self.addLabel(shape)

        self.canvas.loadShapes(s)

    # add by yuan ==>
    def loadLabelsWithRegion(self, shapes):
        s = []
        for label, points in shapes:
            shape = Shape(label=label)

            for x, y in points:
                shape.addPoint(QPointF(x, y))

            shape.close()
            s.append(shape)

            self.addLabel(shape)

        self.canvas.loadShapes(s)

    def saveLabels(self, annotationFilePath):
        annotationFilePath = ustr(annotationFilePath)
        if self.labelFile is None:
            self.labelFile = LabelFile()
            self.labelFile.verified = self.canvas.verified

        def format_shape(s):
            return dict(label=s.label,
                        line_color=s.line_color.getRgb(),
                        fill_color=s.fill_color.getRgb(),
                        points=[(p.x(), p.y()) for p in s.points],
                       # add chris
                        difficult = s.difficult,
                        # add yuan
                        drawRegion = s.drawRegion)

        shapes = [format_shape(shape) for shape in self.canvas.shapes]
        # Can add differrent annotation formats here
        try:
            if annotationFilePath[-4:].lower() != ".xml":
                annotationFilePath += XML_EXT
            self.labelFile.savePascalVrcFormat(annotationFilePath, shapes, self.filePath, self.imageData,
                                               self.lineColor.getRgb(), self.fillColor.getRgb())

            print('Image:{0} -> Annotation:{1}'.format(self.filePath, annotationFilePath))
            return True
        except LabelFileError as e:
            self.errorMessage(u'Error saving label data', u'<b>%s</b>' % e)
            return False

    def copySelectedShape(self):
        self.addLabel(self.canvas.copySelectedShape())
        # fix copy and delete
        self.shapeSelectionChanged(True)

    # yuan: select exist rect event - 1
    def labelSelectionChanged(self):
        item = self.currentItem()
        """
        if item and self.canvas.editing():
            self._noSelectionSlot = True
            self.canvas.selectShape(self.itemsToShapes[item])
            shape = self.itemsToShapes[item]
            # Add Chris
            self.diffcButton.setChecked(shape.difficult)
        """

    def labelItemChanged(self, item):
        shape = self.itemsToShapes[item]
        label = item.text()
        if label != shape.label:
            shape.label = item.text()
            shape.line_color = generateColorByText(shape.label)
            self.setDirty()
        else:  # User probably changed item visibility
            self.canvas.setShapeVisible(shape, item.checkState() == Qt.Checked)

    # Callback functions:
    # add by yun ==> if use draw shape event when mouse left release
    def newShape(self):
        """Pop-up and give focus to the label editor.

        position MUST be in global coordinates.
        """
        if not self.useDefaultLabelCheckbox.isChecked() or not self.defaultLabelTextLine.text():
            if len(self.labelHist) > 0:
                self.labelDialog = LabelDialog(
                    parent=self, listItem=self.labelHist)

            # Sync single class mode from PR#106
            if self.singleClassMode.isChecked() and self.lastLabel:
                text = self.lastLabel
            else:
                text = self.labelDialog.popUp(text=self.prevLabelText)
                self.lastLabel = text
        else:
            text = self.defaultLabelTextLine.text()

        # Add Chris
        # add by yuan ==> enable region button
        self.diffcButton.setChecked(False)
        if text is not None:
            self.prevLabelText = text
            generate_color = generateColorByText(text)
            shape = self.canvas.setLastLabel(text, generate_color, generate_color)
            self.addLabel(shape)
            if self.beginner():  # Switch to edit mode.
                self.canvas.setEditing(True)
                self.actions.create.setEnabled(True)
                self.actions.region.setEnabled(True)
            else:
                self.actions.editMode.setEnabled(True)
            self.setDirty()

            if text not in self.labelHist:
                self.labelHist.append(text)
        else:
            # self.canvas.undoLastLine()
            self.canvas.resetAllLines()

    def scrollRequest(self, delta, orientation):
        units = - delta / (8 * 15)
        bar = self.scrollBars[orientation]
        bar.setValue(bar.value() + bar.singleStep() * units)

    def setZoom(self, value):
        self.actions.fitWidth.setChecked(False)
        self.actions.fitWindow.setChecked(False)
        self.zoomMode = self.MANUAL_ZOOM
        self.zoomWidget.setValue(value)

    def addZoom(self, increment=10):
        self.setZoom(self.zoomWidget.value() + increment)

    def zoomRequest(self, delta):
        # get the current scrollbar positions
        # calculate the percentages ~ coordinates
        h_bar = self.scrollBars[Qt.Horizontal]
        v_bar = self.scrollBars[Qt.Vertical]

        # get the current maximum, to know the difference after zooming
        h_bar_max = h_bar.maximum()
        v_bar_max = v_bar.maximum()

        # get the cursor position and canvas size
        # calculate the desired movement from 0 to 1
        # where 0 = move left
        #       1 = move right
        # up and down analogous
        cursor = QCursor()
        pos = cursor.pos()
        relative_pos = QWidget.mapFromGlobal(self, pos)

        cursor_x = relative_pos.x()
        cursor_y = relative_pos.y()

        w = self.scrollArea.width()
        h = self.scrollArea.height()

        # the scaling from 0 to 1 has some padding
        # you don't have to hit the very leftmost pixel for a maximum-left movement
        margin = 0.1
        move_x = (cursor_x - margin * w) / (w - 2 * margin * w)
        move_y = (cursor_y - margin * h) / (h - 2 * margin * h)

        # clamp the values from 0 to 1
        move_x = min(max(move_x, 0), 1)
        move_y = min(max(move_y, 0), 1)

        # zoom in
        units = delta / (8 * 15)
        scale = 10
        self.addZoom(scale * units)

        # get the difference in scrollbar values
        # this is how far we can move
        d_h_bar_max = h_bar.maximum() - h_bar_max
        d_v_bar_max = v_bar.maximum() - v_bar_max

        # get the new scrollbar values
        new_h_bar_value = h_bar.value() + move_x * d_h_bar_max
        new_v_bar_value = v_bar.value() + move_y * d_v_bar_max

        h_bar.setValue(new_h_bar_value)
        v_bar.setValue(new_v_bar_value)

    def setFitWindow(self, value=True):
        if value:
            self.actions.fitWidth.setChecked(False)
        self.zoomMode = self.FIT_WINDOW if value else self.MANUAL_ZOOM
        self.adjustScale()

    def setFitWidth(self, value=True):
        if value:
            self.actions.fitWindow.setChecked(False)
        self.zoomMode = self.FIT_WIDTH if value else self.MANUAL_ZOOM
        self.adjustScale()

    def togglePolygons(self, value):
        for item, shape in self.itemsToShapes.items():
            item.setCheckState(Qt.Checked if value else Qt.Unchecked)

    def loadFile(self, filePath=None):
        """Load the specified file, or the last opened file if None."""
        self.resetState()
        self.canvas.setEnabled(False)
        if filePath is None:
            filePath = self.settings.get(SETTING_FILENAME)

        # Make sure that filePath is a regular python string, rather than QString
        filePath = ustr(filePath)

        unicodeFilePath = ustr(filePath)
        # Tzutalin 20160906 : Add file list and dock to move faster
        # Highlight the file item
        """
        if unicodeFilePath and self.fileListWidget.count() > 0:
            index = self.mImgList.index(unicodeFilePath)
            fileWidgetItem = self.fileListWidget.item(index)
            fileWidgetItem.setSelected(True)
        """

        if unicodeFilePath and os.path.exists(unicodeFilePath):
            """
            if LabelFile.isLabelFile(unicodeFilePath):
                try:
                    self.labelFile = LabelFile(unicodeFilePath)
                except LabelFileError as e:
                    self.errorMessage(u'Error opening file',
                                      (u"<p><b>%s</b></p>"
                                       u"<p>Make sure <i>%s</i> is a valid label file.")
                                      % (e, unicodeFilePath))
                    self.status("Error reading %s" % unicodeFilePath)
                    return False
                self.imageData = self.labelFile.imageData
                self.lineColor = QColor(*self.labelFile.lineColor)
                self.fillColor = QColor(*self.labelFile.fillColor)
                self.canvas.verified = self.labelFile.verified
            else:
            """

            # Load image:
            # read data first and store for saving into label file.
            self.imageData = read(unicodeFilePath, None)
            self.labelFile = None
            #self.canvas.verified = False

            image = QImage.fromData(self.imageData)
            if image.isNull():
                self.errorMessage(u'Error opening file',
                                  u"<p>Make sure <i>%s</i> is a valid image file." % unicodeFilePath)
                self.status("Error reading %s" % unicodeFilePath)
                return False
            self.status("Loaded %s" % os.path.basename(unicodeFilePath))
            self.image = image
            self.filePath = unicodeFilePath
            self.canvas.loadPixmap(QPixmap.fromImage(image))
            if self.labelFile:
                self.loadLabels(self.labelFile.shapes)

            if not self.filePath is None:
                filename = os.path.basename(self.filePath)
                self.canvas.fileName = os.path.splitext(filename)[0]

            self.initial_property_table(None)
            self.setClean()
            self.canvas.setEnabled(True)
            self.adjustScale(initial=True)
            self.paintCanvas()
            self.addRecentFile(self.filePath)
            self.toggleActions(True)

            # Label xml file and show bound box according to its filename
            # if self.usingPascalVocFormat is True:
            """
            if self.defaultSaveDir is not None:
                basename = os.path.basename(
                    os.path.splitext(self.filePath)[0])
                xmlPath = os.path.join(self.defaultSaveDir, basename + XML_EXT)
                txtPath = os.path.join(self.defaultSaveDir, basename + TXT_EXT)

              
                if os.path.isfile(xmlPath):
                    self.loadPascalXMLByFilename(xmlPath)
                
            else:
                xmlPath = os.path.splitext(filePath)[0] + XML_EXT
                txtPath = os.path.splitext(filePath)[0] + TXT_EXT
                if os.path.isfile(xmlPath):
                    self.loadPascalXMLByFilename(xmlPath)
                #elif os.path.isfile(txtPath):
                #    self.loadYOLOTXTByFilename(txtPath)
            """

            self.setWindowTitle(__appname__ + ' ' + filePath)

            # Default : select last item if there is at least one item
            """
            if self.labelList.count():
                self.labelList.setCurrentItem(self.labelList.item(self.labelList.count()-1))
                self.labelList.item(self.labelList.count()-1).setSelected(True)
            """
            self.canvas.setFocus(True)
            return True
        return False
        # add by yuan

    def loadDCMFile(self, filename):
        if filename is None:
           return

        if os.path.isfile(filename) is False:
            return

        self.resetState()
        self.canvas.setEnabled(False)

        # Make sure that filePath is a regular python string, rather than QString
        filePath = ustr(filename)

        unicodeFilePath = ustr(filePath)

        us_dicom = USDicom.USDicomClass(filename, False)
        #element_list = []
        #us_dicom.readDataset(element_list)
       # for i, items in enumerate(element_list):
       #     if str(items[0]) != '(7fe0, 0010)':
       #         print(items)

        self.imageData = us_dicom.getImages()
        self.labelFile = None
        self.canvas.verified = False

        image = convertqtimage.ConvertQImage.numpy2qimage(self.imageData)

        if image.isNull():
            self.errorMessage(u'Error opening file',
                              u"<p>Make sure <i>%s</i> is a valid image file." % unicodeFilePath)
            self.status("Error reading %s" % unicodeFilePath)
            return False
        self.status("Loaded %s" % os.path.basename(unicodeFilePath))
        self.image = image
        self.filePath = unicodeFilePath
        self.canvas.loadPixmap(QPixmap.fromImage(image))

        shape_list = []
        tissue_box_list = us_dicom.getRegionBox(0x01)  # tissue
        rect_box_list = us_dicom.getRegionBox(0x02)  # color
        property_list = us_dicom.getPrivateCreator()

        # load rectangle
        for index,  tissue in enumerate(tissue_box_list):
            detect_shape = DetectedShape()
            detect_shape.set_tissue_rect_by_dicom(tissue)
            detect_shape.set_roi_point_by_dicom(rect_box_list[index])
            detect_shape.set_roi_property_by_dicom(property_list[index])
            shape_list.append(detect_shape)

        shape_list[0].selected = False
        shape_list[0].select_roi = 0
        shape_list[0].SelectedDisplay = DetectedShape.DISPLAY_AXIS

        #if self.labelFile:
        # self.loadLabels(self.labelFile.shapes)
        self.canvas.loadShapes(shape_list)
        if not self.filePath is None:
            filename = os.path.basename(self.filePath)
            self.canvas.fileName = os.path.splitext(filename)[0]

        self.setClean()
        self.canvas.setEnabled(True)
        self.adjustScale(initial=True)
        self.paintCanvas()
        self.addRecentFile(self.filePath)
        self.toggleActions(True)
        self.setWindowTitle(__appname__ + ' ' + filePath)
        self.canvas.setFocus(True)
        self.canvas.focusShape(0)


    def resizeEvent(self, event):
        if self.canvas and not self.image.isNull()\
           and self.zoomMode != self.MANUAL_ZOOM:
            self.adjustScale()
        super(MainWindow, self).resizeEvent(event)

    def paintCanvas(self):
        assert not self.image.isNull(), "cannot paint null image"
        self.canvas.scale = 0.01 * self.zoomWidget.value()
        self.canvas.adjustSize()
        self.canvas.update()

    def adjustScale(self, initial=False):
        value = self.scalers[self.FIT_WINDOW if initial else self.zoomMode]()
        self.zoomWidget.setValue(int(100 * value))

    def scaleFitWindow(self):
        """Figure out the size of the pixmap in order to fit the main widget."""
        e = 2.0  # So that no scrollbars are generated.
        w1 = self.centralWidget().width() - e
        h1 = self.centralWidget().height() - e
        a1 = w1 / h1
        # Calculate a new scale value based on the pixmap's aspect ratio.
        w2 = self.canvas.pixmap.width() - 0.0
        h2 = self.canvas.pixmap.height() - 0.0
        a2 = w2 / h2
        return w1 / w2 if a2 >= a1 else h1 / h2

    def scaleFitWidth(self):
        # The epsilon does not seem to work too well here.
        w = self.centralWidget().width() - 2.0
        return w / self.canvas.pixmap.width()

    def closeEvent(self, event):
        if not self.mayContinue():
            event.ignore()
        settings = self.settings
        # If it loads images from dir, don't load it at the begining
        if self.dirname is None:
            settings[SETTING_FILENAME] = self.filePath if self.filePath else ''
        else:
            settings[SETTING_FILENAME] = ''

        settings[SETTING_WIN_SIZE] = self.size()
        settings[SETTING_WIN_POSE] = self.pos()
        settings[SETTING_WIN_STATE] = self.saveState()
        settings[SETTING_LINE_COLOR] = self.lineColor
        settings[SETTING_FILL_COLOR] = self.fillColor
        settings[SETTING_RECENT_FILES] = self.recentFiles
        settings[SETTING_ADVANCE_MODE] = not self._beginner
        if self.defaultSaveDir and os.path.exists(self.defaultSaveDir):
            settings[SETTING_SAVE_DIR] = ustr(self.defaultSaveDir)
        else:
            settings[SETTING_SAVE_DIR] = ''

        if self.lastOpenDir and os.path.exists(self.lastOpenDir):
            settings[SETTING_LAST_OPEN_DIR] = self.lastOpenDir
        else:
            settings[SETTING_LAST_OPEN_DIR] = ''

        settings[SETTING_AUTO_SAVE] = self.autoSaving.isChecked()
        settings[SETTING_SINGLE_CLASS] = self.singleClassMode.isChecked()
        settings[SETTING_PAINT_LABEL] = self.displayLabelOption.isChecked()
        settings[SETTING_DRAW_SQUARE] = self.drawSquaresOption.isChecked()
        settings.save()

    def loadRecent(self, filename):
        if self.mayContinue():
            self.loadFile(filename)

    def scanAllImages(self, folderPath):
        extensions = ['.%s' % fmt.data().decode("ascii").lower() for fmt in QImageReader.supportedImageFormats()]
        images = []

        for root, dirs, files in os.walk(folderPath):
            for file in files:
                if file.lower().endswith(tuple(extensions)):
                    relativePath = os.path.join(root, file)
                    path = ustr(os.path.abspath(relativePath))
                    images.append(path)
        images.sort(key=lambda x: x.lower())
        return images

    def changeSavedirDialog(self, _value=False):
        if self.defaultSaveDir is not None:
            path = ustr(self.defaultSaveDir)
        else:
            path = '.'

        dirpath = ustr(QFileDialog.getExistingDirectory(self,
                                                       '%s - Save annotations to the directory' % __appname__, path,  QFileDialog.ShowDirsOnly
                                                       | QFileDialog.DontResolveSymlinks))

        if dirpath is not None and len(dirpath) > 1:
            self.defaultSaveDir = dirpath

        self.statusBar().showMessage('%s . Annotation will be saved to %s' %
                                     ('Change saved folder', self.defaultSaveDir))
        self.statusBar().show()

    """
    def openAnnotationDialog(self, _value=False):
        if self.filePath is None:
            self.statusBar().showMessage('Please select image first')
            self.statusBar().show()
            return

        path = os.path.dirname(ustr(self.filePath))\
            if self.filePath else '.'
        if self.usingPascalVocFormat:
            filters = "Open Annotation XML file (%s)" % ' '.join(['*.xml'])
            filename = ustr(QFileDialog.getOpenFileName(self,'%s - Choose a xml file' % __appname__, path, filters))
            if filename:
                if isinstance(filename, (tuple, list)):
                    filename = filename[0]
            self.loadPascalXMLByFilename(filename)
    """

    def openDirDialog(self, _value=False, dirpath=None):
        if not self.mayContinue():
            return

        defaultOpenDirPath = dirpath if dirpath else '.'
        if self.lastOpenDir and os.path.exists(self.lastOpenDir):
            defaultOpenDirPath = self.lastOpenDir
        else:
            defaultOpenDirPath = os.path.dirname(self.filePath) if self.filePath else '.'

        targetDirPath = ustr(QFileDialog.getExistingDirectory(self,
                                                     '%s - Open Directory' % __appname__, defaultOpenDirPath,
                                                     QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks))
        self.importDirImages(targetDirPath)

    def importDirImages(self, dirpath):
        if not self.mayContinue() or not dirpath:
            return

        self.lastOpenDir = dirpath
        self.dirname = dirpath
        self.filePath = None
        self.fileListWidget.clear()
        self.mImgList = self.scanAllImages(dirpath)
        self.openNextImg()
        for imgPath in self.mImgList:
            item = QListWidgetItem(imgPath)
            self.fileListWidget.addItem(item)

    """
    def verifyImg(self, _value=False):
        # Proceding next image without dialog if having any label
        if self.filePath is not None:
            try:
                self.labelFile.toggleVerify()
            except AttributeError:
                # If the labelling file does not exist yet, create if and
                # re-save it with the verified attribute.
                self.saveFile()
                if self.labelFile != None:
                    self.labelFile.toggleVerify()
                else:
                    return

            self.canvas.verified = self.labelFile.verified
            self.paintCanvas()
            self.saveFile()
    """

    def openPrevImg(self, _value=False):
        # Proceding prev image without dialog if having any label
        if self.autoSaving.isChecked():
            if self.defaultSaveDir is not None:
                if self.dirty is True:
                    self.saveFile()
            else:
                self.changeSavedirDialog()
                return

        if not self.mayContinue():
            return

        if len(self.mImgList) <= 0:
            return

        if self.filePath is None:
            return

        currIndex = self.mImgList.index(self.filePath)
        if currIndex - 1 >= 0:
            filename = self.mImgList[currIndex - 1]
            if filename:
                self.loadFile(filename)

    def openNextImg(self, _value=False):
        # Proceding prev image without dialog if having any label
        if self.autoSaving.isChecked():
            if self.defaultSaveDir is not None:
                if self.dirty is True:
                    self.saveFile()
            else:
                self.changeSavedirDialog()
                return

        if not self.mayContinue():
            return

        if len(self.mImgList) <= 0:
            return

        filename = None
        if self.filePath is None:
            filename = self.mImgList[0]
        else:
            currIndex = self.mImgList.index(self.filePath)
            if currIndex + 1 < len(self.mImgList):
                filename = self.mImgList[currIndex + 1]

        if filename:
            self.loadFile(filename)

    def openFile(self, _value=False):
        if not self.mayContinue():
            return
        path = os.path.dirname(ustr(self.filePath)) if self.filePath else '.'
        #formats = ['*.%s' % fmt.data().decode("ascii").lower() for fmt in QImageReader.supportedImageFormats()]
        #formats = ["*.jpg", "*.png", "*.jpeg"]
        filters = "Image & Label files (%s)" % ' '.join(["*.jpg", "*.png", "*.jpeg"]) # + ['*%s' % LabelFile.suffix])
        filters = filters + ";;DICOM files (%s)" % ' '.join(['*.dcm'])
        filename = QFileDialog.getOpenFileName(self, '%s - Choose Image or DICOM file' % __appname__, path, filters)
        if filename:
            if isinstance(filename, (tuple, list)):
                filename = filename[0]

            if str(filename).endswith((".jpg", ".png", ".jpeg")):
                self.loadFile(filename)
            elif str(filename).endswith((".dcm")):
                self.loadDCMFile(filename)

    # add by yuan
    def saveFile(self, _value=False):
        imgFileName = os.path.basename(self.filePath)
        savedFileName = os.path.splitext(imgFileName)[0]
        defaultSaveDir = os.path.dirname(self.filePath)
        savedPath = os.path.join(ustr(defaultSaveDir), savedFileName)
        self.saveAsDICOM()
        #self._saveFile(savedPath)

    # mark by yuan
    def saveFileAs(self, _value=False):
        assert not self.image.isNull(), "cannot save empty image"
        self._saveFile(self.saveFileDialog())

    def saveFileDialog(self, removeExt=True):
        caption = '%s - Choose File' % __appname__
        filters = 'File (*%s)' % LabelFile.suffix
        openDialogPath = self.currentPath()
        dlg = QFileDialog(self, caption, openDialogPath, filters)
        dlg.setDefaultSuffix(LabelFile.suffix[1:])
        dlg.setAcceptMode(QFileDialog.AcceptSave)
        filenameWithoutExtension = os.path.splitext(self.filePath)[0]
        dlg.selectFile(filenameWithoutExtension)
        dlg.setOption(QFileDialog.DontUseNativeDialog, False)
        if dlg.exec_():
            fullFilePath = ustr(dlg.selectedFiles()[0])
            if removeExt:
                return os.path.splitext(fullFilePath)[0] # Return file path without the extension.
            else:
                return fullFilePath
        return ''

    def _saveFile(self, annotationFilePath):
        if annotationFilePath and self.saveLabels(annotationFilePath):
            self.setClean()
            self.statusBar().showMessage('Saved to  %s' % annotationFilePath)
            self.statusBar().show()

    def closeFile(self, _value=False):
        if not self.mayContinue():
            return
        self.resetState()
        self.setClean()
        self.toggleActions(False)
        self.canvas.setEnabled(False)
        self.actions.saveAs.setEnabled(False)

    def resetAll(self):
        self.settings.reset()
        self.close()
        proc = QProcess()
        proc.startDetached(os.path.abspath(__file__))

    def mayContinue(self):
        return not (self.dirty and not self.discardChangesDialog())

    def discardChangesDialog(self):
        yes, no = QMessageBox.Yes, QMessageBox.No
        msg = u'You have unsaved changes, proceed anyway?'
        return yes == QMessageBox.warning(self, u'Attention', msg, yes | no)

    def errorMessage(self, title, message):
        return QMessageBox.critical(self, title,
                                    '<p><b>%s</b></p>%s' % (title, message))

    def currentPath(self):
        return os.path.dirname(self.filePath) if self.filePath else '.'

    def chooseColor1(self):
        color = self.colorDialog.getColor(self.lineColor, u'Choose line color',
                                          default=DEFAULT_LINE_COLOR)
        if color:
            self.lineColor = color
            Shape.line_color = color
            self.canvas.setDrawingColor(color)
            self.canvas.update()
            self.setDirty()

    def deleteSelectedShape(self):
        self.canvas.deleteSelected()
        self.initial_property_table(None)
        #self.remLabel(self.canvas.deleteSelected())
        self.setDirty()
        self.actions.delete.setEnabled(False)
        if self.noShapes():
            for action in self.actions.onShapesPresent:
                action.setEnabled(False)

    def chshapeLineColor(self):
        color = self.colorDialog.getColor(self.lineColor, u'Choose line color',
                                          default=DEFAULT_LINE_COLOR)
        if color:
            self.canvas.selectedShape.line_color = color
            self.canvas.update()
            self.setDirty()

    def chshapeFillColor(self):
        color = self.colorDialog.getColor(self.fillColor, u'Choose fill color',
                                          default=DEFAULT_FILL_COLOR)
        if color:
            self.canvas.selectedShape.fill_color = color
            self.canvas.update()
            self.setDirty()

    def loadPredefinedClasses(self, predefClassesFile):
        if os.path.exists(predefClassesFile) is True:
            with codecs.open(predefClassesFile, 'r', 'utf8') as f:
                for line in f:
                    line = line.strip()
                    if self.labelHist is None:
                        self.labelHist = [line]
                    else:
                        self.labelHist.append(line)


    def togglePaintLabelsOption(self):
        for shape in self.canvas.shapes:
            shape.paintLabel = self.displayLabelOption.isChecked()

    def toogleDrawSquare(self):
        self.canvas.setDrawingShapeToSquare(self.drawSquaresOption.isChecked())

def inverted(color):
    return QColor(*[255 - v for v in color.getRgb()])

def read(filename, default=None):
    try:
        with open(filename, 'rb') as f:
            return f.read()
    except:
        return default

def get_main_app(argv=[]):
    """
    Standard boilerplate Qt application code.
    Do everything but app.exec_() -- so that we can test the application in one thread
    """
    app = QApplication(argv)
    app.setApplicationName(__appname__)
    app.setWindowIcon(newIcon("app"))
    # Tzutalin 201705+: Accept extra agruments to change predefined class file
    # Usage : labelImg.py image predefClassFile saveDir
    win = MainWindow(argv[1] if len(argv) >= 2 else None,
                     argv[2] if len(argv) >= 3 else os.path.join(os.path.dirname(sys.argv[0]),\
                                                                 'data', 'predefined_classes.txt'),
                     argv[3] if len(argv) >= 4 else None)
    win.show()
    return app, win

def main():

    '''construct main app and run it'''
    app, _win = get_main_app(sys.argv)
    return app.exec_()

if __name__ == '__main__':
    sys.exit(main())





"""
    def copyShape(self):
        self.canvas.endMove(copy=True)
        self.addLabel(self.canvas.selectedShape)
        self.setDirty()

    def moveShape(self):
        self.canvas.endMove(copy=False)
        self.setDirty()

    def loadPascalXMLByFilename(self, xmlPath):
        if self.filePath is None:
            return
        if os.path.isfile(xmlPath) is False:
            return

        self.set_format(FORMAT_PASCALVRC)

        tVrcParseReader = PascalVrcReader(xmlPath)
        shapes = tVrcParseReader.getShapes()
        #self.loadLabels(shapes)
        self.loadLabelsWithRegion(shapes)
        self.canvas.verified = tVrcParseReader.verified

    def loadYOLOTXTByFilename(self, txtPath):
        if self.filePath is None:
            return
        if os.path.isfile(txtPath) is False:
            return

        self.set_format(FORMAT_YOLO)
        tYoloParseReader = YoloReader(txtPath, self.image)
        shapes = tYoloParseReader.getShapes()
        print (shapes)
        self.loadLabels(shapes)
        self.canvas.verified = tYoloParseReader.verified
"""
"""
   def saveFile(self, _value=False):
       if self.defaultSaveDir is not None and len(ustr(self.defaultSaveDir)):
           if self.filePath:
               imgFileName = os.path.basename(self.filePath)
               savedFileName = os.path.splitext(imgFileName)[0]
               savedPath = os.path.join(ustr(self.defaultSaveDir), savedFileName)
               self._saveFile(savedPath)
       else:
           imgFileDir = os.path.dirname(self.filePath)
           imgFileName = os.path.basename(self.filePath)
           savedFileName = os.path.splitext(imgFileName)[0]
           savedPath = os.path.join(imgFileDir, savedFileName)
           self._saveFile(savedPath if self.labelFile
                          else self.saveFileDialog(removeExt=False))
    # add by yuan ==> split image when user select shape
    def createsplitimg(self):
        try:
            print ('start to splil')
            self.canvas.saveSelectedShape()
            #time.sleep(5)
            print('end from splil')
        except:
            print ('catch error')
   
   """


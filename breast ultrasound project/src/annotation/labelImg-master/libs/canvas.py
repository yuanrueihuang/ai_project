
try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except ImportError:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

#from PyQt4.QtOpenGL import *

from libs.shape import Shape
from libs.lib import distance
import math
from time import strftime, gmtime
from os import path, mkdir
import numpy as np
import qimage2ndarray.qimageview_python as qp
import cv2
import matplotlib.pyplot as plt

CURSOR_DEFAULT = Qt.ArrowCursor
CURSOR_POINT = Qt.PointingHandCursor
CURSOR_DRAW = Qt.CrossCursor
CURSOR_MOVE = Qt.ClosedHandCursor
CURSOR_GRAB = Qt.OpenHandCursor

# class Canvas(QGLWidget):


class Canvas(QWidget):
    zoomRequest = pyqtSignal(int)
    scrollRequest = pyqtSignal(int, int)
    newShape = pyqtSignal()
    selectionChanged = pyqtSignal(bool)
    shapeMoved = pyqtSignal()
    drawingPolygon = pyqtSignal(bool)

    CREATE, EDIT = list(range(2))

    epsilon = 11.0

    FIXED_WIDTH = 192
    FIXED_HEIGHT = 192

    def __init__(self, *args, **kwargs):
        super(Canvas, self).__init__(*args, **kwargs)
        # Initialise local state.
        self.mode = self.EDIT
        self.shapes = []
        self.current = None
        self.selectedShape = None  # save the selected shape here
        self.selectedShapeCopy = None
        self.drawingLineColor = QColor(0, 0, 255)
        self.drawingRectColor = QColor(0, 0, 255) 
        self.line = Shape(line_color=self.drawingLineColor)
        self.prevPoint = QPointF()
        self.offsets = QPointF(), QPointF()
        self.scale = 1.0
        self.pixmap = QPixmap()
        self.visible = {}
        self._hideBackround = False
        self.hideBackround = False
        self.hShape = None
        self.hVertex = None
        self._painter = QPainter()
        self._cursor = CURSOR_DEFAULT
        # Menus:
        self.menus = (QMenu(), QMenu())
        # Set widget options.
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.WheelFocus)
        self.verified = False
        self.drawSquare = False
        self.drawRegion = True # Add by yuan : set drawRegion flag to true
        self.fileName = 'unknow'

    def setDrawingColor(self, qColor):
        self.drawingLineColor = qColor
        self.drawingRectColor = qColor

    def enterEvent(self, ev):
        self.overrideCursor(self._cursor)

    def leaveEvent(self, ev):
        self.restoreCursor()

    def focusOutEvent(self, ev):
        self.restoreCursor()

    def isVisible(self, shape):
        return self.visible.get(shape, True)

    def drawing(self):
        return self.mode == self.CREATE

    def editing(self):
        return self.mode == self.EDIT

    def setEditing(self, value=True):
        self.mode = self.EDIT if value else self.CREATE
        if not value:  # Create
            self.unHighlight()
            self.deSelectShape()
        self.prevPoint = QPointF()
        self.repaint()

    def unHighlight(self):
        if self.hShape:
            self.hShape.highlightClear()
        self.hVertex = self.hShape = None

    def selectedVertex(self):
        return self.hVertex is not None

    def mouseMoveEvent(self, ev):
        """Update line with last point and current coordinates."""
        pos = self.transformPos(ev.pos())

        # Update coordinates in status bar if image is opened
        window = self.parent().window()
        if window.filePath is not None:
            self.parent().window().labelCoordinates.setText(
                'X: %d; Y: %d' % (pos.x(), pos.y()))

        # Polygon drawing.
        if self.drawing():
            self.overrideCursor(CURSOR_DRAW)
            if self.current:
                color = self.drawingLineColor
                if self.outOfPixmap(pos):
                    # Don't allow the user to draw outside the pixmap.
                    # Project the point to the pixmap's edges.
                    pos = self.intersectionPoint(self.current[-1], pos)
                elif len(self.current) > 1 and self.closeEnough(pos, self.current[0]):
                    # Attract line to starting point and colorise to alert the
                    # user:
                    pos = self.current[0]
                    color = self.current.line_color
                    self.overrideCursor(CURSOR_POINT)
                    self.current.highlightVertex(0, Shape.NEAR_VERTEX)

                # add by yuan ==> draw region
                if self.drawRegion:
                    # pos_tmp添加到self.pos_xy中
                    # pos_tmp = (pos.x(),  pos.y())
                    if self.current:
                        self.current.addPoint(pos)
                        #self.line[1] = pos
                else:
                    if self.drawSquare:
                        initPos = self.current[0]
                        minX = initPos.x()
                        minY = initPos.y()
                        min_size = min(abs(pos.x() - minX), abs(pos.y() - minY))
                        directionX = -1 if pos.x() - minX < 0 else 1
                        directionY = -1 if pos.y() - minY < 0 else 1
                        self.line[1] = QPointF(minX + directionX * min_size, minY + directionY * min_size)
                    else:
                        self.line[1] = pos

                self.line.line_color = color
                self.prevPoint = QPointF()
                self.current.highlightClear()
            else:
                self.prevPoint = pos
            self.repaint()
            return

        # Polygon copy moving.
        if Qt.RightButton & ev.buttons():
            if self.selectedShapeCopy and self.prevPoint:
                self.overrideCursor(CURSOR_MOVE)
                self.boundedMoveShape(self.selectedShapeCopy, pos)
                self.repaint()
            elif self.selectedShape:
                self.selectedShapeCopy = self.selectedShape.copy()
                self.repaint()
            return

        # Polygon/Vertex moving.
        if Qt.LeftButton & ev.buttons():
            if self.selectedVertex():
                self.boundedMoveVertex(pos)
                self.shapeMoved.emit()
                self.repaint()
            elif self.selectedShape and self.prevPoint:
                self.overrideCursor(CURSOR_MOVE)
                self.boundedMoveShape(self.selectedShape, pos)
                self.shapeMoved.emit()
                self.repaint()
            return

        # Just hovering over the canvas, 2 posibilities:
        # - Highlight shapes
        # - Highlight vertex
        # Update shape/vertex fill and tooltip value accordingly.
        self.setToolTip("Image")
        for shape in reversed([s for s in self.shapes if self.isVisible(s)]):
            # Look for a nearby vertex to highlight. If that fails,
            # check if we happen to be inside a shape.
            index = shape.nearestVertex(pos, self.epsilon)
            if index is not None:
                if self.selectedVertex():
                    self.hShape.highlightClear()
                self.hVertex, self.hShape = index, shape
                shape.highlightVertex(index, shape.MOVE_VERTEX)
                self.overrideCursor(CURSOR_POINT)
                self.setToolTip("Click & drag to move point")
                self.setStatusTip(self.toolTip())
                self.update()
                break
            elif shape.containsPoint(pos):
                if self.selectedVertex():
                    self.hShape.highlightClear()
                self.hVertex, self.hShape = None, shape
                self.setToolTip(
                    "Click & drag to move shape '%s'" % shape.label)
                self.setStatusTip(self.toolTip())
                self.overrideCursor(CURSOR_GRAB)
                self.update()
                break
        else:  # Nothing found, clear highlights, reset state.
            if self.hShape:
                self.hShape.highlightClear()
                self.update()
            self.hVertex, self.hShape = None, None
            self.overrideCursor(CURSOR_DEFAULT)

    def mousePressEvent(self, ev):
        pos = self.transformPos(ev.pos())
        if self.drawRegion:
            # pos_tmp添加到self.pos_xy中
            if ev.button() == Qt.LeftButton:
                if self.drawing():
                    self.handleDrawing(pos)
                    #self.pos_xy.append(pos)
                else:
                    self.selectShapePoint(pos)
                    self.prevPoint = pos
                    self.repaint()
            elif ev.button() == Qt.RightButton and self.editing():
                self.selectShapePoint(pos)
                self.prevPoint = pos
                self.repaint()
        else:
            if ev.button() == Qt.LeftButton:
                if self.drawing():
                    self.handleDrawing(pos)
                else:
                    self.selectShapePoint(pos)
                    self.prevPoint = pos
                    self.repaint()
            elif ev.button() == Qt.RightButton and self.editing():
                self.selectShapePoint(pos)
                self.prevPoint = pos
                self.repaint()

    def mouseReleaseEvent(self, ev):
        if self.drawRegion:
            if ev.button() == Qt.RightButton:
                menu = self.menus[bool(self.selectedShapeCopy)]
                self.restoreCursor()
                if not menu.exec_(self.mapToGlobal(ev.pos())) \
                        and self.selectedShapeCopy:
                    # Cancel the move by deleting the shadow copy.
                    self.selectedShapeCopy = None
                    self.repaint()
            elif ev.button() == Qt.LeftButton and self.selectedShape:
                if self.selectedVertex():
                    self.overrideCursor(CURSOR_POINT)
                else:
                    self.overrideCursor(CURSOR_GRAB)
            elif ev.button() == Qt.LeftButton:
                pos = self.transformPos(ev.pos())
                if self.drawing():
                    self.handleDrawing(pos)
        else:
            if ev.button() == Qt.RightButton:
                menu = self.menus[bool(self.selectedShapeCopy)]
                self.restoreCursor()
                if not menu.exec_(self.mapToGlobal(ev.pos()))\
                    and self.selectedShapeCopy:
                    # Cancel the move by deleting the shadow copy.
                    self.selectedShapeCopy = None
                    self.repaint()
            elif ev.button() == Qt.LeftButton and self.selectedShape:
                if self.selectedVertex():
                    self.overrideCursor(CURSOR_POINT)
                else:
                    self.overrideCursor(CURSOR_GRAB)
            elif ev.button() == Qt.LeftButton:
                pos = self.transformPos(ev.pos())
                if self.drawing():
                    self.handleDrawing(pos)

    def endMove(self, copy=False):
        assert self.selectedShape and self.selectedShapeCopy
        shape = self.selectedShapeCopy
        #del shape.fill_color
        #del shape.line_color
        if copy:
            self.shapes.append(shape)
            self.selectedShape.selected = False
            self.selectedShape = shape
            self.repaint()
        else:
            self.selectedShape.points = [p for p in shape.points]
        self.selectedShapeCopy = None

    def hideBackroundShapes(self, value):
        self.hideBackround = value
        if self.selectedShape:
            # Only hide other shapes if there is a current selection.
            # Otherwise the user will not be able to select a shape.
            self.setHiding(True)
            self.repaint()

    def handleDrawing(self, pos):
        if self.drawRegion:
            if self.current:
                #initPos = self.current[0]
                self.current.addPoint(self.line[1])
                self.finalise_region()
            elif not self.outOfPixmap(pos):
                self.current = Shape(drawRegion=True)
                self.current.addPoint(pos)
                self.line.points = [pos, pos]
                self.setHiding()
                self.drawingPolygon.emit(True)
                self.update()
        else:
            if self.current and self.current.reachMaxPoints() is False:
                initPos = self.current[0]
                minX = initPos.x()
                minY = initPos.y()

                if Canvas.FIXED_HEIGHT == 0 and Canvas.FIXED_WIDTH ==0:
                    targetPos = self.line[1]
                    maxX = targetPos.x()
                    maxY = targetPos.y()
                else:
                    self.current.clearPoints()
                    orig_minX = minX
                    orig_minY = minY
                    minX = minX - Canvas.FIXED_WIDTH/2
                    minY = minY - Canvas.FIXED_HEIGHT/2
                    maxX = minX + Canvas.FIXED_WIDTH
                    maxY = minY + Canvas.FIXED_HEIGHT
                    # lef scale
                    if minX < 25:
                        maxX = maxX + (25 - minX)
                        minX = 25

                    if maxX > 740:
                        minX = minX - (maxX - 740)
                        maxX = 740

                    # top
                    if minY < 155:
                        maxY = maxY + (155 - minY)
                        minY = 155
                    #
                    if maxY > 540:
                        minY = minY - (maxY - 540)
                        maxY = 540

                    if orig_minX <= 378: # left image
                        if minY <= 200 and maxX > 310: #avoid color bar
                            if orig_minY < 200:
                                minX = minX - (maxX - 310)
                                maxX = 310
                            else:
                                minX = minX - (maxX - 378)
                                maxX = 378
                                maxY = maxY - (minY - 200)
                                minY = 200
                        elif maxX > 378:
                            minX = minX - (maxX - 378)
                            maxX = 378
                    else:  # right image
                        if minY <= 200 and maxX > 690:  # avoid color bar
                            if orig_minY < 200:
                                minX = minX - (maxX - 690)
                                maxX = 690
                            else:
                                minX = minX - (maxX - 740)
                                maxX = 740
                                maxY = maxY - (minY - 192)
                                minY = 200
                        else:
                            if maxX > 740:
                                minX = minX - (maxX - 740)
                                maxX = 740

                            if minX < 378:
                                maxX = maxX + (378 - minX )
                                minX = 378

                            if minY < 170:
                                maxY = maxY + (170 - minY)
                                minY = 170

                    self.current.addPoint(QPointF(minX, minY))
                    targetPos = QPointF(maxX, maxY)
                    self.line[1] = targetPos

                self.current.addPoint(QPointF(maxX, minY))
                self.current.addPoint(targetPos)
                self.current.addPoint(QPointF(minX, maxY))
                self.finalise()
            elif not self.outOfPixmap(pos):
                self.current = Shape()
                self.current.addPoint(pos)
                self.line.points = [pos, pos]
                self.setHiding()
                self.drawingPolygon.emit(True)
                self.update()

    def setHiding(self, enable=True):
        self._hideBackround = self.hideBackround if enable else False

    def canCloseShape(self):
        return self.drawing() and self.current and len(self.current) > 2

    def mouseDoubleClickEvent(self, ev):
        # We need at least 4 points here, since the mousePress handler
        # adds an extra one before this handler is called.
        if self.canCloseShape() and len(self.current) > 3:
            self.current.popPoint()
            self.finalise()

    def selectShape(self, shape):
        self.deSelectShape()
        shape.selected = True
        self.drawRegion = shape.drawRegion # add by yuan
        self.selectedShape = shape
        self.setHiding()
        self.selectionChanged.emit(True)
        self.update()

    def selectShapePoint(self, point):
        """Select the first shape created which contains this point."""
        self.deSelectShape()
        if self.selectedVertex():  # A vertex is marked for selection.
            index, shape = self.hVertex, self.hShape
            shape.highlightVertex(index, shape.MOVE_VERTEX)
            self.selectShape(shape)
            return
        for shape in reversed(self.shapes):
           # if not shape.drawRegion:
                if self.isVisible(shape) and shape.containsPoint(point):
                    self.selectShape(shape)
                    self.calculateOffsets(shape, point)
                    return

    def calculateOffsets(self, shape, point):
        rect = shape.boundingRect()
        x1 = rect.x() - point.x()
        y1 = rect.y() - point.y()
        x2 = (rect.x() + rect.width()) - point.x()
        y2 = (rect.y() + rect.height()) - point.y()
        self.offsets = QPointF(x1, y1), QPointF(x2, y2)

    def boundedMoveVertex(self, pos):
        index, shape = self.hVertex, self.hShape
        point = shape[index]
        if self.outOfPixmap(pos):
            pos = self.intersectionPoint(point, pos)

        if self.drawSquare:
            opposite_point_index = (index + 2) % 4
            opposite_point = shape[opposite_point_index]

            min_size = min(abs(pos.x() - opposite_point.x()), abs(pos.y() - opposite_point.y()))
            directionX = -1 if pos.x() - opposite_point.x() < 0 else 1
            directionY = -1 if pos.y() - opposite_point.y() < 0 else 1
            shiftPos = QPointF(opposite_point.x() + directionX * min_size - point.x(),
                               opposite_point.y() + directionY * min_size - point.y())
        else:
            shiftPos = pos - point

        shape.moveVertexBy(index, shiftPos)

        lindex = (index + 1) % 4
        rindex = (index + 3) % 4
        lshift = None
        rshift = None
        if index % 2 == 0:
            rshift = QPointF(shiftPos.x(), 0)
            lshift = QPointF(0, shiftPos.y())
        else:
            lshift = QPointF(shiftPos.x(), 0)
            rshift = QPointF(0, shiftPos.y())
        shape.moveVertexBy(rindex, rshift)
        shape.moveVertexBy(lindex, lshift)

    def boundedMoveShape(self, shape, pos):
        if self.outOfPixmap(pos):
            return False  # No need to move
        o1 = pos + self.offsets[0]
        if self.outOfPixmap(o1):
            pos -= QPointF(min(0, o1.x()), min(0, o1.y()))
        o2 = pos + self.offsets[1]
        if self.outOfPixmap(o2):
            pos += QPointF(min(0, self.pixmap.width() - o2.x()),
                           min(0, self.pixmap.height() - o2.y()))
        # The next line tracks the new position of the cursor
        # relative to the shape, but also results in making it
        # a bit "shaky" when nearing the border and allows it to
        # go outside of the shape's area for some reason. XXX
        #self.calculateOffsets(self.selectedShape, pos)
        dp = pos - self.prevPoint
        if dp:
            shape.moveBy(dp)
            self.prevPoint = pos
            return True
        return False

    def deSelectShape(self):
        if self.selectedShape:
            self.selectedShape.selected = False
            self.selectedShape = None
            self.setHiding(False)
            self.selectionChanged.emit(False)
            self.update()

    def deleteSelected(self):
        if self.selectedShape:
            shape = self.selectedShape
            self.shapes.remove(self.selectedShape)
            self.selectedShape = None
            self.update()
            return shape

    def copySelectedShape(self):
        if self.selectedShape:
            shape = self.selectedShape.copy()
            self.deSelectShape()
            self.shapes.append(shape)
            shape.selected = True
            self.selectedShape = shape
            self.boundedShiftShape(shape)
            return shape

    def boundedShiftShape(self, shape):
        # Try to move in one direction, and if it fails in another.
        # Give up if both fail.
        point = shape[0]
        offset = QPointF(2.0, 2.0)
        self.calculateOffsets(shape, point)
        self.prevPoint = point
        if not self.boundedMoveShape(shape, point - offset):
            self.boundedMoveShape(shape, point + offset)

    def paintEvent(self, event):
        if not self.pixmap:
            return super(Canvas, self).paintEvent(event)

        p = self._painter
        p.begin(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.HighQualityAntialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        p.scale(self.scale, self.scale)
        p.translate(self.offsetToCenter())
        p.drawPixmap(0, 0, self.pixmap)

        Shape.scale = self.scale
        for shape in self.shapes:
            if (shape.selected or not self._hideBackround) and self.isVisible(shape):
                shape.fill = shape.selected or shape == self.hShape
                shape.paint(p)

        # Paint rect
        # add by yuan ==> draw region
        if self.drawRegion:
            if self.current:
                self.current.paint(p)
        else:
            #Shape.scale = self.scale
            #for shape in self.shapes:
            #    if (shape.selected or not self._hideBackround) and self.isVisible(shape):
            #        shape.fill = shape.selected or shape == self.hShape
            #        shape.paint(p)

            if self.current:
                self.current.paint(p)
                self.line.paint(p)
            if self.selectedShapeCopy:
                self.selectedShapeCopy.paint(p)

            if self.current is not None and len(self.line) == 2:
                leftTop = self.line[0]
                rightBottom = self.line[1]
                rectWidth = rightBottom.x() - leftTop.x()
                rectHeight = rightBottom.y() - leftTop.y()
                p.setPen(self.drawingRectColor)
                brush = QBrush(Qt.BDiagPattern)
                p.setBrush(brush)
                p.drawRect(leftTop.x(), leftTop.y(), rectWidth, rectHeight)

            if self.drawing() and not self.prevPoint.isNull() and not self.outOfPixmap(self.prevPoint):
                p.setPen(QColor(0, 0, 0))
                p.drawLine(self.prevPoint.x(), 0, self.prevPoint.x(), self.pixmap.height())
                p.drawLine(0, self.prevPoint.y(), self.pixmap.width(), self.prevPoint.y())

            self.setAutoFillBackground(True)
            if self.verified:
                pal = self.palette()
                pal.setColor(self.backgroundRole(), QColor(184, 239, 38, 128))
                self.setPalette(pal)
            else:
                pal = self.palette()
                pal.setColor(self.backgroundRole(), QColor(232, 232, 232, 255))
                self.setPalette(pal)

        p.end()

    def transformPos(self, point):
        """Convert from widget-logical coordinates to painter-logical coordinates."""
        return point / self.scale - self.offsetToCenter()

    def offsetToCenter(self):
        s = self.scale
        area = super(Canvas, self).size()
        w, h = self.pixmap.width() * s, self.pixmap.height() * s
        aw, ah = area.width(), area.height()
        x = (aw - w) / (2 * s) if aw > w else 0
        y = (ah - h) / (2 * s) if ah > h else 0
        return QPointF(x, y)

    def outOfPixmap(self, p):
        w, h = self.pixmap.width(), self.pixmap.height()
        return not (0 <= p.x() <= w and 0 <= p.y() <= h)

    # add by yuan
    def finalise_region(self):
        assert self.current
        # first equlas last is closed region
        if len(self.current.points) >= 10:
            if self.current.points[0] == self.current.points[-1]:
                self.current.close()
                self.shapes.append(self.current)
                self.current = None
                self.setHiding(False)
                self.drawingPolygon.emit(False)
                self.newShape.emit()  # notify to create labedialog
                self.update()

    def finalise(self):
        assert self.current
        # first equlas last is closed region
        if self.current.points[0] == self.current.points[-1]:
            self.current = None
            self.drawingPolygon.emit(False)
            self.update()
            return

        self.current.close()
        self.shapes.append(self.current)
        self.current = None
        self.setHiding(False)
        self.newShape.emit() # notify to create labedialog
        self.update()

    def closeEnough(self, p1, p2):
        #d = distance(p1 - p2)
        #m = (p1-p2).manhattanLength()
        # print "d %.2f, m %d, %.2f" % (d, m, d - m)
        return distance(p1 - p2) < self.epsilon

    def intersectionPoint(self, p1, p2):
        # Cycle through each image edge in clockwise fashion,
        # and find the one intersecting the current line segment.
        # http://paulbourke.net/geometry/lineline2d/
        size = self.pixmap.size()
        points = [(0, 0),
                  (size.width(), 0),
                  (size.width(), size.height()),
                  (0, size.height())]
        x1, y1 = p1.x(), p1.y()
        x2, y2 = p2.x(), p2.y()
        d, i, (x, y) = min(self.intersectingEdges((x1, y1), (x2, y2), points))
        x3, y3 = points[i]
        x4, y4 = points[(i + 1) % 4]
        if (x, y) == (x1, y1):
            # Handle cases where previous point is on one of the edges.
            if x3 == x4:
                return QPointF(x3, min(max(0, y2), max(y3, y4)))
            else:  # y3 == y4
                return QPointF(min(max(0, x2), max(x3, x4)), y3)
        return QPointF(x, y)

    def intersectingEdges(self, x1y1, x2y2, points):
        """For each edge formed by `points', yield the intersection
        with the line segment `(x1,y1) - (x2,y2)`, if it exists.
        Also return the distance of `(x2,y2)' to the middle of the
        edge along with its index, so that the one closest can be chosen."""
        x1, y1 = x1y1
        x2, y2 = x2y2
        for i in range(4):
            x3, y3 = points[i]
            x4, y4 = points[(i + 1) % 4]
            denom = (y4 - y3) * (x2 - x1) - (x4 - x3) * (y2 - y1)
            nua = (x4 - x3) * (y1 - y3) - (y4 - y3) * (x1 - x3)
            nub = (x2 - x1) * (y1 - y3) - (y2 - y1) * (x1 - x3)
            if denom == 0:
                # This covers two cases:
                #   nua == nub == 0: Coincident
                #   otherwise: Parallel
                continue
            ua, ub = nua / denom, nub / denom
            if 0 <= ua <= 1 and 0 <= ub <= 1:
                x = x1 + ua * (x2 - x1)
                y = y1 + ua * (y2 - y1)
                m = QPointF((x3 + x4) / 2, (y3 + y4) / 2)
                d = distance(m - QPointF(x2, y2))
                yield d, i, (x, y)

    # add by yuan
    def covert2Rectangle(self, points):
        xmin = float('inf')
        ymin = float('inf')
        xmax = float('-inf')
        ymax = float('-inf')
        for p in points:
            x = p.x()
            y = p.y()
            xmin = min(x, xmin)
            ymin = min(y, ymin)
            xmax = max(x, xmax)
            ymax = max(y, ymax)

        # Martin Kersner, 2015/11/12
        # 0-valued coordinates of BB caused an error while
        # training faster-rcnn object detector.
        if xmin < 1:
            xmin = 1

        if ymin < 1:
            ymin = 1

        width = int(xmax - xmin)
        if width < 1:
            width = 1

        height = int(ymax-ymin)
        if height < 1:
            height = 1
        return (int(xmin), int(ymin), width, height)

    def storePoint(self, points):
        xmin = float('inf')
        ymin = float('inf')
        xmax = float('-inf')
        ymax = float('-inf')
        for p in points:
            x = p.x()
            y = p.y()
            xmin = min(x, xmin)
            ymin = min(y, ymin)
            xmax = max(x, xmax)
            ymax = max(y, ymax)

        # Martin Kersner, 2015/11/12
        # 0-valued coordinates of BB caused an error while
        # training faster-rcnn object detector.
        if xmin < 1:
            xmin = 1

        if ymin < 1:
            ymin = 1

        return (int(xmin), int(ymin), int(xmax), int(ymax))

    # add by yuan
    def saveSplitImage(self, shape, split_img, ismask, image_side ,serial_num):
        print("begin - saveSplitImage")
        label_name = 'unknow'
        if not shape.label is None:
            label_name = str(shape.label)

        #self.fileName
        if ismask:
            img_file = '{}_{}_{}_{}_mask.jpg'.format(label_name, self.fileName, image_side , serial_num)
        else:
            img_file = '{}_{}_{}_{}.jpg'.format(label_name,self.fileName, image_side, serial_num)

        img_path = path.abspath('breast dataset/train dataset')
        if not path.exists(img_path):
            mkdir(img_path)

        split_img.save(path.join(img_path, img_file), 'JPG', 100)

        print("end - saveSplitImage ")

    def saveSplitHSImage(self, shape, split_img, image_side, serial_num):
        print("begin - saveSplitHSImage")

        label_name = 'unknow'
        if not shape.label is None:
            label_name = str(shape.label)

        # self.fileName
        img_file = '{}_{}_{}_{}_HS.jpg'.format(label_name, self.fileName, image_side, serial_num)
        afimg_file = '{}_{}_{}_{}_after.jpg'.format(label_name, self.fileName, image_side, serial_num)
        beimg_file = '{}_{}_{}_{}_before.jpg'.format(label_name, self.fileName, image_side, serial_num)
        img_path = path.abspath('breast dataset/train HSdataset')
        if not path.exists(img_path):
            mkdir(img_path)

        splitimg = split_img.toImage()
        splitimg = splitimg.convertToFormat(QImage.Format_Grayscale8)
        splitimg = qp.qimageview(splitimg)
        splitimg = np.stack((splitimg,) * 3, axis=-1)

        #print (splitimg)
        min_gray = np.min(splitimg)
        max_gray = np.max(splitimg)
        # print (img[0][:10])
        print ('min:',min_gray,'max:', max_gray)
        x_axis = list(range(0, 255))
        #y_axis = splitimg.flatten().tolist()
        plt.figure()
        plt.hist(splitimg.flatten().tolist(), bins=x_axis)
        plt.title('Original Histogram - Min:{} Max:{}'.format(min_gray, max_gray))
        plt.savefig(path.join(img_path, beimg_file))

        scale = 255 / (max_gray - min_gray)
        print (scale)
        trasfor_img = (splitimg - min_gray)
        splitimg = trasfor_img * scale
        splitimg = splitimg.astype(int)

        #splitimg.save(path.join(img_path, img_file), 'JPG', 100)
        cv2.imwrite(path.join(img_path, img_file), splitimg, [cv2.IMWRITE_JPEG_QUALITY, 100])

        min_gray = np.min(splitimg)
        max_gray = np.max(splitimg)
        print('min:', min_gray, 'max:', max_gray)

        plt.figure()
        plt.hist(splitimg.flatten().tolist(), bins=x_axis)
        plt.title('Histogram Stretching - Min:{} Max:{}'.format(min_gray, max_gray) )
        plt.savefig(path.join(img_path, afimg_file))

        print("end - saveHSSplitImage ")


    def saveSelectedShape(self):
        print ('begin - saveSelectedShape')
        #select_shape =   self.selectedShape
        # the tiles are known to divide evenly
        # width = self.pixmap.width()  height = self.pixmap.height()
        str_time = strftime("%m%d%H%M%S", gmtime())

        shape = self.selectedShape
        imgside = 'right'

        if shape.drawRegion:
            print("start - saveRegionByOutsideRectangle")
            rect = self.storePoint(shape.points)
            rect = self.findFitRectangleShape(rect)
            split_img = self.pixmap.copy(rect[0], rect[1], rect[2], rect[3])

            if rect[0] < 380:
                imgside = 'left'

            self.saveSplitImage(shape, split_img, False, imgside, str_time)
            self.saveSplitHSImage(shape, split_img, imgside, str_time)
            self.saveRegionByOutsideRectangle(shape, rect, str_time)
            print("end - saveRegionByOutsideRectangle")
        else:
            print("start - findContainRegion")
            rect = self.covert2Rectangle(shape.points)
            split_img = self.pixmap.copy(rect[0], rect[1], rect[2], rect[3])

            if rect[0] < 380:
                imgside = 'left'

            self.saveSplitImage(shape, split_img, False, imgside, str_time)
            self.saveSplitHSImage(shape, split_img, imgside, str_time)
            self.findContainRegion(shape, rect, str_time)
            print("end - findContainRegion")

        QMessageBox.information(self, "Save Image", "Save finished!")

    # add by yuan
    def findFitRectangleShape(self, rectangle):
        min_rectx = 0
        min_recty = 0
        max_rectx = float('inf')
        max_recty = float('inf')

        isfindrect = False
        for shape in self.shapes:
            if not shape.drawRegion:
                rect = self.storePoint(shape.points)
                if rect[0] <= rectangle[0] and rect[1] <= rectangle[1]:
                    if rect[2] >= rectangle[2] and rect[3] >= rectangle[3]:
                        if rect[0] >= min_rectx and rect[1] >= min_recty:
                            if rect[2]<= max_rectx and rect[3] <= max_recty:
                                min_rectx = rect[0]
                                min_recty = rect[1]
                                max_rectx = rect[2]
                                max_recty = rect[3]
                                isfindrect = True

        if isfindrect:
            rect_x = min_rectx
            rect_y = min_recty
            rect_width = int (max_rectx - min_rectx)
            rect_height =int (max_recty - min_recty)
        else:
            rect_x = rectangle[0] - 5
            if rect_x <=0 :
                rect_x = 1

            rect_y = rectangle[1] - 5
            if rect_y <=0:
                rect_y = 1

            rect_width = int(rectangle[2] - rectangle[0]) + 10
            rect_height = int(rectangle[3] - rectangle[1]) + 10

        return (rect_x, rect_y, rect_width, rect_height)

    def saveRegionByOutsideRectangle(self, shape, rectangle, str_time):
        print ('begin - ')
        pix = QPixmap(self.pixmap.width(), self.pixmap.height())

        pp = QPainter()
        pp.begin(pix)

        pp.setPen(QPen(QColor(0, 0, 0)))
        pp.setBrush(QBrush(QColor(255, 255, 255)))

        polygon = QPolygonF()
        for point in shape:
            polygon.append(QPointF(point.x(), point.y()))

        print('draw polygon')
        pp.drawPolygon(polygon)
        pp.end()

        print('copy image')
        pix = pix.copy(rectangle[0], rectangle[1], rectangle[2], rectangle[3])
        print ('save image')

        imgside = 'right'
        if rectangle[0] < 380:
            imgside = 'left'

        self.saveSplitImage(shape, pix, True, imgside, str_time)
        print('end - ')


    # add by yuan => save mask by rectangle shape
    def findContainRegion(self, shape, rectangle, str_time):
        pix = QPixmap(self.pixmap.width(), self.pixmap.height())
        #size = pix.size()

        pp = QPainter()
        pp.begin(pix)
        pp.setPen(QPen(QColor(0,0,0)))
        pp.setBrush(QBrush(QColor(255,255,255)))

        polygon = QPolygonF()

        for s in self.shapes:
            if s.drawRegion:
                polygon.clear()
                for point in s:
                    polygon.append(QPointF(point.x(), point.y()))
                pp.drawPolygon(polygon)
        pp.end()

        pix = pix.copy(rectangle[0], rectangle[1], rectangle[2], rectangle[3])

        imgside = 'right'
        if rectangle[0] < 380:
            imgside = 'left'

        self.saveSplitImage(shape, pix, True, imgside,  str_time)

    # These two, along with a call to adjustSize are required for the
    # scroll area.
    def sizeHint(self):
        return self.minimumSizeHint()

    def minimumSizeHint(self):
        if self.pixmap:
            return self.scale * self.pixmap.size()
        return super(Canvas, self).minimumSizeHint()

    def wheelEvent(self, ev):
        qt_version = 4 if hasattr(ev, "delta") else 5
        if qt_version == 4:
            if ev.orientation() == Qt.Vertical:
                v_delta = ev.delta()
                h_delta = 0
            else:
                h_delta = ev.delta()
                v_delta = 0
        else:
            delta = ev.angleDelta()
            h_delta = delta.x()
            v_delta = delta.y()

        mods = ev.modifiers()
        if Qt.ControlModifier == int(mods) and v_delta:
            self.zoomRequest.emit(v_delta)
        else:
            v_delta and self.scrollRequest.emit(v_delta, Qt.Vertical)
            h_delta and self.scrollRequest.emit(h_delta, Qt.Horizontal)
        ev.accept()

    def keyPressEvent(self, ev):
        key = ev.key()
        if key == Qt.Key_Escape and self.current:
            print('ESC press')
            self.current = None
            self.drawingPolygon.emit(False)
            self.update()
        elif key == Qt.Key_Return and self.canCloseShape():
            self.finalise()
        elif key == Qt.Key_Left and self.selectedShape:
            self.moveOnePixel('Left')
        elif key == Qt.Key_Right and self.selectedShape:
            self.moveOnePixel('Right')
        elif key == Qt.Key_Up and self.selectedShape:
            self.moveOnePixel('Up')
        elif key == Qt.Key_Down and self.selectedShape:
            self.moveOnePixel('Down')

    def moveOnePixel(self, direction):
        # print(self.selectedShape.points)
        if direction == 'Left' and not self.moveOutOfBound(QPointF(-1.0, 0)):
            # print("move Left one pixel")
            self.selectedShape.points[0] += QPointF(-1.0, 0)
            self.selectedShape.points[1] += QPointF(-1.0, 0)
            self.selectedShape.points[2] += QPointF(-1.0, 0)
            self.selectedShape.points[3] += QPointF(-1.0, 0)
        elif direction == 'Right' and not self.moveOutOfBound(QPointF(1.0, 0)):
            # print("move Right one pixel")
            self.selectedShape.points[0] += QPointF(1.0, 0)
            self.selectedShape.points[1] += QPointF(1.0, 0)
            self.selectedShape.points[2] += QPointF(1.0, 0)
            self.selectedShape.points[3] += QPointF(1.0, 0)
        elif direction == 'Up' and not self.moveOutOfBound(QPointF(0, -1.0)):
            # print("move Up one pixel")
            self.selectedShape.points[0] += QPointF(0, -1.0)
            self.selectedShape.points[1] += QPointF(0, -1.0)
            self.selectedShape.points[2] += QPointF(0, -1.0)
            self.selectedShape.points[3] += QPointF(0, -1.0)
        elif direction == 'Down' and not self.moveOutOfBound(QPointF(0, 1.0)):
            # print("move Down one pixel")
            self.selectedShape.points[0] += QPointF(0, 1.0)
            self.selectedShape.points[1] += QPointF(0, 1.0)
            self.selectedShape.points[2] += QPointF(0, 1.0)
            self.selectedShape.points[3] += QPointF(0, 1.0)
        self.shapeMoved.emit()
        self.repaint()

    def moveOutOfBound(self, step):
        points = [p1+p2 for p1, p2 in zip(self.selectedShape.points, [step]*4)]
        return True in map(self.outOfPixmap, points)

    def setLastLabel(self, text, line_color  = None, fill_color = None):
        assert text
        self.shapes[-1].label = text
        if line_color:
            self.shapes[-1].line_color = line_color
        
        if fill_color:
            self.shapes[-1].fill_color = fill_color

        return self.shapes[-1]

    def undoLastLine(self):
        assert self.shapes
        self.current = self.shapes.pop()
        self.current.setOpen()
        self.line.points = [self.current[-1], self.current[0]]
        self.drawingPolygon.emit(True)

    def resetAllLines(self):
        assert self.shapes
        self.current = self.shapes.pop()
        self.current.setOpen()
        self.line.points = [self.current[-1], self.current[0]]
        self.drawingPolygon.emit(True)
        self.current = None
        self.drawingPolygon.emit(False)
        self.update()

    def loadPixmap(self, pixmap):
        self.pixmap = pixmap
        self.shapes = []
        self.repaint()

    def loadShapes(self, shapes):
        self.shapes = list(shapes)
        self.current = None
        self.repaint()

    def setShapeVisible(self, shape, value):
        self.visible[shape] = value
        self.repaint()

    def currentCursor(self):
        cursor = QApplication.overrideCursor()
        if cursor is not None:
            cursor = cursor.shape()
        return cursor

    def overrideCursor(self, cursor):
        self._cursor = cursor
        if self.currentCursor() is None:
            QApplication.setOverrideCursor(cursor)
        else:
            QApplication.changeOverrideCursor(cursor)

    def restoreCursor(self):
        QApplication.restoreOverrideCursor()

    def resetState(self):
        self.restoreCursor()
        self.pixmap = None
        self.update()

    def setDrawingShapeToSquare(self, status):
        self.drawSquare = status

    def setDrawRegion(self, status):
        self.drawRegion = status

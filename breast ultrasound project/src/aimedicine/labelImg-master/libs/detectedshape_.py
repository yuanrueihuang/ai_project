#!/usr/bin/python
# -*- coding: utf-8 -*-


try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
except ImportError:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

from libs.lib import distance
import sys


DEFAULT_HORIZONTAL_LINE_COLOR = QColor(0, 0, 128, 255)
DEFAULT_VIRTICAL_LINE_COLOR = QColor(0, 128, 255, 0)

DEFAULT_BI_DADS_2_COLOR = QColor(0, 255, 0)
DEFAULT_BI_DADS_3_COLOR = QColor(255, 255, 0)
DEFAULT_BI_DADS_4_COLOR = QColor(255, 0, 0)

DEFAULT_DETECTED_RECTANGLE_COLOR = QColor(255, 255, 255)

DEFAULT_LINE_COLOR = QColor(0, 255, 0, 128)
DEFAULT_FILL_COLOR = QColor(255, 0, 0, 128)
DEFAULT_SELECT_LINE_COLOR = QColor(255, 255, 255)
DEFAULT_SELECT_FILL_COLOR = QColor(0, 128, 255, 155)
DEFAULT_VERTEX_FILL_COLOR = QColor(0, 255, 0, 255)
DEFAULT_HVERTEX_FILL_COLOR = QColor(255, 0, 0)
#MIN_Y_LABEL = 10

class DetectedShape(object):
    #P_SQUARE, P_ROUND = range(2)

    #MOVE_VERTEX, NEAR_VERTEX = range(2)

    # The following class variables influence the drawing
    # of _all_ shape objects.
    line_color = DEFAULT_LINE_COLOR
    fill_color = DEFAULT_FILL_COLOR
    select_line_color = DEFAULT_SELECT_LINE_COLOR
    select_fill_color = DEFAULT_SELECT_FILL_COLOR
    vertex_fill_color = DEFAULT_VERTEX_FILL_COLOR
    hvertex_fill_color = DEFAULT_HVERTEX_FILL_COLOR

    DISPLAY_AXIS = 0x1
    DISPLAY_RECT = 0x2

    #point_type = P_ROUND
    #point_size = 8
    scale = 1.0

    def __init__(self, label=2):
        self.label = label
        self.points = []
        self.horizontal_line = None
        self.vertical_line = None
        self.roi_rectangle = None
        self.tumor_area = 0
        self.vertical_length = 0
        self.horizontal_leng = 0
        self.SelectedDisplay = self.DISPLAY_RECT| self.DISPLAY_AXIS

        print ('bi-rads:',label)
        self.bi_rads_colors = [DEFAULT_BI_DADS_2_COLOR, DEFAULT_BI_DADS_2_COLOR, DEFAULT_BI_DADS_2_COLOR,\
                               DEFAULT_BI_DADS_3_COLOR, DEFAULT_BI_DADS_4_COLOR]

        #self.fill = False
        self.selected = False
        #self.difficult = difficult
        #self.paintLabel = paintLabel

        #self._highlightIndex = None
        #self._highlightMode = self.NEAR_VERTEX
        #self._highlightSettings = {
        #    self.NEAR_VERTEX: (4, self.P_ROUND),
        #    self.MOVE_VERTEX: (1.5, self.P_SQUARE),
        #}

        self._closed = False
        #self.drawRegion = drawRegion
        #self.shapeType = shapeType

        #if line_color is not None:
            # Override the class line_color attribute
            # with an object attribute. Currently this
            # is used for drawing the pending line a different color.
        #self.line_color = line_color

    def close(self):
        self._closed = True

    def clearPoints(self):
        return self.points.clear()

    def addPoint(self, point):
        self.points.append(point)

    def paintPoint(self, painter):
        for pos_tmp in self.points:
            painter.drawLine(pos_tmp.x(), pos_tmp.y(), pos_tmp.x(), pos_tmp.y())
            #print('pt : ', pos_tmp)

    def paintRectangle(self, painter):
        if self.roi_rectangle is None:
            return

        line_path = QPainterPath()

        vrtx_path = QPainterPath()

        line_path.moveTo(self.roi_rectangle[0])

        # Uncommenting the following line will draw 2 paths
        # for the 1st vertex, and make it non-filled, which
        # may be desirable.
        # self.drawVertex(vrtx_path, 0)
        #print('s : ' ,self.roi_rectangle[0])

        #for i, p in enumerate(self.roi_rectangle):
            #line_path.lineTo(p)
            #print (i,' : ',p)
        self.drawVertex(self.roi_rectangle[0], vrtx_path)
        self.drawVertex(self.roi_rectangle[2], vrtx_path)

        #print('e : ', self.roi_rectangle[0])
        #if self.isClosed():
        line_path.lineTo(self.roi_rectangle[1])
        line_path.lineTo(self.roi_rectangle[2])
        line_path.lineTo(self.roi_rectangle[3])
        line_path.lineTo(self.roi_rectangle[0])

        painter.drawPath(line_path)
        painter.drawPath(vrtx_path)
        painter.fillPath(vrtx_path, DEFAULT_DETECTED_RECTANGLE_COLOR)

        # Draw text at the top-left
        """
        if self.paintLabel:
            min_x = sys.maxsize
            min_y = sys.maxsize
            for point in self.points:
                min_x = min(min_x, point.x())
                min_y = min(min_y, point.y())
            if min_x != sys.maxsize and min_y != sys.maxsize:
                font = QFont()
                font.setPointSize(8)
                font.setBold(True)
                painter.setFont(font)
                if (self.label == None):
                    self.label = ""
                if (min_y < MIN_Y_LABEL):
                    min_y += MIN_Y_LABEL
                painter.drawText(min_x, min_y, self.label)
            """

        #if self.fill:
        #    color = self.select_fill_color if self.selected else self.fill_color
        #    painter.fillPath(line_path, color)

    def drawVertex(self, point , path):
        d = 2.0 / self.scale # 1.0
        # path.addEllipse(point, d / 2.0, d / 2.0)
        path.addEllipse(point, d , d)

    def paintLineWithVertex(self, line_points , painter, vertex_color):
        line_path = QPainterPath()

        vrtx_path = QPainterPath()

        line_path.moveTo(line_points[0])
        # Uncommenting the following line will draw 2 paths
        # for the 1st vertex, and make it non-filled, which
        # may be desirable.
        # self.drawVertex(vrtx_path, 0)
        self.drawVertex(line_points[0], vrtx_path)

        #for i, p in enumerate(line_points):
        line_path.lineTo(line_points[1])
        self.drawVertex(line_points[1], vrtx_path)

        #if self.isClosed():
        #    line_path.lineTo(self.points[0])

        painter.drawPath(line_path)
        painter.drawPath(vrtx_path)
        #painter.fillPath(line_path, vertex_color)
        painter.fillPath(vrtx_path, vertex_color)

    def paint(self, painter):
        if self.selected:
            if self.SelectedDisplay & self.DISPLAY_AXIS:
                if self.horizontal_line is not None:
                    color = DEFAULT_HORIZONTAL_LINE_COLOR  # self.select_line_color if self.selected else self.line_color
                    color.setAlphaF(1.0)
                    pen = QPen(color)
                    pen.setStyle(Qt.DashLine)
                    pen.setWidth(max(1, int(round(2.0 / self.scale))))
                    painter.setPen(pen)
                    self.paintLineWithVertex(self.horizontal_line, painter, color)

                if self.vertical_line is not None:
                    color = DEFAULT_VIRTICAL_LINE_COLOR  # self.select_line_color if self.selected else self.line_color
                    color.setAlphaF(1.0)
                    pen = QPen(color)
                    pen.setStyle(Qt.DashLine)
                    pen.setWidth(max(1, int(round(2.0 / self.scale))))
                    painter.setPen(pen)
                    self.paintLineWithVertex(self.vertical_line, painter, color)

            if self.SelectedDisplay & self.DISPLAY_RECT:
                if self.roi_rectangle is not None:
                    color = DEFAULT_DETECTED_RECTANGLE_COLOR  # self.select_line_color if self.selected else self.line_color
                    color.setAlphaF(0.5)
                    pen = QPen(color)
                    #pen.setStyle(Qt.DashLine)
                    pen.setWidth(max(1, int(round(2.0 / self.scale))))
                    painter.setPen(pen)
                    self.paintRectangle(painter)
        else:
            if self.points:
                color = self.bi_rads_colors[self.label]  #self.select_line_color if self.selected else self.line_color
                color.setAlphaF(0.03)
                pen = QPen(color)
                # Try using integer sizes for smoother drawing(?)
                pen.setWidth(max(1, int(round(2.0 / self.scale))))
                painter.setPen(pen)
                self.paintPoint(painter)

    def makePath(self):
        path = QPainterPath(self.points[0])
        for p in self.points[1:]:
            path.lineTo(p)
        return path

    def containsPoint(self, point):
        x = int(point.x())
        y = int(point.y())
        for p in self.points:
            if p.x() == x and p.y() == y:
                return True
        return False
        #return self.makePath().contains(point)

    def boundingRect(self):
        return self.makePath().boundingRect()

    def copy(self):
        shape = DetectedShape("%s" % self.label)
        shape.points = [p for p in self.points]
        shape.selected = self.selected
        return shape

    def __len__(self):
        return len(self.points)

    def __getitem__(self, key):
        return self.points[key]

    def __setitem__(self, key, value):
        self.points[key] = value

    def set_tumor_area(self, tumor_area):
        self.tumor_area = tumor_area

    def set_Horizontal_Line(self, relative_point, line_points, line_len):
        # print ('h point:', line_points)
        self.horizontal_length = line_len

        if line_points is not None:
            self.horizontal_line = [
                                QPointF(relative_point[0]+line_points[0][0],
                                        relative_point[1]+line_points[0][1]),
                                QPointF(relative_point[0]+line_points[1][0],
                                        relative_point[1]+line_points[1][1])]

    def set_Vertical_Line(self, relative_point, line_points, line_len):
        # print('v point:', line_points)
        self.vertical_length = line_len

        if line_points is not None:
            self.vertical_line = [
                    QPointF(relative_point[0] + line_points[0][0],
                            relative_point[1] + line_points[0][1]),
                    QPointF(relative_point[0] + line_points[1][0],
                            relative_point[1] + line_points[1][1])]

    def set_Detected_Rectangle(self, relative_point, rectangle_point):
        print ('rect : ',rectangle_point)
        if rectangle_point is not None:
            self.roi_rectangle = [
                QPointF(relative_point[0] + rectangle_point[1],
                        relative_point[1] + rectangle_point[0]),

                QPointF(relative_point[0] + rectangle_point[3],
                        relative_point[1] + rectangle_point[0]),

                QPointF(relative_point[0] + rectangle_point[3],
                        relative_point[1] + rectangle_point[2]),

                QPointF(relative_point[0] + rectangle_point[1],
                        relative_point[1] + rectangle_point[2])]

    # property_name = ['BI-RADS', 'Position', 'Area', 'Horizontal Axis', 'Vertical Axis']
    def get_selected_shape_information(self):
        rectMinPt = '({}, {})'.format(int(self.roi_rectangle[0].x()), int(self.roi_rectangle[0].y()))

        rectMaxPt = '({}, {})'.format(int(self.roi_rectangle[2].x()), int(self.roi_rectangle[2].y()))

        horPt = '({}, {}), ({}, {})'.format(int(self.horizontal_line[0].x()), int(self.horizontal_line[0].y()),
                                          int(self.horizontal_line[1].x()), int(self.horizontal_line[1].y()))

        vertPt = '({}, {}), ({}, {})'.format(int(self.vertical_line[0].x()), int(self.vertical_line[0].y()),
                                         int(self.vertical_line[1].x()), int(self.vertical_line[1].y()))

        return [str(self.label), rectMinPt, rectMaxPt, str(self.tumor_area)+" cm2",
                horPt, str(self.horizontal_length)+" cm",
                vertPt, str(self.vertical_length)+" cm"]

    """
    def reachMaxPoints(self):
        if len(self.points) >= 4:
            return True
        return False

     def drawVertex(self, path, i):
        d = 1.0 / self.scale
        point = self.points[i]
        path.addEllipse(point, d / 2.0, d / 2.0)
        
     def paint(self, painter):
        if self.points:
            if self.shapeType == 1:
                color = self.select_line_color if self.selected else self.line_color
                color.setAlphaF(0.01);
                pen = QPen(color)
                # Try using integer sizes for smoother drawing(?)
                pen.setWidth(max(1, int(round(2.0 / self.scale))))
                painter.setPen(pen)
                self.paintRegion(painter)
            else:
                color = self.select_line_color if self.selected else self.line_color
                pen = QPen(color)
                # Try using integer sizes for smoother drawing(?)
                pen.setWidth(max(1, int(round(2.0 / self.scale))))
                painter.setPen(pen)

                if self.drawRegion:
                    self.paintRegion(painter)
                else:
                    self.paintRectangle(painter)

            "
            line_path = QPainterPath()

            vrtx_path = QPainterPath()

            line_path.moveTo(self.points[0])
            # Uncommenting the following line will draw 2 paths
            # for the 1st vertex, and make it non-filled, which
            # may be desirable.
            # self.drawVertex(vrtx_path, 0)

            for i, p in enumerate(self.points):
                line_path.lineTo(p)
                self.drawVertex(vrtx_path, i)

            if self.isClosed():
                line_path.lineTo(self.points[0])

            painter.drawPath(line_path)
            painter.drawPath(vrtx_path)
            painter.fillPath(vrtx_path, self.vertex_fill_color)

            # Draw text at the top-left
            if self.paintLabel:
                min_x = sys.maxsize
                min_y = sys.maxsize
                for point in self.points:
                    min_x = min(min_x, point.x())
                    min_y = min(min_y, point.y())
                if min_x != sys.maxsize and min_y != sys.maxsize:
                    font = QFont()
                    font.setPointSize(8)
                    font.setBold(True)
                    painter.setFont(font)
                    if (self.label == None):
                        self.label = ""
                    if (min_y < MIN_Y_LABEL):
                        min_y += MIN_Y_LABEL
                    painter.drawText(min_x, min_y, self.label)

            if self.fill:
                color = self.select_fill_color if self.selected else self.fill_color
                painter.fillPath(line_path, color)
            "
    
     def drawVertex(self, path, i):
        d = self.point_size / self.scale
        shape = self.point_type
        point = self.points[i]
        if i == self._highlightIndex:
            size, shape = self._highlightSettings[self._highlightMode]
            d *= size
        if self._highlightIndex is not None:
            self.vertex_fill_color = self.hvertex_fill_color
        else:
            self.vertex_fill_color = Shape.vertex_fill_color
        if shape == self.P_SQUARE:
            path.addRect(point.x() - d / 2, point.y() - d / 2, d, d)
        elif shape == self.P_ROUND:
            path.addEllipse(point, d / 2.0, d / 2.0)
        else:
            assert False, "unsupported vertex shape"
            
     def nearestVertex(self, point, epsilon):
        for i, p in enumerate(self.points):
            if distance(p - point) <= epsilon:
                return i
        return None
    
    
        
    def moveBy(self, offset):
        self.points = [p + offset for p in self.points]
        
    def moveVertexBy(self, i, offset):
        self.points[i] = self.points[i] + offset
        
    def paintRegion(self, painter):
        point_start = self.points[0]
        for pos_tmp in self.points:
            point_end = pos_tmp
            painter.drawLine(point_start.x(), point_start.y(), point_end.x() , point_end.y())
                point_start = point_end
    """
#!/usr/bin/env python

import numpy
from PyQt5.QtGui import QImage, QColor

class ConvertQImage:

	_bgra_rec = numpy.dtype({'b': (numpy.uint8, 0),
                         'g': (numpy.uint8, 1),
                         'r': (numpy.uint8, 2),
                         'a': (numpy.uint8, 3)})

	@staticmethod
	def qimage2numpy(qimage):
		if qimage.format() in (QImage.Format_ARGB32_Premultiplied,
                           QImage.Format_ARGB32,
                           QImage.Format_RGB32):
			dtype = ConvertQImage._bgra_rec
		elif qimage.format() == QImage.Format_Indexed8:
			dtype = numpy.uint8
		else:
			raise ValueError("qimage2numpy only supports 32bit and 8bit images")
		# FIXME: raise error if alignment does not match
		buf = qimage.bits().asstring(qimage.numBytes())
		return numpy.frombuffer(buf, dtype).reshape(
						(qimage.height(), qimage.width()))

	@staticmethod
	def numpy2qimage(array):
		if numpy.ndim(array) == 2:
			return ConvertQImage.gray2qimage(array)
		elif numpy.ndim(array) == 3:
			return ConvertQImage.rgb2qimage(array)
		raise ValueError("can only convert 2D or 3D arrays")

	@staticmethod
	def gray2qimage(gray_array, width=0, height=0):
		"""Convert the 2D numpy array `gray` into a 8-bit QImage with a gray
		colormap.  The first dimension represents the vertical image axis."""
		if len(gray_array.shape) != 2:
			raise ValueError("gray2QImage can only convert 2D arrays")

		gray = numpy.require(gray_array, numpy.uint8, 'C')
		#gray = gray_array
		h, w = gray.shape

		if not height == 0:
			h = height

		if not w == 0:
			w = width

		result = QImage(gray.data, w, h, QImage.Format_Indexed8)
		result.ndarray = gray
		for i in range(256):
			result.setColor(i, QColor(i, i, i).rgb())
		return result

	@staticmethod
	def rgb2qimage(rgb_array):
		"""Convert the 3D numpy array `rgb` into a 32-bit QImage.  `rgb` must
		have three dimensions with the vertical, horizontal and RGB image axes."""
		if len(rgb_array.shape) != 3:
			raise ValueError("rgb2QImage can expects the first (or last) dimension to contain exactly three (R,G,B) channels")
		if rgb_array.shape[2] != 3:
			raise ValueError("rgb2QImage can only convert 3D arrays")

		h, w, channels = rgb_array.shape

		#Qt expects 32bit BGRA data for color images:
		bgra = numpy.empty((h, w, 4), numpy.uint8, 'C')
		bgra[...,0] = rgb_array[...,2]
		bgra[...,1] = rgb_array[...,1]
		bgra[...,2] = rgb_array[...,0]
		bgra[...,3].fill(255)

		result = QImage(bgra.data, w, h, QImage.Format_RGB32)
		result.ndarray = bgra
		return result



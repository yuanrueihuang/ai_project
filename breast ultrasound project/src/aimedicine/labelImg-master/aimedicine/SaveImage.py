from time import strftime, gmtime
from os import path, mkdir
import numpy as np
import qimage2ndarray.qimageview_python as qp
import cv2
import matplotlib.pyplot as plt

class SaveImgeClass(object):

    def __init__(self, save_directory):
        BASE_DIRECTORY = 'breast dataset/train HSdataset'
        if save_directory is not None:
            BASE_DIRECTORY = save_directory

        self.img_path = path.abspath(BASE_DIRECTORY)
        if not path.exists(self.img_path):
            mkdir(self.img_path)

        self.x_axis = list(range(0, 255))

    def __save_histogram_image__(self,image_data, save_name, historgram_title):
        min_gray = np.min(image_data)
        max_gray = np.max(image_data)
        print('min:', min_gray, 'max:', max_gray)
        plt.figure()
        plt.hist(image_data.flatten().tolist(), bins=self.x_axis)
        plt.title('{} - Min:{} Max:{}'.format(historgram_title, min_gray, max_gray))
        plt.savefig(path.join(self.img_path, save_name))

    def __save_split_image__(self,image_data, save_name):
        cv2.imwrite(path.join(self.img_path, save_name), image_data, [cv2.IMWRITE_JPEG_QUALITY, 100])

    def saveSplitImage(self,image_data ,save_name):
        print("begin - saveSplitImage")

        self.__save_histogram_image__(image_data,'{}_orihist.jpg'.format(save_name),'Original Histogram')
        self.__save_split_image__(image_data,'{}_oriimage.jpg'.format(save_name))

        min_gray = np.min(image_data)
        max_gray = np.max(image_data)
        scale = 255 / (max_gray - min_gray)
        print(scale)
        trasform_img = (image_data - min_gray)
        trasform_image_data = trasform_img * scale
        trasform_image_data = trasform_image_data.astype(int)

        self.__save_histogram_image__(trasform_image_data, '{}_hshist.jpg'.format(save_name), 'Histogram Stretching')
        self.__save_split_image__(trasform_image_data, '{}_hsimage.jpg'.format(save_name))

        print("end - saveSplitImage ")
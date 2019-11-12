from mrcnn import utils
import mrcnn
import mrcnn.model as modellib
from mrcnn import visualize
from mrcnn.config import Config
import os.path
import math
import numpy as np
from operator import itemgetter
import threading
import queue


class BUModelClass(object):
    DEFAULT_WIDTH = 192
    DEFAULT_HEIGHT = 192
    Is_HS = True

    class InferenceConfig(Config):
        # Give the configuration a recognizable name
        NAME = 'breast_ultrasound'
        BACKBONE = 'resnet50'
        #BACKBONE = 'resnet101'
        # Train on 1 GPU and 8 images per GPU. We can put multiple images on each
        # GPU because the images are small. Batch size is 8 (GPUs * images/GPU).
        GPU_COUNT = 1
        IMAGES_PER_GPU = 1
        BATCH_SIZE = 1

        # Number of classes (including background)
        NUM_CLASSES = 1 + 3  # Background, BI-RADYS 2 , BI-RADYS 3, BI-RADYS 4

        # Use small images for faster training. Set the limits of the small side
        # the large side, and that determines the image shape.
        IMAGE_MIN_DIM = 192  # 448
        IMAGE_MAX_DIM = 192  # 576
        # IMAGE_MIN_SCALE = 1.0
        IMAGE_CHANNEL_COUNT = 3

        # Use smaller anchors because our image and objects are small
        #RPN_ANCHOR_SCALES = (16, 32, 64, 128, 192)  # anchor side in pixels 128
        RPN_ANCHOR_SCALES = (16, 32, 64, 128, 192)  # anchor side in pixels 128


        # Image mean (grau)
        #MEAN_PIXEL = np.array([127.0, 127.0, 127.0])
        MEAN_PIXEL = np.array([57.22, 57.22, 57.22])
        USE_MINI_MASK = True

        DETECTION_MAX_INSTANCES = 20  # 100

        MAX_GT_INSTANCES = 20  # 100

        # Reduce training ROIs per image because the images are small and have
        # few objects. Aim to allow ROI sampling to pick 33% positive ROIs.
        TRAIN_ROIS_PER_IMAGE = 16  # 32

        # How many anchors per image to use for RPN training
        RPN_TRAIN_ANCHORS_PER_IMAGE = 32  # 64

        # Use a small epoch since the data is simple
        STEPS_PER_EPOCH = 200

        # use small validation steps since the epoch is small
        VALIDATION_STEPS = 200

        # Don't resize imager for inferencing
        IMAGE_RESIZE_MODE = "pad64"

    def __init__(self):
        self.model = None
        self.IsInitial = False
        """
        self.hv_axis = None
        self.horizontal_len = 0
        self.vertical_len = 0
        self.area_val = 0
        self.side_point = None
        """
        self.mask=[]
        self.roi=[]
        self.bi_rads=[]
        self.hv_axis = []
        self.horizontal_len = []
        self.vertical_len = []
        self.area_val = []
        self.side_point = []

        self.analyze_image_queue = queue.Queue(maxsize=1)
        self.analyze_result_queue = queue.Queue(maxsize=1)

    def analyze_image(self,img):
        if self.Is_HS:
            min_gray = np.min(img[0])
            max_gray = np.max(img[0])
            #print (img[0][:10])
            # print (min_gray, max_gray)
            scale = 255 / (max_gray - min_gray)
            # print (scale)
            trasfor_img = (img[0] - min_gray)
            img[0] = trasfor_img * scale
            img[0] = img[0].astype(int)

        print ('add img', img[0].shape)
        self.analyze_image_queue.put(img)
        print('analyze_image_queue.put')

        self.thread_event.set()
        print('thread_event.set')

    def initial_job(self, event_notify , analyze_image_queue, analyze_result_queue):
        try:
            print ('initial_job -- begin')
            np.random.seed(7718)
            config = BUModelClass.InferenceConfig()
            # modir_dir = os.path.join(os.path.dirname( os.path.realpath(__file__)),'logs')
            modir_dir = os.path.join(os.path.abspath('.'), 'aimedicine//logs')
            print(modir_dir)
            model = modellib.MaskRCNN(mode="inference", model_dir=modir_dir, config=config)

            model_path = model.find_last()
            print(model_path)
            # Load trained weights
            print("Loading weights from ", model_path)
            model.load_weights(model_path, by_name=True)

            print('analyze_result_queue - True')
            analyze_result_queue.put(True)

            while(True):
                print ('waiting')
                event_notify.wait()
                print('get notify')
                img = analyze_image_queue.get()
                print('get img', img[0].shape)
                result = model.detect(img, verbose=0)
                print (result[0])
                analyze_result_queue.put(result[0])
                print ('clear notify')
                event_notify.clear()
            print ('Exit thread')
        except Exception as e:
            model = None
            print(str(e))

    def loading_AI_Mode(self):
        model = None
        self.thread_event = threading.Event()
        t = threading.Thread(target=self.initial_job, args=(self.thread_event, self.analyze_image_queue, self.analyze_result_queue))
        t.setDaemon(True)
        t.start()
        #t.join()

    def get_result(self):
        if not self.analyze_result_queue.empty():
            return self.analyze_result_queue.get()
        return None

    def is_completed(self):
        return not self.analyze_result_queue.empty()

    def is_initial_completed(self):
        if not self.IsInitial:
            if self.analyze_result_queue.empty():
                return False
            self.IsInitial = self.analyze_result_queue.get()

        return self.IsInitial

    def __internal_section__(self, check_point, rect_point):
        if check_point[1] >= rect_point[0] and check_point[1] <= rect_point[2]:  # y pos
            if check_point[0] >= rect_point[1] and check_point[0] <= rect_point[3]:  # x pos
                return True
        return False

    def __compute_center_distance_on_rectenagle__(self, check_point, rect_point):
        print ('roi:', rect_point)
        distance_x = rect_point[2] - rect_point[1]
        distance_y = rect_point[3] - rect_point[0]
        distance_x = math.pow(distance_x - check_point[0], 2)
        distance_y = math.pow(distance_y - check_point[1], 2)
        return math.sqrt(distance_x + distance_y)

    def __roi_area__(self, mask, pixel_unit=0.01):
        area_val = np.sum(mask) * pixel_unit * pixel_unit
        return round(area_val, 3)

    def __horizontal_vertical_axis__(self, mask, rect):
        h_axis_min = None
        h_axis_max = None
        v_axis_min = None
        v_axis_max = None
        print(mask.shape)

        for col in range(rect[1], mask.shape[1]):
            for row in range(rect[0], mask.shape[0]):
                if mask[row][col] == 1:
                    h_axis_min = (col, row)
                    break
            if not h_axis_min is None:
                break

        if h_axis_min[1] <= mask.shape[0]/2:
            for col in range(mask.shape[1] - 1, rect[1], -1):
                for row in range(mask.shape[0] - 1, rect[0], -1):
                    if mask[row][col] == 1:
                        h_axis_max = (col, row)
                        break
                if not h_axis_max is None:
                    break
        else:
            for col in range(mask.shape[1] - 1, rect[1], -1):
                for row in range(rect[0], mask.shape[0]):
                    if mask[row][col] == 1:
                        h_axis_max = (col, row)
                        break
                if not h_axis_max is None:
                    break


        # max_height = np.sum(mask, axis=0)  # row sum
        if h_axis_min[1] < h_axis_max[1]:
            for row in range(rect[0], mask.shape[0]):
                for col in range(mask.shape[1] - 1, rect[1], -1):
                    if mask[row][col] == 1:
                        v_axis_min = (col, row)
                        break
                if not v_axis_min is None:
                    break

            for row in range(mask.shape[0] - 1, rect[0], -1):
                for col in range(rect[1], mask.shape[1], 1):
                    if mask[row][col] == 1:
                        v_axis_max = (col, row)
                        break
                if not v_axis_max is None:
                    break
        else:
            for row in range(rect[0], mask.shape[0]):
                for col in range(rect[1], mask.shape[1], 1):
                    if mask[row][col] == 1:
                        v_axis_min = (col, row)
                        break
                if not v_axis_min is None:
                    break

            for row in range(mask.shape[0] - 1, rect[0], -1):
                for col in range(mask.shape[1] - 1, rect[1], -1):
                    if mask[row][col] == 1:
                        v_axis_max = (col, row)
                        break
                if not v_axis_max is None:
                    break

        return (h_axis_min, h_axis_max, v_axis_min, v_axis_max)

    def __distance_between_point__(self, start_point, end_point, pixel_unit=0.01):
        distance_x = math.pow(start_point[0] - end_point[0], 2)
        distance_y = math.pow(start_point[1] - end_point[1], 2)
        return round(math.sqrt(distance_x + distance_y) * pixel_unit, 3)

    def __mask_side_point__(self, mask):
        side_point = []
        for row in range(1, self.DEFAULT_HEIGHT-1):
            for col in range(1, self.DEFAULT_WIDTH-1):
                if mask[row][col] == 1:
                    point_cnt = mask[row - 1][col] + mask[row + 1][col] + mask[row][col-1] + mask[row][col+1]
                    if point_cnt == 0:
                        point_cnt = mask[row-1][col+1] + mask[row-1][col-1] + mask[row+1][col-1] \
                                    + mask[row+1][col+1]

                    if point_cnt <= 3 and point_cnt > 0:
                        side_point.append((col, row))
        return side_point

    def __mask_point__(self, mask):
        side_point = []
        for row in range(0, mask.shape[0]):
            for col in range(0, mask.shape[1]):
                if mask[row][col] == 1:
                    side_point.append((col, row))
        return side_point

    def _long_short_axis_(self, side_point):
        # find all side point
        long_axis_len = 1
        long_axis = []
        for start_point in range(0, len(side_point)):
            for end_point in range(start_point, len(side_point)):
                distance_x = math.pow(side_point[start_point][0] - side_point[end_point][0], 2)
                distance_y = math.pow(side_point[start_point][1] - side_point[end_point][1], 2)
                axis_len = math.sqrt(distance_x + distance_y)
                if axis_len > long_axis_len:
                    long_axis_len = axis_len
                    long_axis = (side_point[start_point], side_point[end_point])
            # print(long_axis_len, long_axis)

        long_axis_slope = long_axis[0][0] - long_axis[1][0]
        long_axis_slope = (long_axis[0][1] - long_axis[1][1]) / long_axis_slope

        short_axis_len = 0
        short_axis = ((0, 0), (0, 0))
        for start_point in range(0, len(side_point)):
            for end_point in range(start_point, len(side_point)): # start_point
                IsKeepPoint = False
                if abs(long_axis_slope) <=0.1:
                    if abs(side_point[start_point][0] - side_point[end_point][0]) <= 5:
                       IsKeepPoint = True
                elif side_point[start_point][0] != side_point[end_point][0]:
                    # 兩條線相交其斜率相乘等於-1.
                    slope = side_point[start_point][0] - side_point[end_point][0]
                    slope = (side_point[start_point][1] - side_point[end_point][1]) / slope
                    if abs((slope * long_axis_slope) + 1) <= 0.05 and abs((slope * long_axis_slope) + 1) >=0:
                        IsKeepPoint = True

                if IsKeepPoint:
                    distance_x = math.pow(side_point[start_point][0] - side_point[end_point][0], 2)
                    distance_y = math.pow(side_point[start_point][1] - side_point[end_point][1], 2)
                    axis_len = math.sqrt(distance_x + distance_y)
                    if axis_len > short_axis_len:
                        short_axis_len = axis_len
                        short_axis = (side_point[start_point], side_point[end_point])

        h_axis_min = min(long_axis)
        h_axis_max = max (long_axis)
        v_axis_min = min (short_axis)
        v_axis_max = max (short_axis)
        print ((h_axis_min, h_axis_max, v_axis_min, v_axis_max), round(long_axis_len / 100, 3), round(short_axis_len / 100, 3))
        return  ((h_axis_min, h_axis_max, v_axis_min, v_axis_max), round(long_axis_len/100,3), round(short_axis_len/100,3))

    def get_axis_information_by_index(self, index):
        if self.hv_axis is not None:
            return (self.hv_axis[index], self.horizontal_len[index], self.vertical_len[index])
        return None

    def get_all_side_points(self):
        if self.mask is not None:
            for index in range(len(self.mask)):
                self.side_point.append(self.__mask_point__(self.mask[index]))
            return self.side_point
        return None

    def get_all_region_area(self):
        return self.area_val

    def get_all_mask(self):
        return self.mask

    def get_all_bi_rads(self):
        return self.bi_rads

    def get_all_roi_rect(self):
        return self.roi

    def get_axis_information(self):
        if self.hv_axis is not None:
            return (self.hv_axis, self.horizontal_len, self.vertical_len)
        return None

    def get_side_points(self):
        if self.mask is not None:
            self.side_point = self.__mask_point__(self.mask)
            return self.side_point
        return None

    def get_region_area(self):
        return self.area_val

    def get_mask(self):
        return self.mask

    def get_bi_rads(self):
        return self.bi_rads

    def get_roi_rect(self):
        return self.roi

    def get_roi_count(self):
        return len(self.roi)

    def region_of_interests(self, rois, check_point, rect_point):
        self.mask = []
        self.roi = []
        self.bi_rads = []
        self.hv_axis = []
        self.horizontal_len = []
        self.vertical_len = []
        self.area_val = []
        self.side_point = []

        #self.bi_rads = [1]

        # 1 . minus clik point postion by rect minx, miny to get relative point
        relative_point = (check_point[0] - rect_point[0][0], check_point[1] - rect_point[0][1])
        # print(relative_point)
        # print (rois['masks'][0])

        interset_region_list = []
        mask = rois['masks']
        #if self.side_point is not None:
        #    self.side_point.clear()

        # 2. click point is internal area
        for i, (roi, cls_id, score) in enumerate(zip(rois['rois'], rois['class_ids'], rois['scores'])):
            if self.__internal_section__(relative_point, roi):
                interset_region_list.append([int(cls_id) + 1, float(score), roi, mask[:, :, i].astype(np.uint8)])

        # 3. computer center point and distance between click point and center point if more one region
        if len(interset_region_list) >= 1:
            for region in interset_region_list:
                distance = self.__compute_center_distance_on_rectenagle__(relative_point, region[2])
                region.insert(0, distance)

            # [s for s in x if len(s) == 2] - example 1
            # [x+1 if x >= 45 else x+5 for x in l] - example  2
            if len(interset_region_list) > 1:
                # sort distance between center point and click point
                region_list = sorted(interset_region_list, key=itemgetter(0))
                # region_list = region_list[0:2]  # select first two
                # sort by sorce
                interset_region_list = sorted(region_list, key=itemgetter(2), reverse=True)


            for index in range (len(interset_region_list)):
                self.mask.append(interset_region_list[index][4])
                self.roi.append(interset_region_list[index][3])
                self.bi_rads.append(interset_region_list[index][1])

                #self.hv_axis.append(self.__horizontal_vertical_axis__(self.mask[index], self.roi[index]))
                #self.horizontal_len.append(self.__distance_between_point__(
                #                            self.hv_axis[index][0], self.hv_axis[index][1]))
                #self.vertical_len.append(self.__distance_between_point__(
                #                            self.hv_axis[index][2], self.hv_axis[index][3]))
                self.area_val.append(self.__roi_area__(self.mask[index]))
                self.side_point.append(self.__mask_point__(self.mask[index]))
                side_point = self.__mask_side_point__(self.mask[index])

                hv_axis, long_axis_len, short_axis_len = self._long_short_axis_(side_point)
                self.hv_axis.append(hv_axis)
                self.vertical_len.append(short_axis_len)
                self.horizontal_len.append( long_axis_len)

            # self.side_point = self.__mask_side_point__(self.mask)

        return len(interset_region_list) >= 1

    def region_of_interest(self, rois , check_point, rect_point):
        self.bi_rads = 1

        # 1 . minus clik point postion by rect minx, miny to get relative point
        relative_point = (check_point[0] - rect_point[0][0], check_point[1] - rect_point[0][1])
        #print(relative_point)
        # print (rois['masks'][0])

        interset_region_list = []
        mask = rois['masks']
        if self.side_point is not None:
            self.side_point.clear()

        # 2. click point is internal area
        for i, (roi, cls_id, score) in enumerate(zip(rois['rois'], rois['class_ids'], rois['scores'])):
            if self.__internal_section__(relative_point, roi):
                interset_region_list.append([int(cls_id)+1, float(score), roi, mask[:, :, i].astype(np.uint8)])

        # 3. computer center point and distance between click point and center point if more one region
        if len(interset_region_list) >= 1:
            for region in interset_region_list:
                distance = self.__compute_center_distance_on_rectenagle__(relative_point, region[2])
                region.insert(0, distance)

            # [s for s in x if len(s) == 2] - example 1
            # [x+1 if x >= 45 else x+5 for x in l] - example  2
            if len(interset_region_list) > 1:
                # sort distance between center point and click point
                region_list = sorted(interset_region_list, key=itemgetter(0))
                region_list = region_list[0:2] # select first two
                # sort by sorce
                interset_region_list = sorted(region_list, key=itemgetter(2), reverse=True)

            self.mask = interset_region_list[0][4]
            self.roi = interset_region_list[0][3]
            self.bi_rads = interset_region_list[0][1]
            self.hv_axis = self.__horizontal_vertical_axis__(self.mask, self.roi)

            self.horizontal_len = self.__distance_between_point__(self.hv_axis[0], self.hv_axis[1])
            self.vertical_len = self.__distance_between_point__(self.hv_axis[2], self.hv_axis[3])

            self.area_val = self.__roi_area__(self.mask)
            self.side_point = self.__mask_point__(self.mask)
            #self.side_point = self.__mask_side_point__(self.mask)

        return len(interset_region_list) >=1

"""  
def prepare_model(self):
        try:
            if self.model is None:
                config = BUModelClass.InferenceConfig()
                #modir_dir = os.path.join(os.path.dirname( os.path.realpath(__file__)),'logs')
                modir_dir = os.path.join(os.path.abspath('.'), 'aimedicine//logs')
                print (modir_dir)
                self.model = modellib.MaskRCNN(mode="inference", model_dir=modir_dir, config=config)

                # Get path to saved weights
                # Either set a specific path or find last trained weights
                # model_path = os.path.join(ROOT_DIR, ".h5 file name here")
                model_path = self.model.find_last()
                print(model_path)

                # Load trained weights
                print("Loading weights from ", model_path)
                self.model.load_weights(model_path, by_name=True)
        except Exception as e:
            self.model = None
            print(str(e))

def predict_model(self, image):
        if self.model is None:
            return

        self.hv_axis = None
        self.horizontal_len = 0
        self.vertical_len = 0
        self.area_val = 0
        self.side_point = None

        return self.model.detect(image, verbose=0)
"""
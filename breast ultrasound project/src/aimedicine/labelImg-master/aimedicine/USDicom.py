import datetime
import time
import numpy as np
from pydicom.dataset import FileDataset
from matplotlib import pyplot as plt
from pydicom.sequence import Sequence
import pydicom as dicom
from pydicom.datadict import DicomDictionary, keyword_dict
from pydicom.dataset import Dataset
import struct

"""
TAG_DESCRIBES = {}
"""
class USDicomClass(object):
    MIN_X0 = 0x00186018
    MIN_Y0 = 0x0018601A
    MAX_X1 = 0x0018601C
    MAX_Y1 = 0x0018601E

    AI_ANLAYSIS_ITEM = {
        0x7FE10010: ('SQ', '1', "Tumor Information", '0.0', 'TumorInformation'),
        0x00180001: ('US', '1', "BI-RADS", '0', 'BIRADS'),
        0x00180002: ('FD', '1', "Long Axis", '0.0', 'LongAxis'),
        0x00180003: ('FD', '1', "Short Axis", '0.0', 'ShortAxis'),
        0x00180004: ('FD', '1', "Tumor Area", '0.0', 'TumorArea'),

        0x00180005: ('UL', '1', "Long Axis MinX", '0', 'LongAxisMinX'),
        0x00180006: ('UL', '1', "Long Axis MinY", '0', 'LongAxisMinY'),
        0x00180007: ('UL', '1', "Long Axis MaxX", '0', 'LongAxisMinX'),
        0x00180008: ('UL', '1', "Long Axis MaxY", '0', 'LongAxisMinY'),

        0x00180009: ('UL', '1', "Short Axis MinX", '0', 'ShortAxisMinX'),
        0x0018000A: ('UL', '1', "Short Axis MinY", '0', 'ShortAxisMinY'),
        0x0018000B: ('UL', '1', "Short Axis MaxX", '0', 'ShortAxisMaxX'),
        0x0018000C: ('UL', '1', "Short Axis MaxY", '0', 'ShortAxisMaxY'),

        0x0018000D: ('OW', '1', "Mask PointX", '', 'MaskPointX'),
        0x0018000E: ('OW', '1', "Mask PointY", '', 'MaskPointY'),
    }

    def __init__(self, file_name, IsCreate=False):
        ## This code block was taken from the output of a MATLAB secondary
        ## capture.  I do not know what the long dotted UIDs mean, but
        ## this code works.
        # Define items as (VR, VM, description, is_retired flag, keyword)
        #   Leave is_retired flag blank.

        # Update the dictionary itself
        DicomDictionary.update(self.AI_ANLAYSIS_ITEM)

        if IsCreate:
            self.__file_name__ = file_name
            file_meta = Dataset()

            # Ultrasound Multiframe Image Storage - https://www.dicomlibrary.com/dicom/sop/
            file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.1.1.3.1'
            file_meta.MediaStorageSOPInstanceUID = '999.999.2.19941105.134500.2.101'
            file_meta.ImplementationClassUID = '999.999'
            # Transfer Syntax - https://www.dicomlibrary.com/dicom/transfer-syntax/
            file_meta.TransferSyntaxUID = '1.2.840.10008.1.2'

            ds = FileDataset(file_name, {}, file_meta=file_meta, preamble=b"\0" * 128)
            # DICOM modality, that represents DICOM file type - https://www.dicomlibrary.com/dicom/modality/
            ds.Modality = 'US'  # Ultrasound
            ds.ContentDate = str(datetime.date.today()).replace('-', '')
            ds.ContentTime = str(time.time())  # milliseconds since the epoch
            ds.StudyInstanceUID = '999.999.2.19941105.134500'
            ds.SeriesInstanceUID = '999.999.2.19941105.134500.2'
            ds.SOPInstanceUID = '999.999.2.19941105.134500.2.101'

            # https://searchcode.com/codesearch/view/13929148/
            ds.SOPClassUID = '1.2.840.10008.5.1.4.1.1.3.1'  # 'Ultrasound Multi-frame Image Storage' - 1.2.840.10008.5.1.4.1.1.3.1
            # ds.SecondaryCaptureDeviceManufctur = 'Python 2.7.3'
            self.Dataset = ds
        else:
            self.Dataset = dicom.read_file(file_name)

    def setUSImage(self, image_array, image_width, image_height):
        # https://dicom.innolitics.com/ciods/ophthalmic-photography-8-bit-image/ophthalmic-photography-image/00280002
        ## These are the necessary imaging components of the FileDataset object.
        # Dicom tag - https://www.dicomlibrary.com/dicom/dicom-tags/
        self.Dataset.add_new(0x00280008, 'IS', 1)  # Number of Frames : can setting more one
        self.Dataset.add_new(0x00181063, 'DS', 100000)  # Frames Time
        self.Dataset.add_new(0x00082128, 'IS', 1)  # View Number
        self.Dataset.add_new(0x00080008, 'CS', 'ORIGINAL\PRIMARY\BU\0001')  # Image Type
        self.Dataset.SamplesPerPixel = 1
        self.Dataset.PhotometricInterpretation = "MONOCHROME2"
        self.Dataset.PixelRepresentation = 0  # unsigned integer.
        self.Dataset.HighBit = 7  # 15
        self.Dataset.BitsStored = 8  # 16
        self.Dataset.BitsAllocated = 8  # 16
        # ds.SmallestImagePixelValue =  0 #'\\x00\\x00'
        # ds.LargestImagePixelValue =  255 # '\\xff\\xff'
        self.Dataset.Columns = image_width  # pixel_array.shape[0]
        self.Dataset.Rows = image_height  # pixel_array.shape[1]
        # pixel_array = image_array.astype(np.uint8)
        # if pixel_array.dtype != np.uint16:
        #    pixel_array = pixel_array.astype(np.uint16)
        self.Dataset.PixelData = image_array.astype(np.uint8).tostring()
        self.Dataset.add_new((0x0018, 0x6011), 'SQ', [])
        self.Dataset.add_new((0x7FE1, 0x0010), 'SQ', [])
        #self.Dataset.is_little_endian = True
        #self.Dataset.is_implicit_VR = False

    def setRegion(self, region_rect, region_type=0x1):
        # split retangle  to DL
        # http://northstar-www.dartmouth.edu/doc/idl/html_6.2/DICOM_Attributes.html
        # http://dicom.nema.org/medical/dicom/2016e/output/chtml/part03/sect_C.8.5.5.html
        # https://imagej.nih.gov/nih-image/download/nih-image_spin-offs/NucMed_Image/DICOM%20Dictionary
        ds = Dataset()
        ds.add_new((0x0018, 0x6018), 'UL', region_rect[0])  # Region Location Min X0
        ds.add_new((0x0018, 0x601A), 'UL', region_rect[1])  # Region Location Min Y0
        ds.add_new((0x0018, 0x601C), 'UL', region_rect[2])  # Region Location Max X1
        ds.add_new((0x0018, 0x601E), 'UL', region_rect[3])  # Region Location Max Y1
        ds.add_new((0x0018, 0x6024), 'UL', 0x3)  # Physical Units X Direction 0x3:cm
        ds.add_new((0x0018, 0x6026), 'UL', 0x3)  # Physical Units Y Direction 0x3:cm
        ds.add_new((0x0018, 0x602C), 'FD', 0.01)  # Physical Delta X 1 pixel : 0.05 mm
        ds.add_new((0x0018, 0x602E), 'FD', 0.01)  # Physical Delta Y 1 pixel : 0.05 mm
        ds.add_new((0x0018, 0x6012), 'US', 0x1)  # Region Spatial Format 0x1 : 2D (tissue or flow)
        ds.add_new((0x0018, 0x6014), 'US', region_type)  # Region Data Type 0x1: Tissue 0x2 : Clor Flow
        ds.add_new((0x0018, 0x6016), 'UL', 0x0)  # Region Flags  0: Region pixels are high priority
        self.Dataset[0x00186011].value.append(ds)

    def __parsing_data_set__(self, dataset, element_list):
        for sequence_item in dataset:
            element_list.append((sequence_item.tag, sequence_item.name, sequence_item.VR,
                                 sequence_item.VM, sequence_item.value))
            if sequence_item.VR == "SQ":  # a sequence
                for seq_item in data_element.value:
                    self.__parsing_data_set__(seq_item, element_list)

    def readDataset(self, element_list):
        for data_element in self.Dataset:
            element_list.append(
                (data_element.tag, data_element.name, data_element.VR, data_element.VM, data_element.value))
            if data_element.VR == "SQ":  # a sequence
                for sequence_item in data_element.value:
                    self.__parsing_data_set__(sequence_item, element_list)

    def getImages(self):
        return self.Dataset.pixel_array

    def getRegionBox(self, region_type):
        rect_box_list = []
        region_area = self.Dataset[0x00186011].value
        if len(region_area) > 0:
            for i, reg in enumerate(region_area):
                if (reg[0x00186014].value == region_type):
                    rect_box_list.append(((reg[self.MIN_X0].value, reg[self.MIN_Y0].value),
                                      (reg[self.MAX_X1].value, reg[self.MAX_Y1].value)))
        return rect_box_list

    def save(self):
        self.Dataset.save_as(self.__file_name__)

    def setPrivateCreator(self, tumor_property_list, axis_property_list, tumor_shape_pts):
        for index, tumor_property in enumerate(tumor_property_list):
            self.Dataset[0x7FE10010].value.append(Dataset())
            self.Dataset[0x7FE10010].value[-1].add_new((0x0018, 0x0001), 'US', tumor_property[0])
            self.Dataset[0x7FE10010].value[-1].add_new((0x0018, 0x0004), 'FD', tumor_property[1])
            self.Dataset[0x7FE10010].value[-1].add_new((0x0018, 0x0002), 'FD', tumor_property[2])
            self.Dataset[0x7FE10010].value[-1].add_new((0x0018, 0x0003), 'FD', tumor_property[3])

            axis_property =axis_property_list[index]
            self.Dataset[0x7FE10010].value[-1].add_new((0x0018, 0x0005), 'UL', int(axis_property[0][0]))
            self.Dataset[0x7FE10010].value[-1].add_new((0x0018, 0x0006), 'UL', int(axis_property[0][1]))
            self.Dataset[0x7FE10010].value[-1].add_new((0x0018, 0x0007), 'UL', int(axis_property[0][2]))
            self.Dataset[0x7FE10010].value[-1].add_new((0x0018, 0x0008), 'UL', int(axis_property[0][3]))

            self.Dataset[0x7FE10010].value[-1].add_new((0x0018, 0x0009), 'UL', int(axis_property[1][0]))
            self.Dataset[0x7FE10010].value[-1].add_new((0x0018, 0x000A), 'UL', int(axis_property[1][1]))
            self.Dataset[0x7FE10010].value[-1].add_new((0x0018, 0x000B), 'UL', int(axis_property[1][2]))
            self.Dataset[0x7FE10010].value[-1].add_new((0x0018, 0x000C), 'UL', int(axis_property[1][3]))

            pt_list = np.array(tumor_shape_pts[index][0]).astype(np.uint16) # X
            self.Dataset[0x7FE10010].value[-1].add_new((0x0018, 0x000D), 'OW', pt_list.tostring())

            pt_list = np.array(tumor_shape_pts[index][1]).astype(np.uint16) # Y
            self.Dataset[0x7FE10010].value[-1].add_new((0x0018, 0x000E), 'OW', pt_list.tostring())

    def convertouint(self, byte_str):
        fomart_len = 'H' * int(len(byte_str) / 2)
        testResult = struct.unpack(fomart_len, byte_str)
        return testResult

    def getPrivateCreator(self):
        private_list = self.Dataset[0x7FE10010].value
        private_data = []
        if private_list is not None:
            for index, private_table in enumerate(private_list):
                bi_rads = private_table[0x00180001].value
                horizontal_len = private_table[0x00180002].value
                vertical_len = private_table[0x00180003].value
                tumor_area = private_table[0x00180004].value
                axis_point = [(private_table[0x00180005].value, private_table[0x00180006].value,
                              private_table[0x00180007].value, private_table[0x00180008].value),
                             (private_table[0x00180009].value, private_table[0x0018000A].value,
                              private_table[0x0018000B].value, private_table[0x0018000C].value)]

                Xpoint_list = private_table[0x0018000D].value
                Xpoint_list = self.convertouint(Xpoint_list)
                Ypoint_list = private_table[0x0018000E].value
                Ypoint_list = self.convertouint(Ypoint_list)
                private_data.append((horizontal_len, vertical_len, tumor_area, bi_rads, axis_point, Xpoint_list, Ypoint_list))
        return private_data
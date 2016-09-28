import json
import struct

import numpy as np


class DigHeader(object):
    """
    class with file header and other header type data

    """

    def __init__(self, handle):
        self._handle = handle
        self.hl_bytes = 4 # number of bytes encoding the header-length
        with self._handle.file_object() as o:
            try:
                self.header_length = struct.unpack("<L", o.read(self.hl_bytes))[0]
            except TypeError:
                raise HeaderReadError("file handle has no read attribute")
            except IOError:
                raise HeaderReadError()
            assert o.tell() == self.hl_bytes
            hdr = json.loads(o.read(self.header_length))
            self._file_header = hdr
            self.total_ch = len(hdr['channel_list'])
            self.file_downsampling = self._file_header['downsample']  # if the file has already been downsampled
            self.sample_frequency = self._file_header['freq_hz'] # digitization frequency
            self.file_frequency = self.sample_frequency/self.file_downsampling
            self.output_frequency = None
            self.bit_shift = self._file_header['bit_shift']
            self.bit_depth = self.get_bit_depth()
            self.data_type = self.get_data_type()
            self.data_start = self.header_length + self.hl_bytes
            try: assert type(hdr) is dict
            except:
                raise HeaderFormatError('Header is not a dictionary unexpected header format or length')
            self.file_length = self._handle.length
            self.data_length_bytes = self.file_length - self.header_length - self.hl_bytes
            self.data_length_reads = self.data_length_bytes/(self.bit_depth * self.total_ch)

    def __getattr__(self, item):
        return self._file_header[item]

    def get_bit_depth(self):
        try:
            bd = self._file_header["bit_depth"]
        except KeyError:
            bd = self._file_header["byte_depth"]
        return bd

    def get_data_type(self):
        """ Select data encoding from bit depth """
        if self.bit_depth == 2:
            dt = np.int16
        elif self.bit_depth == 4:
            dt = np.int32
        elif self.bit_depth == 8:
            dt = np.float64
        else:
            raise HeaderFormatError("unknown bit_depth")
        return dt


class HeaderError(Exception):
    """ Exception relating to the file header """
    pass


class HeaderReadError(HeaderError, IOError):
    def __init__(self, msg=None):
        self.msg = " Attempt to read file handle failed "
        if msg is not None:
            self.msg = json.dumps(msg)


class HeaderFormatError(HeaderError, TypeError):
    def __init__(self, msg=None):
        self.msg = " Header has an unexpected format "
        if msg is not None:
            self.msg = json.dumps(msg)
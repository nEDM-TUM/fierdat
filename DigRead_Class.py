from DigHeader_Class import DigHeader
import numpy as np


class DigReadSettingError(TypeError):
    def __init__(self, msg=None):
        self.msg = "Invalid Setting for digitizer file read"
        if msg is not None:
            self.msg = msg


class DigReadChannelError(DigReadSettingError):
    def __init__(self, channel, filename, msg=None):
        self.msg = "Channel {} does not exist in the file {}".format(channel, filename)
        if msg is not None:
            self.msg = msg


class DigRead(object):
    """
    Sets up to a digitizer file from file handle, using header and read settings objects

    """

    def __init__(self, handle, header=None, requested_settings=dict()):
        """

        :param handle:
        :param header:
        :param requested_settings: a dictionary containing requested data from the reader
                The settings should include the following keys:
                'downsample': factor to downsample the data by
                'channels_to_read': list of the channel numbers that you want back
                'start_read': First digitizer read number to include
                'end_read': Last digitizer read number to include
        """

        self._handle = handle
        if header:
            self.header = header
        elif not header:
            self.header = DigHeader(self._handle)
        self.known_keys = [
            "downsample",
            "channels_to_read",
            "start_read",
            "end_read"]
        self.reads_per_segment = 2 ** 20  # set the number of samples per read of the file
        self.settings = self.check_settings(requested_settings)
        bit_depth = self.header.bit_depth
        downsample = self.settings['downsample']
        self.data_type = self.header.data_type
        self.total_ch = self.header.total_ch
        self.bytes_per_read = self.total_ch * bit_depth
        self.min_chunk = self.bytes_per_read * downsample
    #
    # @property
    # def channels_to_read(self):
    #     if self.settings['i']

    def __getattr__(self, item):
        return self.settings[item]

    def check_settings(self, requested_settings):
        """
        check that the requested read settings are
        valid.

        :return: Error if settings are invalid
        """
        settings_dict = dict()
        try:
            user_keys = requested_settings.keys()
        except AttributeError:
            raise DigReadSettingError('Invalid settings format, must be a dictionary with keys: {}'.format(
                default_settings.keys()))
        # load requested settings and check that they are valid
        if not set(user_keys) <= set(self.known_keys):
            unknown_keys = set(user_keys).difference(self.known_keys)
            print(unknown_keys)
            raise DigReadSettingError('Requested settings "{}" not recognized.  Possible settings are: {}'.format(
                 unknown_keys, self.known_keys))

        ds = requested_settings['downsample']
        self.check_downsample_value(ds)
        settings_dict['downsample'] = ds
        self.set_output_frequency(ds)

        chns = requested_settings['channels_to_read']
        self.check_channels(chns)
        settings_dict['channels_to_read'] = chns

        start = requested_settings['start_read']
        end = requested_settings['end_read']
        self.check_start_end_request(start, end)
        settings_dict['start_read'] = requested_settings['start_read']
        settings_dict['end_read'] = requested_settings['end_read']

        return settings_dict

    def set_output_frequency(self, downsample):
        """ give the frequency of the data points in the output array """

        ff = self.header.file_frequency
        self.header.output_frequency = ff/downsample

    def check_downsample_value(self, value):
        if type(value) is not int:
            raise DigReadSettingError('Downsample must be an integer. Invalid for request for downsample '
                                      'by factor of {} was type {}'.format(value, type(value)))
        else:
            return

    def check_channels(self, value):
        available_channels = self.header.channel_list
        bad_channel = False
        try:
            for chn in value:
                if chn not in available_channels:
                    bad_channel = True
        except TypeError:
            chn = value
            if chn not in available_channels:
                bad_channel = True
        if bad_channel:
            raise DigReadChannelError(chn, self._handle.file_name)
        else:
            return

    def check_start_end_request(self, start, end):

        if type(start) is not int:
            raise DigReadSettingError('Start read must be an integer')
        if start < 0:
            raise DigReadSettingError('Start point must greater than zero')
        if start > self.header.data_length_reads:
            raise DigReadSettingError('Start point can not be beyond the end of the file')

        if type(end) is not int:
            raise DigReadSettingError('End read must be an integer')
        if end < 0:
            raise DigReadSettingError('End point must greater than zero')
        if end > self.header.data_length_reads:
            raise DigReadSettingError('End point can not be beyond the end of the file')

        if start > end:
                raise DigReadSettingError("Requested start point must be before requested end point")

    def data_segments(self):
        """
        for getting .dig files and putting them in the class.

        File structure is:
               bytes 0..3: length of json header N (excluding header word)
        bytes 4..4+N: json header (ASCII data)
        bytes 4+N+1..EOF: binary data of channels
        The binary data format depends on what's in the json header:
        header["channel_list"] ---> ordered list of channels
        header["byte_depth"]    ---> size of binary word
        header["bit_shift"]    ---> amount to shift right
        Every channel is listed one after another for each time point (fully
        interlaced)
        :return:
        """

        channels_to_read = self.settings['channels_to_read']

        with self._handle.file_object() as o:

            # Reads from position hl_bytes + header_length + start_read*bytes_per_read
            read_data_start = self.header.data_start + self.settings['start_read']*self.bytes_per_read
            read_data_end = self.header.data_start + self.settings['end_read']*self.bytes_per_read
            o.seek(read_data_start)
            chunk_size = self.min_chunk * self.reads_per_segment
            segment_dict = dict()

            def file_iterator():
                """
                Make a generator of file data, broken into multiples of the chunk_length

                :rtype : generator
                """

                at_end = False
                while True:
                    if at_end:
                        break
                    if o.tell()+chunk_size > read_data_end:
                        new_chunk_size = read_data_end-o.tell()
                        data_segment = o.read(new_chunk_size)
                        at_end = True
                    else:
                        data_segment = o.read(chunk_size)
                    if not data_segment:
                        break
                    yield data_segment

            for segment in file_iterator():
                # untwist data
                segment_in_decimal = self.convert_hex_to_float(segment)
                segment_rotated = self.untwist(segment_in_decimal)
                # downsample requested channels
                for channel in channels_to_read:
                    segment_dict[channel] = self.downsample_array(segment_rotated[channel])
                yield segment_dict

    def convert_hex_to_float(self, segment):
        bit_shift = self.header.bit_shift
        data_type = self.header.data_type
        converted_data = np.fromstring(segment, dtype=data_type)
        if bit_shift != 0:
            converted_data = np.right_shift(segment_in_decimal, bit_shift)
        return converted_data

    def untwist(self, serialized_data):
        total_ch = self.total_ch
        serialized_data.shape = (-1, total_ch)
        segment_rotated = serialized_data.swapaxes(0, 1)
        return segment_rotated

    def downsample_array(self, data):
        downsample = self.settings['downsample']
        data_length = len(data)
        if data_length % downsample != 0:
            new_length = data_length / downsample
            data = data[:new_length*downsample]
        new_data = data.reshape(-1, downsample)
        return new_data.mean(axis=1)

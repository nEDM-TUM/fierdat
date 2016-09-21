import os

import pynedm
THIS_PATH = os.path.dirname(os.path.abspath(__file__))


class LocalHandle(object):
    """
    Handle for reading a .dig file on the local disk

    """

    def __init__(self, file_name, file_path=THIS_PATH):
        self._file_path = file_path
        self.file_name = file_name
        self._file_address = self._make_file_address()
        self.file_object = self.open_file
        self.length = self._get_file_length()

    def _make_file_address(self):
        try:
            file_address = os.path.join(self._file_path, self.file_name)
        except TypeError:
            print("File path or file name invalid format")
            raise
        return file_address

    @property
    def open_file(self):
        """ return a file-like object that defines methods read('bytes') and tell(). NOTE: seek() not always
        supported

        If the file is downsampled from the server seek does not work
        """

        def ll(): return open(self._file_address)
        return ll

    def _get_file_length(self):
        # length = os.path.getsize(self._file_address)
        with self.file_object() as o:
            o.seek(0, 2)
            length = o.tell()
        return length


###
###
### Work on ServerHandle once data access is fully functional


class ServerHandle(object):
    """
    Handle for reading a .dig file

    """

    def __init__(self, file_name=None, doc_id=None, flags=None):
        self._doc_id = doc_id
        self._flag_dict = self.set_flag_dict(flags)
        self._file_url = self.set_file_url()
        self._file_address = self._make_file_address()
        self._server_dict = dict(_db="nedm%2Fmeasurements",
                                 # _server="http://10.155.59.88:5984",
                                 _server="http://10.155.59.15",
                                 _server2="http://db.nedm1",
                                 _password="clu$terXz",
                                 _username="nedm_user")
        self.file_object = self.open_file
        self.length = self._get_file_length()

    def set_flag_dict(self, flags):
        """
        Set the flags needed for handle_get on the server side.  In particular, set default flags where needed

        :param flags: currently available flags can be downsample; bytes; channels
        :return:
        """
        pass

    def set_file_url(self):
        """
        create file url in correct format using the flag dict

        :return:
        """

    @property
    def open_file(self):
        """ return a file-like object that defines methods read('bytes') and tell(). NOTE: seek() not always
        supported

        If the file is downsampled from the server seek does not work
        """

        # retrieve file from server
        if self._doc_id:
            po = pynedm.ProcessObject(uri=self._server_dict['_server2'],
                                      username=self._server_dict['_username'],
                                      password=self._server_dict['_password'],
                                      adb=self._server_dict['_db'])

            afile = po.open_file(self._doc_id, self._file_name)
            if self._downsample > 1:
                def ll():
                    t = afile.req.get(stream=True)
                    return t.raw
            elif not self._downsample or self._downsample == 1:
                def ll():
                    return afile
        return ll

    def _get_file_length(self):
        try:
            length = self.file_object().total_length
        except AttributeError:
            length = os.path.getsize(self._file_address)
        return length
import urllib.parse as parse
from general import isEmpty
import multipart
import json

def _readonly(self, *args, **kwargs):
    raise RuntimeError("Cannot modify ReadOnlyDictionary")


class FakeMultipartParser(multipart.MultipartParser):
    def __init__(
        self,
        stream,
        content_length=-1,
        disk_limit=2 ** 30,
        mem_limit=2 ** 20,
        memfile_limit=2 ** 18,
        buffer_size=2 ** 16,
        charset='latin1'
    ):
        """ Parse a application/x-www-form-urlencoded byte stream. This object is an iterator
            over the parts of the message.
            :param stream: A file-like stream. Must implement ``.read(size)``.
            :param boundary: The multipart boundary as a byte string.
            :param content_length: The maximum number of bytes to read.
        """

        self.stream = stream
        self.content_length = content_length
        self.disk_limit = disk_limit
        self.memfile_limit = memfile_limit
        self.mem_limit = min(mem_limit, self.disk_limit)
        self.buffer_size = min(buffer_size, self.mem_limit)
        self.charset = charset

        if self.buffer_size - 6 < 1:
            raise multipart.MultipartError("Boundary does not fit into buffer_size.")

        self._done = []
        self._part_iter = None

    def _iterparse(self):
        opts = {
            "buffer_size": self.buffer_size,
            "memfile_limit": self.memfile_limit,
            "charset": self.charset,
        }

        for key, value in parse.parse_qsl(self.stream.read(self.content_length)):
            part = multipart.MultipartPart(**opts)
            part.feed(multipart.to_bytes(F"Content-Disposition: form-data; name=\"{key}\"", self.charset), '\n')
            part.feed(b'', '\n')
            part.feed(multipart.to_bytes(value, self.charset), '\n')
            yield part

    def parts(self):
        """ Returns a list with all parts of the multipart message. """
        return list(self)


def process_request(content_type: bytes, rfile, content_length: int = -1, charset: str = 'UTF-8') -> multipart.MultipartParser:
    if isEmpty(content_type):
        return
    content_type = content_type.strip()
    req = None
    if content_type.split(';')[0] == 'multipart/form-data':
        i = 1
        boundary = content_type.split(';')[i].strip()
        while not boundary.startswith('boundary='):
            print(boundary)
            i += 1
            print(i)
            boundary = content_type.split(';')[i].strip()
        boundary = boundary.replace('boundary=', '', 1)

        req = multipart.MultipartParser(
            rfile,
            boundary,
            int(content_length),
            charset="UTF-8"
            )

    elif content_type == 'application/x-www-form-urlencoded':
        req = FakeMultipartParser(
            rfile,
            int(content_length),
            charset="UTF-8"
            )
    elif content_type == 'application/json':
        string = rfile.read(content_length).decode(charset)
        req = json.loads(string)
    else:
        try:
            print(rfile.read(content_length))
        except Exception as e:
            print(e)
        raise NotImplementedError("cant handle type " + content_type)
    return req

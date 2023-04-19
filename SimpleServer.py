import http.server as http
import os
import urllib.parse as parse
import ssl
import multiprocessing
import requests
from time import sleep
from typing import Any, List
import subprocess
import gzip
import zlib
import functools

import RequestParameters
from general import Settings
import importlib
try:
    import addons
except ImportError as ie:
    print("WARNING Unable to import addons, no custom functionality is available", ie)


def splitpath(path: str) -> list[str]:
    path = path.split('?')[0].split('#')[0]
    while '//' in path:
        path.replace('//', '/')
    pathlist_a = path.split('/')
    pathlist_b = []
    for item in pathlist_a:
        if item.strip() != '':
            pathlist_b.append(parse.unquote(item))
    return pathlist_b


@functools.cache
def parse_accept_encoding_header(header: str) -> List[str]:
    """
    Parse the given Accept-Encoding header string and return a list of
    encodings ordered by their qvalues weighting.

    Args:
        header (str): The Accept-Encoding header string.

    Returns:
        A list of encoding names ordered by their qvalues.

    Example:
        >>> header = 'gzip, deflate;q=0.5, br;q=0.1'
        >>> parse_accept_encoding(header)
        ['gzip', 'deflate', 'br']
    """
    encodings = [('identity', 0.01)]  # A list of encoding names with their qvalues
    if header:
        parts = header.split(',')
        for part in parts:
            encoding, _, params = part.strip().partition(';')
            qvalue = 1.0
            for param in params.split(';'):
                key, _, value = param.strip().partition('=')
                if key == 'q':
                    qvalue = float(value)
            encodings.append((encoding, qvalue))
    encodings.sort(key=lambda x: x[1], reverse=True)
    return [encoding for encoding, _ in encodings]


def compress_data(data: bytes, encodings: List[str] = ['identity',]) -> tuple[bytes, str]:
    """
    Compress the given bytes object using the specified encoding.

    Args:
        data (bytes): The bytes object to compress.
        encodings (List of str): The parsed Accept-Encoding header sent by the client.

    Returns:
        The compressed bytes object.
    """
    # Compress the data using the first available encoding
    for encoding in encodings:
        if encoding == 'gzip' or encoding == '*':
            return gzip.compress(data, compresslevel=9), 'gzip'
        elif encoding == 'compress':
            return zlib.compress(data, level=9), 'compress'
        elif encoding == 'deflate':
            compressobj = zlib.compressobj(level=9, method=zlib.DEFLATED, wbits=15)
            compressed = compressobj.compress(data) + compressobj.flush()  # compress the data using Deflate
            return compressed, 'deflate'
        elif encoding == 'identity':
            return data, 'identity'


class SimpleServer(http.SimpleHTTPRequestHandler):  # eine Klasse 'Server' erstellen, diese wird dem http modul übergeben
    pathlist = None
    __headers = None

    def handle_one_request(self, *args, **kargs):
        """
        Add custom headers and call the super method.

        Initializes the __headers attribute to an empty list, then calls
        the handle_one_request method of the superclass with the provided
        arguments and keyword arguments.

        Returns:
            The return value of the superclass's handle_one_request method.
        """
        self.__headers = []
        return super().handle_one_request(*args, **kargs)

    def send_header(self, keyword, value) -> None:
        """
        Add a custom header to the response.

        Overrides the send_header method of the superclass to add
        the specified header to the internal __headers list instead
        of writing it to the output stream.

        Args:
            keyword (str): The name of the header.
            value (str): The value of the header.
        """
        if self.__headers is None:
            self.__headers = []
        if value is not None:
            if isinstance(value, str):
                value = value.strip()
            if value != "":
                self.__headers.append((keyword, value))

    def end_headers(self):
        """
        Overridden method to write stored headers using super send_header method
        before calling super end_headers method.
        """
        if self.__headers is None:
            self.__headers = []
        for key, value in self.__headers:
            super().send_header(key, value)
        self.__headers = []
        return super().end_headers()

    def search_header(self, keyword, case_sensitive=True) -> Any:
        """
         search buffered headers for keyword
         returns value of key if it is found,
         if key exists multiple times, returns first value else None
        """
        if self.__headers is None:
            self.__headers = []
        if not case_sensitive:
            keyword = str(keyword).lower()
        for key, value in self.__headers:
            if case_sensitive:
                if key == keyword:
                    return value
            else:
                if str(key).lower() == keyword:
                    return value
        return None

    def get_path_segment_by_index(self, position: int) -> str:
        """
        Return the path segment at the given index.

        The index must be a non-negative integer. If the index is out of bounds, an empty string is returned.

        If the pathlist attribute is None or empty, it is initialized by calling the splitpath function with the current path.

        Raises:
            TypeError: If the position argument is not an integer.
        """
        if self.pathlist is None or not self.pathlist:
            self.pathlist = splitpath(self.path)
        if not isinstance(position, int):
            raise TypeError('position MUST be of type int')
        try:
            pathpart = self.pathlist[position]
        except IndexError:
            pathpart = ''
        return pathpart

    def version_string(self):
        """
        Return the server version, consisting of the string "Python-WebServer-Template" and the current git commit hash.

        If the commit hash is not available for any reason, return just the string "drive-desaster/Python-WebServer-Template".
        """
        if commit_hash is not None:
            return f"Python-WebServer-Template-{commit_hash}"
        else:
            return "drive-desaster/Python-WebServer-Template"

    def checkVersion(self):
        return True
        if self.request_version == 'HTTP/0.9':
            self.return_string("HTTP/0.9 is not supported", status=403)
            return False
        return True

    def return_string(self, string: str, content_type: str = 'text/plain', status: int = 200):
        if not isinstance(string, bytes):
            string = bytes(str(string), 'UTF-8')
        if self.search_header('Content-Type', case_sensitive=False) is None:
            self.send_header('Content-Type', content_type)
        if 'Accept-Encoding' in self.headers:
            string, encoding = compress_data(string, parse_accept_encoding_header(self.headers['Accept-Encoding']))
            self.send_header('Content-Encoding', encoding)
        self.send_header('Content-Length', len(string))
        self.do_HEAD(status)
        self.wfile.write(string)

    def return_file(self, path: str, *, status: int = 200,  error_status: int = 404):
        try:
            byte_file = open(path, 'rb')
            body = byte_file.read()
            byte_file.close()
            if self.search_header('Content-Type', case_sensitive=False) is None:
                self.send_header('Content-Type', self.guess_type(path))
        except OSError as e:
            status = error_status
            body = bytes(str(e), 'UTF-8')
            self.send_header('Content-Type', 'text/plain')
        if 'Accept-Encoding' in self.headers:
            body, encoding = compress_data(body, parse_accept_encoding_header(self.headers['Accept-Encoding']))
            self.send_header('Content-Encoding', encoding)
        self.send_header('Content-Length', len(body))
        self.do_HEAD(status)
        self.wfile.write(body)

    def do_HEAD(self, status: int = 501):
        """send header infomation back too client"""
        self.send_response(status)
        self.end_headers()

    def log_message(self, format_str, *args, logfile: str = None):
        """Log an arbitrary message.

        This is used by all other logging functions.  Override
        it if you have specific logging wishes.

        The first argument, FORMAT, is a format string for the
        message to be logged.  If the format string contains
        any % escapes requiring parameters, they should be
        specified as subsequent arguments (it's just like
        printf!).

        The client ip and current date/time are prefixed to
        every message.

        """
        if logfile is None:
            logfile = settings('logfile', 'log.log')
        logstring = (
            f"{self.address_string()} - - "
            f"[{self.log_date_time_string()}] "
            f"{format_str % args}\n"
        )
        with open(logfile, 'a') as log:
            log.write(logstring)
        print(logstring, end='')

    def preprocess(self):
        self.pathlist = splitpath(self.path)
        self.rawpath = self.path
        self.path = parse.unquote(self.path)

    def do_GET(self):
        """Handle GET requests coming to the server.

        - Checks the client version.
        - Preprocesses the request.
        - Handles specific paths:
            - robots.txt: Sends the file.
            - file/files: Sends the requested file.
            - favicon.ico/png/svg: Sends the favicon file.
            - .well-known: Sends the requested file from the server's well-known directory.
            - reload: Reloads the addons module.
            - css: Sends the requested CSS file. If the path is not specified, sends the default CSS file.
            - addons: Delegates to the addons module.
        - Raises an exception if an error occurs after returning the errormessage to the client.

        """
        try:
            if not self.checkVersion():
                return
            self.preprocess()
            path0 = self.get_path_segment_by_index(0).lower()
            if path0 == 'robots.txt':
                self.send_header('Cache-Controll', 'max-age=86400, public')
                self.return_file('robots.txt')
            elif path0 in ('file', 'files'):
                self.return_file(settings.get_path('fileroot', *self.pathlist[1:]))
            elif os.path.splitext(path0)[0] == 'favicon' or path0 in ('favicon', 'favicon.ico', 'favicon.png', 'favicon.svg'):
                self.send_header('Cache-Controll', 'max-age=86400, public')
                self.return_file(settings('favicon', 'favicon.ico'))
            elif path0 == '.well-known':
                self.return_file(settings.get_path('well-known', *self.pathlist[1:]))
            elif path0 == 'reload':
                importlib.reload(addons)
                self.return_string('sucess')
            elif path0 == 'css':
                if len(self.pathlist) == 1:
                    self.return_file(settings.get_path('css dir',  'default.css'))
                else:
                    self.return_file(settings.get_path('css dir', *self.pathlist[1:]))
            else:
                if 'addons' in globals() and hasattr(addons, 'get'):
                    addons.get(self)
                else:
                    self.do_HEAD(status=501)
        except Exception as e:
            self.return_string('ERROR: ' + str(e), status=500)
            raise e

    def do_POST(self):
        """Handle POST requests coming to the server.

        - Checks the clinet version.
        - Preprocesses the request.
        - Extracts the request parameters from the request.
        - Delegates to the addons module to process the request.
        - Raises an exception if an error occurs after returning the errormessage to the client.

        """
        try:
            if not self.checkVersion():
                return
            self.preprocess()
            if 'addons' in globals() and hasattr(addons, 'post'):
                self.postdata = RequestParameters.process_request(
                    self.headers['Content-Type'],
                    self.rfile,
                    int(self.headers['Content-Length'])
                    )
                return addons.post(self)
            else:
                return self.do_HEAD(status=501)
        except Exception as e:
            self.return_string(str(e), status=500)
            raise e
    
    def do_PUT(self):
        """
        handle PUT requests by calling the addons.put function
        """
        try:
            if not self.checkVersion():
                return
            self.preprocess()
            if 'addons' in globals() and hasattr(addons, 'put'):
                return addons.put(self)
            else:
                return self.do_HEAD(status=501)
        except Exception as e:
            self.return_string(str(e), status=500)
            raise e


class ForwardServer(http.SimpleHTTPRequestHandler):
    """
    A custom implementation of SimpleHTTPRequestHandler that forwards HTTP requests
    to their corresponding HTTPS endpoints.

    This class overrides the handle_one_request method to send a 308 Permanent Redirect
    response to the client with the HTTPS URL of the requested resource.

    Additionally, this class overrides the log_message method to log all incoming
    requests to a file specified in the settings.
    """
    def version_string(self):
        return SimpleServer.version_string(self)

    def handle_one_request(self):
        """
        Handle a single HTTP request.

        Overrides the handle_one_request method of the base class
        to redirect the client to the HTTPS version of the requested URL
        by sending an HTTP 308 Permanent Redirect status code with the new URL.
        If the request is invalid or malformed, it sends an appropriate error response.

        """
        try:
            self.raw_requestline = self.rfile.readline(65537)
            if len(self.raw_requestline) > 65536:
                self.requestline = ''
                self.request_version = ''
                self.command = ''
                self.send_error(http.HTTPStatus.REQUEST_URI_TOO_LONG)
                return
            if not self.raw_requestline:
                self.close_connection = True
                return
            if not self.parse_request():
                # An error code has been sent, just exit
                return
            self.close_connection = True
            self.send_response(308)
            address = 'https://' + settings('host', self.address_string()) + self.path
            self.send_header('Location', address)
            self.end_headers()
            self.wfile.flush()  # actually send the response if not already done.
        except TimeoutError as e:
            # read or write timed out. Discard this connection
            self.log_error("Request timed out: %r", e)
            self.close_connection = True
            return

    def log_message(self, format, *args):
        logfile = settings('forwardlogfile', 'forwardlog.log')
        with open(logfile, 'a') as log:
            log.write(
                f"{self.address_string()} - - "
                f"[{self.log_date_time_string()}] "
                f"{format_str % args}\n"
            )


def run_server(server, use_ssl: bool, port: int, host: str) -> None:
    # Create an HTTPServer bound to the specified host and port.
    httpd = http.HTTPServer((host, port), server)

    # If the ssl argument is True, create an SSL/TLS context and wrap the server's
    # socket in the context to make it an HTTPS server. Otherwise, leave it as an HTTP server.

    if use_ssl:
        context = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(settings['ssl key chain'], keyfile=settings['ssl key'])
        httpd.socket = context.wrap_socket(httpd.socket, server_side=True)

    # Start the HTTPServer and run it indefinitely.
    httpd.serve_forever()


def check_website(url: str, timeout: int, status: int):
    """
    Check if a website responds with the given status code. Return True if it does, False otherwise.

    Args:
        url: The URL to check.
        timeout: The maximum number of seconds to wait for a response.
        status: The HTTP status code to expect.

    Returns:
        True if the website responds with the given status code, False otherwise.
    """
    try:
        response = requests.get(url, timeout=timeout, allow_redirects=False)
        if response.status_code == status:
            # Website exists and is responding
            return True
        else:
            print("response: ", response.status_code)
            return False
    except (requests.exceptions.RequestException):
        # Website does not exist or is not responding
        print("no response")
        return False


def run_and_monitore_website(server, use_ssl: bool, port: int, check_target: str, expected_returncode: int, host: str):
    server_process = multiprocessing.Process(target=run_server, args=(server, use_ssl, port, host))
    server_process.start()
    sleep(5)
    while True:
        if not check_website(check_target, 1, expected_returncode):
            server_process.terminate()
            sleep(0.25)
            server_process = multiprocessing.Process(target=run_server, args=(server, use_ssl, port, host))
            sleep(0.25)
            server_process.start()
        sleep(1*60*60)


settings = Settings('settings.txt')
try:
    commit_hash = subprocess.check_output(
        ['git', 'rev-parse', '--short', 'HEAD']
    ).decode().strip()
except subprocess.CalledProcessError:
    commit_hash = None
if __name__ == '__main__':
    # If this code is executed directly (and not imported as a module),
    # check if the ssl key in the settings dictionary is set to True,
    # and start the appropriate server(s) accordingly.
    if not os.path.isdir(settings['fileroot']):
        os.mkdir(settings['fileroot'])

    if settings('ssl', False):
        server_process = multiprocessing.Process(target=run_server, args=(SimpleServer, True, settings('ssl port', 443)))
        forward_process = multiprocessing.Process(target=run_server, args=(ForwardServer, False, settings('port', 80)))
        server_process.start()
        forward_process.start()
        # Monitor the HTTPS server to make sure it's always running.
        watchdog1 = multiprocessing.Process(target=run_and_monitore_website, args=(SimpleServer, True, settings('ssl port', 443), F"https://{settings('host', '127.0.0.1')}:{settings('ssl port', 443)}", 200, settings('host', '127.0.0.1')))
        watchdog1.start()
        watchdog2 = multiprocessing.Process(target=run_and_monitore_website, args=(ForwardServer, False, settings('port', 80), F"http://{settings('host', '127.0.0.1')}:{settings('port', 80)}", 308, settings('host', '127.0.0.1')))
        watchdog2.start()
    else:
        run_and_monitore_website(SimpleServer, False, settings('port', 80), F"http://{settings('host', '127.0.0.1')}:{settings('port', 80)}", 200, settings('host', '127.0.0.1'))

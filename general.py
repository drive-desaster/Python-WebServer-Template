import os
from html import escape


class CaseInsensitiveDict(dict):
    """
    dictionary without case sensitive keys
    """
    @classmethod
    def _k(cls, key):
        if isinstance(key, str):
            key = key.strip()
            while '  ' in key:
                key = key.replace('  ', ' ')
            return key.lower()
        else:
            return key

    def __init__(self, *args, **kwargs):
        super(CaseInsensitiveDict, self).__init__(*args, **kwargs)
        self._convert_keys()
    def __getitem__(self, key):
        return super(CaseInsensitiveDict, self).__getitem__(self.__class__._k(key))
    def __setitem__(self, key, value):
        super(CaseInsensitiveDict, self).__setitem__(self.__class__._k(key), value)
    def __delitem__(self, key):
        return super(CaseInsensitiveDict, self).__delitem__(self.__class__._k(key))
    def __contains__(self, key):
        return super(CaseInsensitiveDict, self).__contains__(self.__class__._k(key))
    def has_key(self, key):
        return super(CaseInsensitiveDict, self).has_key(self.__class__._k(key))
    def pop(self, key, *args, **kwargs):
        return super(CaseInsensitiveDict, self).pop(self.__class__._k(key), *args, **kwargs)
    def get(self, key, *args, **kwargs):
        return super(CaseInsensitiveDict, self).get(self.__class__._k(key), *args, **kwargs)
    def setdefault(self, key, *args, **kwargs):
        return super(CaseInsensitiveDict, self).setdefault(self.__class__._k(key), *args, **kwargs)
    def update(self, E={}, **F):
        super(CaseInsensitiveDict, self).update(self.__class__(E))
        super(CaseInsensitiveDict, self).update(self.__class__(**F))
    def _convert_keys(self):
        for k in list(self.keys()):
            v = super(CaseInsensitiveDict, self).pop(k)
            self.__setitem__(k, v)


class Settings(CaseInsensitiveDict):
    """
    Setting class (Singleton unless clasified otherwise)
    supposed to be a dictionary of all settings
    """
    _instance = None
    def __new__(cls, *args, seperate_instance: bool = False, **kargs):
        if seperate_instance:
            return super().__new__(cls, **kargs)
        elif cls._instance == None:
            cls._instance = super().__new__(cls, **kargs)
            return cls._instance
        else:
            return cls._instance

    def __init__(self, *args, seperate_instance: bool = False, **kargs):
        super().__init__(self, **kargs)
        for arg in args:
            if isinstance(arg, str):
                self.from_string(arg, may_be_file=True)
            elif isinstance(arg, dict):
                for key, value in arg.items():
                    self[key] = value
            elif isinstance(arg, (list, tuple)):
                if len(arg) == 2:
                    self[arg[0]] = arg[1]
                else:
                    raise ValueError("arguments given as list should be length of two")
            else:
                raise TypeError("arguments should be of type str, list, tuple or dict")

    def from_file(self, filepath: str):
        with open(filepath, 'r') as file:
            for line in file.readlines():
                line = line.replace('\n', '').replace('\r', '').strip()
                if line.startswith('include '):
                    self.from_string(line[8:], is_file=True)
                else:
                    self.from_string(line)

    def from_string(self, string: str, /, *, may_be_file: bool = False, is_file: bool = False):
        if string.strip() == "":
            return
        elif is_file:
            self.from_file(string)
        elif may_be_file and os.path.isfile(string):
            self.from_file(string)
        else:
            tmp = ''
            flag = False
            for char in string:
                if char == '\\':
                    flag = True
                    tmp += char
                elif flag:
                    tmp += char
                    flag = False
                elif char == '#':
                    break
                else:
                    tmp += char
            string = tmp
            del flag
            del tmp
            key, value = string.split('=')
            key = key.strip()
            value = value.strip()
            if key.strip() != "" and key[0] in ('\'', '\"') and key[-1] == key[0]:
                key = key[1:-1]
            if value.strip() != "" and value[0] in ('\'', '\"') and value[-1] == value[0]:
                value = value[1:-1]

            self[key] = type_string(value)

    def get_path(self, key: str, *path):
        start = os.path.realpath(self[key])
        target = os.path.join(start, *path)
        target = os.path.realpath(target)
        if target.startswith(start):
            return target
        else:
            raise PermissionError(target + ' outside of provided settings dir: ' + start)

    def __call__(self, key, /, default=None):
        if key in self:
            return self[key]
        else:
            return default


def isEmpty(string:str)->bool:
    if string == None:
        return True
    elif len(string.strip()) == 0:
        return True
    else:
        return False


def path_from_settings(key: str, *path):
    return Settings().get_path(key, *path)


def type_string(value: str) -> str:
    value = value.strip()
    if value.lower() == 'true':
        return True
    elif value.lower() == 'false':
        return False
    try:
        result = int(value)
    except:
        try:
            result = float(value.replace(',', '.'))
        except:
            try:
                result = str(value)
            except:
                result = value
    return result


class html_compiler:
    title = ""
    lang = "en_US"
    favicon = "/favicon"
    _body = ""
    footer = ""
    header = "<h1>%(title)s<h1>"

    def __init__(self, server, status: int = 200, **send_headers):
        self.server = server
        self.settings = Settings()
        self.css = []
        for a, b in send_headers.items():
            self.server.send_header(a, b)
        self.status = status

    def add_css(self, name):
        self.css.append(name)

    def append_body(self, string, do_escape=False):
        if do_escape:
            string = escape(string)
        self._body += string

    def __str__(self):
        html = F"<!DOCTYPE html>\n<html lang=\"{escape(self.lang)}\">\n"
        self.server.send_header('charset', 'UTF-8')
        self.server.send_header('Charset', 'UTF-8')
        html += F"""<head>
        <meta charset=\"UTF-8\">
        <link rel=\"icon\" href=\"{escape(self.favicon)}\">
        <link rel=\"shortcut icon\" href=\"{escape(self.favicon)}\">
        <link rel=\"stylesheet\" href=\"/css\">"""
        for css in self.css:
            html += "<link rel=\"stylesheet\" href=\"" + escape(os.path.join("/css", css)) + "\">"
        html += F"<title>{Settings()('Servername', 'Python-WebServer-Template')} - {escape(self.title)}</title></head><body>"
        if self.header != "":
            html += "<header>" + self.header % {'title': escape(self.title), 'location': escape(self.server.path)} + "</header>"
        html += self._body
        if self.footer != "":
            html += "<footer>" + self.footer + "</footer>"
        html += "</body></html>"
        return html

    def send(self):
        html = str(self)
        self.server.return_string(html, content_type='text/html', status=self.status)

    def set_status(self, status: int):
        self.status = int(status)

    def __call__(self, body: str = "", status: int = None):
        self.append_body(body)
        if status is not None:
            self.set_status(status)
        return self.send()

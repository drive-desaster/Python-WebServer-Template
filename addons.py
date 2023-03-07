import os
from general import Settings, html_compiler
import datetime
import hashlib
import uuid
import time

settings = Settings()


def post(server):
    path0 = server.get_path_segment_by_index(0)
    if path0 == 'fileserver':
        return fileserver_post(server)
    else:
        server.do_HEAD()


def get(server):
    path0 = server.get_path_segment_by_index(0)
    if path0 == 'fileserver':
        return fileserver_get(server)
    elif path0.lower() in ('', 'index', 'index.html'):
        html = html_compiler(server)
        html.title = "Index"
        html.header = "<h1>Index of all available Services</h1>"
        html.append_body("<br>")
        html.append_body("<a href=\"/fileserver\">Fileserver</a><br>")
        html()
        return
    else:
        server.do_HEAD(404)


def fileserver_post(server):
    path0 = server.get_path_segment_by_index(1).lower()
    path1 = server.get_path_segment_by_index(2).lower()
    if path0 == 'upload':
        if path1 == 'v1':
            if not os.path.isdir(settings.get_path("fileroot", "userfiles")):
                os.mkdir(settings.get_path("fileroot", "userfiles"))
            post = server.postdata.get('file')
            filename = uuid.uuid4().hex + os.path.splitext(post.filename)[-1]
            path = settings.get_path("fileroot", "userfiles", filename)
            with open(path, 'wb') as byte_file:
                byte_file.write(post.raw)
            html = html_compiler(server)
            html.title = "Upload sucess"
            html.append_body("<p>your file was uploaded sucessfully, you can reach it from <a href=\"")
            html.append_body(os.path.join("/files/userfiles/", filename), True)
            html.append_body("\">")
            html.append_body('http://' + settings('host', 'localhost') + os.path.join("/files/userfiles/", filename), True)
            html.append_body("</a>")
            html()
            return
    return get(server)


def fileserver_get(server):
    path0 = server.get_path_segment_by_index(1).lower()
    if path0 in ('index', '', 'index.html', 'upload'):
        html = html_compiler(server)
        html.title = "Chose a File to upload"
        html.header = "<h1>Files</h1>"
        html.append_body("<form action=\"/fileserver/upload/v1\" method=\"POST\" enctype=\"multipart/form-data\">")
        html.append_body(" <label for=\"file\">File to Upload:</label><br>")
        html.append_body(" <input type=\"file\" id=\"file\" name=\"file\"><br><br>")
        html.append_body(" <input type=\"submit\" value=\"Upload\">")
        html.append_body("</form>")
        html()
    else:
        server.do_HEAD(404)

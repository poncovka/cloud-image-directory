import json
import os
import pathlib

from pathlib import Path


exception_not_connected = Exception("Client is not connected to s3 bucket")
exception_already_connected = Exception("Client is already connected to s3 bucket")
exception_path_not_existing = Exception(
    "The given path to the filesystem doesn't exist"
)
exception_not_implemented = Exception("Not implemented")


class Connection:
    def connect(self):
        pass

    def get_filenames(self):
        pass

    def get_content(self, filename):
        pass

    def put_content(self, content, filename):
        pass


class DataEntry:
    filename = ""
    content = None

    def __init__(self, filename, content):
        self.filename = filename
        self.content = content

    def is_raw(self) -> bool:
        return self.filename.__contains__("raw/")

    def is_provided_by(self, input: str) -> bool:
        return self.filename.__contains__(input + "/")


class ConnectionFS(Connection):
    origin_path: str = ""
    arg_files: list[str] = []

    def __init__(self, origin_path: str, arg_files: list[str]):
        self.arg_files = arg_files
        self.origin_path = origin_path
        if self.origin_path == "":
            self.origin_path = os.getcwd()

    def connect(self):
        pass

    def get_filenames(self) -> list[DataEntry]:
        if len(self.arg_files) != 0:
            result = []
            for file in self.arg_files:
                result.append(DataEntry(file, None))
            return result
        return self.__list_files(self.origin_path)

    def __list_files(self, dir: str) -> list[DataEntry]:
        data_files = []
        p = pathlib.Path(dir)
        if p.exists():
            for child in p.glob("**/*.json"):
                data_files.append(DataEntry(str(child.resolve()), None))
        else:
            raise exception_path_not_existing
        return data_files

    def get_content(self, data) -> DataEntry:
        content: str = ""
        content = Path(data.filename).read_text()
        if content == "":
            content = "{}"
        content = json.loads(content)
        return DataEntry(data.filename, content)

    def put_content(self, data):
        json_data = json.dumps(data.content)
        tmp = data.filename.split("/")
        tmp = tmp[: len(tmp) - 1]
        tmp = "/".join(tmp)
        os.makedirs(tmp, exist_ok=True)
        Path(data.filename).write_text(json_data + "\n")

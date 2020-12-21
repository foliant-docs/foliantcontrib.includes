import os


def rel_name(path: str):
    return os.path.join(os.path.dirname(__file__), path)


def data_file_content(path: str) -> str:
    '''read data file by path relative to this module and return its contents'''
    with open(rel_name(path), encoding='utf8') as f:
        return f.read()

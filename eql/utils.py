"""Generic utility functions for analytic_engines."""
import codecs
import gzip
import io
import json
import os
import sys

# Lazy load dynamic loaders
try:
    import yaml
except ImportError:
    yaml = None

try:
    import toml
except ImportError:
    toml = None

# Python2 and Python3 compatible type checking
unicode_t = type(u"")
long_t = type(int(1e100))

if unicode_t == str:
    strings = str,
    to_unicode = str
else:
    strings = str, unicode_t
    to_unicode = unicode_t

if long_t != int:
    numbers = (int, float, long_t)
else:
    numbers = int, float


def is_string(s):
    """Check if a python object is a unicode or ascii string."""
    return isinstance(s, strings)


def is_number(s):
    """Check if a python object is a unicode or ascii string."""
    return isinstance(s, numbers)


def str_presenter(dumper, data):
    """Patch YAML so that it folds the long query strings."""
    if len(data.splitlines()) > 1:  # check for multiline string
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)


def get_type_converter(items):
    """Get a python callback function that can convert None to observed typed values."""
    items = iter(items)

    def get_empty(v):
        """Get the empty version of a value."""
        return None if v is None else type(v)()

    def default_converter(_):
        """Convert things to None when no other options available."""
        return None

    try:
        first = next(items)
    except StopIteration:
        return default_converter

    if not isinstance(first, (tuple, list)):
        empty = get_empty(first)

        if empty is None:
            for item in items:
                if item is not None:
                    empty = get_empty(item)
                    break

        return lambda x: x or empty

    else:
        empty_values = [get_empty(f) for f in first]

        for item_tuple in items:
            for i, item in enumerate(item_tuple):
                if item is not None and empty_values[i] is None:
                    # Update it with an empty value
                    empty_values[i] = type(item)()

            if all(v is not None for v in empty_values):
                break

        def convert_types(tup):
            """Take a tuple and convert each key to make sure it's not None."""
            return tuple(tup[i] or empty_i for i, empty_i in enumerate(empty_values))

        return convert_types


if yaml is not None:
    yaml.add_representer(str, str_presenter)
    if str != unicode_t:
        yaml.add_representer(unicode_t, str_presenter)


def load_dump(filename):
    """Load dump."""
    extension = filename.split('.').pop().lower()

    with open(filename) as f:
        if extension in ('yml', 'yaml'):
            assert yaml, "PyYAML module not found"
            return yaml.safe_load(f)
        elif extension == 'toml':
            assert toml, "TOML module not found"
            return toml.load(f)
        elif extension == 'json':
            return json.load(f)

    raise ValueError("Unsupported file type {}".format(extension))


def save_dump(contents, filename):
    """Save dump."""
    extension = filename.split('.').pop().lower()

    with open(filename, 'w') as f:
        if extension in ('yml', 'yaml'):
            assert yaml, "PyYAML module not found"
            yaml.dump(contents, stream=f, explicit_start=True, allow_unicode=True, default_flow_style=False, indent=2)
        elif extension == 'json':
            json.dump(contents, fp=f, indent=2, sort_keys=True)
        elif extension == 'toml':
            assert toml, "TOML module not found"
            toml.dump(contents, f)
        else:
            raise ValueError("Unsupported file type {}".format(extension))


def stream_json_lines(json_input):
    """Iterate over json lines to get Events."""
    for line in json_input:
        line = line.strip()
        if line.strip():
            yield json.loads(line)


def stream_file_events(file_path, file_format=None, encoding="utf8"):
    """Stream a file as JSON.

    :param str file_path: Path to the file
    :param str file_format: One of json.jgz, json.gz
    :param str encoding: File encoding (ascii, utf8, utf16, etc.)
    """
    gz_ext = '.gz'

    if not file_format:
        base_path, file_format = os.path.splitext(file_path)
        if file_format == gz_ext:
            base_path, file_format = os.path.splitext(file_path[:-len(gz_ext)])
            file_format += gz_ext

    if file_format.endswith(gz_ext):
        file_format = file_format[:-len(gz_ext)]
        decoder = codecs.getreader(encoding)
        handle = decoder(gzip.open(file_path, 'rb'))
    else:
        handle = io.open(file_path, encoding=encoding)

    with handle:
        for event in stream_events(handle, file_format=file_format):
            yield event


def stream_stdin_events(file_format=None):
    """Stream a file as JSON.

    :param str file_format: One of json.jgz, json.gz
    """
    gz_ext = '.gz'
    file_format = file_format or 'jsonl'
    f = sys.stdin

    if file_format.endswith(gz_ext):
        file_format = file_format[:-len(gz_ext)]
        f = gzip.GzipFile(mode='r', fileobj=sys.stdin)

    for event in stream_events(f, file_format):
        yield event


def stream_events(fileobj, file_format="json"):
    """Stream events from a file handle.

    :param file fileobj: Handle to a file or stream
    :param str file_format: JSON or JSONL
    """
    file_format = file_format.lstrip(".")

    if file_format == 'jsonl':
        return stream_json_lines(fileobj)
    elif file_format == 'json':
        return json.load(fileobj)

    raise NotImplementedError("Unexpected format: {}".format(file_format))
''' ===========================================================================

JSON for IronPython via .NET's JavaScriptSerializer (System.Web.Extensions),
since the json module isn't reliably available in ComicRack's IronPython.

loads() returns plain Python dicts / lists / unicode / int / float / bool /
None. dumps() accepts the same.

=========================================================================== '''
import clr

clr.AddReference('System.Web.Extensions')
from System.Web.Script.Serialization import JavaScriptSerializer
clr.AddReference('System')
from System import Int32, Decimal, Array, Object, String
from System.Collections.Generic import Dictionary


def _serializer():
    s = JavaScriptSerializer()
    # a page of 500 Komga books with metadata is a few MB; the default
    # limit (2M characters) is too small
    s.MaxJsonLength = Int32.MaxValue
    return s


def _to_python(value):
    if value is None:
        return None
    if isinstance(value, (bool, int, long, float, unicode, str)):
        return value
    if isinstance(value, Decimal):
        f = float(value)
        return int(f) if f == int(f) and abs(f) < 2 ** 53 else f
    if hasattr(value, 'Keys') and hasattr(value, 'Values'):
        return dict((unicode(k), _to_python(value[k])) for k in value.Keys)
    if isinstance(value, Array) or hasattr(value, '__iter__'):
        return [_to_python(v) for v in value]
    return value


def _to_dotnet(value):
    if isinstance(value, dict):
        d = Dictionary[String, Object]()
        for k, v in value.items():
            d[unicode(k)] = _to_dotnet(v)
        return d
    if isinstance(value, (list, tuple)):
        return Array[Object]([_to_dotnet(v) for v in value])
    return value


def loads(text):
    '''Parses JSON text into Python values.'''
    if text is None or not text.strip():
        return None
    return _to_python(_serializer().DeserializeObject(text))


def dumps(value):
    '''Serialises Python values (dict/list/str/number/bool/None) to JSON.'''
    return _serializer().Serialize(_to_dotnet(value))

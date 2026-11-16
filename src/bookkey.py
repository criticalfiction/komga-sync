''' ===========================================================================

How a book is matched between ComicRack and Komga: by its file path, made
comparable. Both run on the same PC and see the same paths, so:
  - forward slashes become backslashes
  - case is ignored (Windows paths are case-insensitive)
  - Unicode is normalised to NFC, so an accented letter stored as one
    character and as letter + accent compare equal

=========================================================================== '''
import clr

clr.AddReference('System')
from System.Text import NormalizationForm


def path_key(path):
    '''The comparable form of a file path ('' for no path).'''
    if not path:
        return ''
    # IronPython strings are .NET strings, so .NET's methods work on them.
    # (Don't wrap in String(...): that decodes the text as bytes and fails
    # on accented characters.)
    text = path.Normalize(NormalizationForm.FormC)
    return text.Replace('/', '\\').ToLowerInvariant()

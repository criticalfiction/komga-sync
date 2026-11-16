'''
Static checks on src/*.py for problems that only show up inside ComicRack:
  - non-ASCII characters / UTF-8 BOM (IronPython 2 rejects them without an
    encoding line)
  - a class attribute later redefined as a method/property (the method
    silently replaces the value)
  - syntax errors (after converting the two Python 2 forms we use)
Real IronPython behaviour is tested by run_ironpython.ps1.
Exit code 1 if anything is found.
'''
import ast
import glob
import re
import sys

problems = 0
for path in sorted(glob.glob('src/*.py')):
    raw = open(path, 'rb').read()
    if raw.startswith(b'\xef\xbb\xbf'):
        print('%s: UTF-8 BOM' % path)
        problems += 1
    for i, line in enumerate(raw.decode('utf-8', 'replace').splitlines(), 1):
        if any(ord(c) > 127 for c in line):
            print('%s:%d: non-ASCII character' % (path, i))
            problems += 1

    # make py2 syntax parseable by py3: 'except X, e:' and 'print x'
    src = raw.decode('utf-8', 'replace')
    src = re.sub(r'except\s+([\w.]+)\s*,\s*(\w+)\s*:', r'except \1 as \2:', src)
    src = re.sub(r'^(\s*)print (.+)$', r'\1print(\2)', src, flags=re.M)
    try:
        tree = ast.parse(src)
    except SyntaxError as ex:
        print('%s:%s: syntax error: %s' % (path, ex.lineno, ex.msg))
        problems += 1
        continue
    for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        assigned = {}
        for node in cls.body:
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        assigned[t.id] = node.lineno
            elif isinstance(node, ast.FunctionDef) and node.name in assigned:
                print('%s: class %s: "%s" assigned line %d, redefined line %d'
                      % (path, cls.name, node.name, assigned[node.name], node.lineno))
                problems += 1

print('source problems: %d' % problems)
sys.exit(1 if problems else 0)

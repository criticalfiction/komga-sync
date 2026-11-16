#!/usr/bin/env python
'''
Builds the Komga Sync ComicRack plugin: zips the files in src/ (flat, as
ComicRack expects) into build/KomgaSync-<version>.crplugin.

Usage:  python build.py
'''
import os
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(ROOT, 'src')
BUILD_DIR = os.path.join(ROOT, 'build')


def read_package_ini():
    '''Name/Version from src/Package.ini (key = value lines, no sections).'''
    meta = {'Name': 'Komga Sync', 'Version': '0.0.0'}
    with open(os.path.join(SRC_DIR, 'Package.ini')) as f:
        for line in f:
            if '=' in line and not line.strip().startswith('#'):
                key, val = [p.strip() for p in line.split('=', 1)]
                if key in meta:
                    meta[key] = val
    return meta


def build_plugin():
    meta = read_package_ini()
    if not os.path.isdir(BUILD_DIR):
        os.makedirs(BUILD_DIR)
    out = os.path.join(BUILD_DIR, '%s-%s.crplugin'
                       % (meta['Name'].replace(' ', ''), meta['Version']))
    # only replace the plugin itself; build/ also holds test screenshots
    for old in os.listdir(BUILD_DIR):
        if old.endswith('.crplugin'):
            os.remove(os.path.join(BUILD_DIR, old))

    files = sorted(f for f in os.listdir(SRC_DIR)
                   if os.path.isfile(os.path.join(SRC_DIR, f))
                   and not f.startswith('.')
                   and not f.endswith(('.pyc', '.pyo')))
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
        for name in files:
            zf.write(os.path.join(SRC_DIR, name), name)

    print('Built: %s' % out)
    print('  Version: %s, files: %d, size: %d bytes'
          % (meta['Version'], len(files), os.path.getsize(out)))
    return out


if __name__ == '__main__':
    build_plugin()

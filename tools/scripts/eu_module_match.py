#!/usr/bin/env python3
"""Strict relocation-based EU module candidates. Analysis never grants C credit."""
import argparse
import hashlib
import json
import pathlib
import re
import struct

EU_SHA1 = '6e80a65cca65236e405940c880b144d77f3f4f08'
BASE = 0x08000000
FLAGS = '-mthumb-interwork -Wimplicit -Wparentheses -O2 -fhex-asm -fprologue-bugfix'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Elf:
    """Minimal ELF32 little-endian ARM REL reader; no external dependencies."""
    def __init__(self, path):
        self.raw = pathlib.Path(path).read_bytes()
        b = self.raw
        if b[:6] != b'\x7fELF\x01\x01' or struct.unpack_from('<H', b, 18)[0] != 40:
            raise ValueError('expected ELF32 little-endian ARM')
        off = struct.unpack_from('<I', b, 32)[0]
        ent, num, names = struct.unpack_from('<HHH', b, 46)
        self.sections = [struct.unpack_from('<10I', b, off+i*ent) for i in range(num)]
        strings = self.data(self.sections[names])
        self.names = [self.string(strings, s[0]) for s in self.sections]
        self.text_index = self.names.index('.text')
        self.text = self.data(self.sections[self.text_index])
        sym = self.sections[self.names.index('.symtab')]
        strings = self.data(self.sections[sym[6]])
        self.symbols = []
        for off in range(sym[4], sym[4]+sym[5], sym[9]):
            n, value, size, info, other, section = struct.unpack_from('<IIIBBH', b, off)
            self.symbols.append(dict(name=self.string(strings, n), value=value,
                                     size=size, info=info, section=section))
        self.relocs = []
        for section in self.sections:
            if section[1] == 4 and section[7] == self.text_index:
                raise ValueError('RELA unsupported')
            if section[1] != 9 or section[7] != self.text_index:
                continue
            for off in range(section[4], section[4]+section[5], section[9]):
                site, info = struct.unpack_from('<II', b, off)
                self.relocs.append(dict(offset=site, type=info & 255,
                                        symbol=self.symbols[info >> 8]))

    def data(self, section):
        return self.raw[section[4]:section[4]+section[5]]

    @staticmethod
    def string(strings, off):
        return strings[off:strings.index(b'\0', off)].decode()


def thumb_displacement(data, offset=0):
    hi, lo = struct.unpack_from('<HH', data, offset)
    if hi & 0xF800 != 0xF000 or lo & 0xF800 != 0xF800:
        raise ValueError('relocation site is not ARMv4T Thumb BL')
    value = ((hi & 0x7FF) << 12) | ((lo & 0x7FF) << 1)
    return value - (1 << 23) if value & (1 << 22) else value


def thumb_target(data, offset, address):
    return address + 4 + thumb_displacement(data, offset)


def relocation_mask(text, relocs):
    mask = bytearray(b'\xff' * len(text))
    for r in relocs:
        off, kind = r['offset'], r['type']
        if kind == 40:  # R_ARM_V4BX is a marker; instruction remains fixed.
            continue
        if kind not in (2, 10):
            raise ValueError('unsupported relocation type %s' % kind)
        if off < 0 or off + 4 > len(text):
            raise ValueError('relocation outside text')
        if kind == 10 and thumb_displacement(text, off) != -4:
            raise ValueError('nonstandard Thumb BL object addend')
        mask[off:off+4] = b'\0' * 4
    return mask


def unique_sites(text, mask, rom, end):
    runs = list(re.finditer(b'\xff+', mask))
    run = max(runs, key=lambda m: m.end()-m.start(), default=None)
    if run is None or run.end()-run.start() < 6 or sum(bool(b) for b in mask) < 16:
        return []
    a, b = run.span()
    fixed = [i for i, m in enumerate(mask) if m]
    sites = []
    pos = rom.find(text[a:b], 0, end)
    while pos >= 0:
        start = pos-a
        if start >= 0 and start % 4 == 0 and start+len(text) <= end:
            if all(rom[start+i] == text[i] for i in fixed):
                sites.append(BASE+start)
        pos = rom.find(text[a:b], pos+1, end)
    return sites


def bind_relocations(elf, rom, start):
    bindings, evidence = {}, []
    for r in elf.relocs:
        off, kind, symbol = r['offset'], r['type'], r['symbol']
        if kind == 40:
            continue
        actual = rom[start-BASE+off:start-BASE+off+4]
        if kind == 2:
            addend = struct.unpack_from('<I', elf.text, off)[0]
            value = (struct.unpack('<I', actual)[0]-addend) & 0xFFFFFFFF
        elif kind == 10:
            addend = thumb_displacement(elf.text, off)
            if addend != -4:
                raise ValueError('nonstandard Thumb BL object addend')
            value = thumb_target(actual, 0, start+off) | 1
        else:
            raise ValueError('unsupported relocation')
        name = symbol['name']
        if symbol['section'] == 0:
            if not name:
                raise ValueError('unnamed undefined symbol')
            if name in bindings and bindings[name] != value:
                raise ValueError('conflicting external binding: '+name)
            bindings[name] = value
        else:
            if symbol['section'] == elf.text_index:
                expected = start + symbol['value']
            elif symbol['section'] == 0xFFF1:
                expected = symbol['value']
            else:
                raise ValueError('internal relocation outside .text')
            if kind == 10:
                expected |= 1
            if value != expected:
                raise ValueError('internal symbol relocation differs: '+name)
        evidence.append(dict(offset=off, type=kind, symbol=name, addend=addend,
                             inferred_value=value, external=symbol['section'] == 0))
    return bindings, evidence


def validate_manifest(root, manifest, directory=None):
    stale = []
    expected_flags = {
        'game': FLAGS.split(),
        'm4a': FLAGS.replace(' -fprologue-bugfix', '').split(),
        'preprocessor': ['-nostdinc', '-I', 'include', '-I', '<compiler>/include', '-iquote', 'include'],
        'assembler': ['-mcpu=arm7tdmi', '-I', 'include'],
    }
    if manifest.get('compiler_flags') != expected_flags:
        stale.append('missing or unexpected compiler_flags')
    recipe = root/'tools/scripts/metadata_build.py'
    if not recipe.is_file() or manifest.get('builder_sha256') != digest(recipe):
        stale.append('missing or stale builder_sha256')
    for name, expected in manifest.get('inputs_sha256', {}).items():
        path = root / name.replace('\\', '/')
        if not path.is_file() or digest(path) != expected:
            stale.append(name)
    if not manifest.get('inputs_sha256'):
        stale.append('missing inputs_sha256')
    compiler = pathlib.Path(manifest.get('compiler_dir', ''))
    for name, expected in manifest.get('compiler_sha256', {}).items():
        path = compiler / 'bin' / name
        if not path.is_file() or digest(path) != expected:
            stale.append('compiler/'+name)
    if not manifest.get('compiler_sha256'):
        stale.append('missing compiler_sha256')
    headers = manifest.get('compiler_headers_sha256', {})
    if not headers:
        stale.append('missing compiler_headers_sha256')
    for name, expected in headers.items():
        path = compiler/'include'/name.replace('\\', '/')
        if not path.is_file() or digest(path) != expected:
            stale.append('compiler header/'+name)
    objects = manifest.get('objects_sha256', {})
    if not objects:
        stale.append('missing objects_sha256')
    for module in manifest.get('modules', []):
        name = module['object'].replace('\\', '/')
        path = (directory/pathlib.Path(*pathlib.PurePosixPath(name).parts[2:])) if directory else root/name
        if name not in objects or not path.is_file() or digest(path) != objects[name]:
            stale.append('object/'+name)
    return stale


def analyze(root, directory, rom_path):
    manifest_path = directory/'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    rom = rom_path.read_bytes()
    sha1 = hashlib.sha1(rom).hexdigest()
    if sha1 != EU_SHA1:
        raise ValueError('EU ROM SHA1 mismatch')
    stale = validate_manifest(root, manifest, directory)
    if stale:
        raise ValueError('stale metadata inputs: '+', '.join(stale))
    report = dict(schema_version=1, analysis_only=True, rom_match_verified=False,
                  matching_c_credit=False, eu_sha1=sha1,
                  source_manifest_sha256=digest(manifest_path),
                  inputs_sha256=manifest['inputs_sha256'],
                  compiler_sha256=manifest['compiler_sha256'],
                  compiler_flags=manifest['compiler_flags'],
                  builder_sha256=manifest['builder_sha256'],
                  compiler_headers_sha256=manifest['compiler_headers_sha256'],
                  objects_sha256=manifest['objects_sha256'],
                  flags_recipe_sha256=digest(root/'tools/scripts/metadata_build.py'),
                  candidates=[], rejected=[])
    for module in manifest['modules']:
        source = module['source']
        if not source.startswith('src/'):
            continue
        obj = source[:-2]+'.o'
        path = directory/pathlib.Path(obj)
        try:
            elf = Elf(path)
            mask = relocation_mask(elf.text, elf.relocs)
            sites = unique_sites(elf.text, mask, rom, 0x52B30)
            if len(sites) != 1:
                raise ValueError('ambiguous or absent full masked match (%d sites)' % len(sites))
            start = sites[0]
            bindings, relocs = bind_relocations(elf, rom, start)
            report['candidates'].append(dict(object=obj, source=source, eu_start=start,
                size=len(elf.text), bindings=bindings, relocations=relocs,
                object_sha256=digest(path), fixed_bytes=sum(bool(b) for b in mask),
                text_symbols={s['name']:s['value'] for s in elf.symbols
                    if s['section'] == elf.text_index and s['name'] and not s['name'].startswith(('$', '.'))}))
        except ValueError as error:
            report['rejected'].append(dict(object=obj, reason=str(error)))
    report['candidate_bytes'] = sum(c['size'] for c in report['candidates'])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[2])
    parser.add_argument('--metadata-dir', type=pathlib.Path)
    parser.add_argument('--rom', type=pathlib.Path, required=True)
    parser.add_argument('--out', type=pathlib.Path, default=pathlib.Path('tmp/eu-module-candidates.json'))
    args = parser.parse_args()
    report = analyze(args.root, args.metadata_dir or args.root/'build/metadata', args.rom)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2)+'\n')
    print('%d candidate modules, %d bytes; analysis only, no C credit' % (len(report['candidates']), report['candidate_bytes']))


if __name__ == '__main__':
    main()

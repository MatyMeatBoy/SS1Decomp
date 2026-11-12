#!/usr/bin/env python3
"""Reproduce owned EU ROM with verified shared C and explicitly pending gaps."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import struct
import subprocess

EXPECTED_SHA1 = '6e80a65cca65236e405940c880b144d77f3f4f08'
ROM_SIZE = 0x800000
CODE_END = 0x52B30
GAME_FLAGS = '-mthumb-interwork -Wimplicit -Wparentheses -O2 -fhex-asm -fprologue-bugfix'.split()
EXPECTED_FLAGS = {'game': GAME_FLAGS, 'm4a': GAME_FLAGS[:-1],
                  'preprocessor': ['-nostdinc', '-I', 'include', '-I', '<compiler>/include', '-iquote', 'include'],
                  'assembler': ['-mcpu=arm7tdmi', '-I', 'include']}


def verify_metadata_provenance(manifest, recipe=None):
    required = ('compiler_flags', 'builder_sha256', 'compiler_headers_sha256', 'objects_sha256', 'compiler_sha256')
    if any(not manifest.get(name) for name in required):
        raise ValueError('metadata lacks required compiler/object provenance; rebuild it')
    if manifest['compiler_flags'] != EXPECTED_FLAGS:
        raise ValueError('metadata compiler flags differ from reviewed matching recipe')
    if recipe is None or not recipe.is_file() or hashlib.sha256(recipe.read_bytes()).hexdigest() != manifest['builder_sha256']:
        raise ValueError('stale metadata builder recipe provenance')
    compiler = Path(manifest['compiler_dir'])
    for table, base in [('compiler_sha256', compiler / 'bin'), ('compiler_headers_sha256', compiler / 'include')]:
        for name, expected in manifest[table].items():
            path = base / name.replace('\\', '/')
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError('stale compiler provenance: ' + name)


def validate_rom(data):
    if len(data) != ROM_SIZE or data[0xAC:0xB0] != b'AHUP':
        raise ValueError('EU profile requires the 8 MiB AHUP ROM')
    if hashlib.sha1(data).hexdigest() != EXPECTED_SHA1:
        raise ValueError('EU ROM SHA1 does not match the supported original')


def verify_rebuild(original, rebuilt, credited_bytes):
    validate_rom(original)
    if rebuilt != original or hashlib.sha1(rebuilt).hexdigest() != EXPECTED_SHA1:
        raise ValueError('full EU ROM comparison failed; no C credit is valid')
    return {'rom_match_verified': True, 'full_rom_byte_compare': True,
            'expected_sha1': EXPECTED_SHA1, 'rebuilt_sha1': EXPECTED_SHA1,
            'credited_c_bytes': credited_bytes}


def output_path(root, relative):
    base = (root / 'build/eu').resolve()
    if base != root.resolve() / 'build/eu':
        raise ValueError('output directory must not redirect outside build/eu')
    result = (base / relative).resolve()
    if not result.is_relative_to(base) or result == base:
        raise ValueError('output must remain inside build/eu')
    return result


def guard_input_paths(root, metadata, rom, candidates=None):
    """Reject inputs the isolated build could replace, before any output I/O."""
    base = output_path(root, 'report.json').parent
    for label, path in [('ROM', rom), ('metadata directory', metadata), ('candidates', candidates)]:
        if path is not None and path.resolve().is_relative_to(base):
            raise ValueError(label + ' input must not be inside build/eu')


def elf_sections(path):
    data = path.read_bytes()
    if data[:7] != b'\x7fELF\x01\x01\x01':
        raise ValueError('expected little-endian ELF32')
    header = struct.unpack_from('<16sHHIIIIIHHHHHH', data)
    sections = [struct.unpack_from('<IIIIIIIIII', data, header[6] + i * header[11]) for i in range(header[12])]
    names = sections[header[13]]
    strings = data[names[4]:names[4] + names[5]]
    return data, {strings[s[0]:].split(b'\0')[0].decode(): s for s in sections}, sections


def guard_relocations(path, allow_calls=False):
    data, named, sections = elf_sections(path)
    for section in sections:
        if section[1] in (4, 9):
            if section[1] != 9 or section[9] != 8:
                raise ValueError('unsupported ELF relocation format')
            for offset in range(section[4], section[4] + section[5], 8):
                _, info = struct.unpack_from('<II', data, offset)
                if info & 255 not in ((2, 10, 40) if allow_calls else (2,)):
                    raise ValueError('unsupported relocation; EU call targets need independent proof')


def elf_symbols(path):
    data, _, sections = elf_sections(path)
    result = []
    for section in sections:
        if section[1] != 2:
            continue
        strings = sections[section[6]]
        strings = data[strings[4]:strings[4] + strings[5]]
        for offset in range(section[4], section[4] + section[5], 16):
            name, value, size, info, other, index = struct.unpack_from('<IIIBBH', data, offset)
            name = strings[name:].split(b'\0')[0].decode()
            if name and info >> 4 in (1, 2):
                result.append((name, value, index))
    return result


def build(root, metadata, rom, bash, candidates=None):
    root, metadata, rom = root.resolve(), metadata.resolve(), rom.resolve()
    candidates = candidates.resolve() if candidates else None
    guard_input_paths(root, metadata, rom, candidates)
    original = rom.read_bytes()
    validate_rom(original)  # Validate before producing outputs.
    manifest_bytes = (metadata / 'manifest.json').read_bytes()
    manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()
    manifest = json.loads(manifest_bytes)
    metadata_recipe = metadata.parents[1] / 'tools/scripts/metadata_build.py'
    verify_metadata_provenance(manifest, metadata_recipe)
    manifest['inputs_sha256'] = {name.replace('\\', '/'): digest for name, digest in manifest['inputs_sha256'].items()}
    for name, digest in manifest['inputs_sha256'].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
            raise ValueError('stale metadata input: ' + name)
    if candidates:
        receipt = json.loads(candidates.read_text())
        if receipt['eu_sha1'] != EXPECTED_SHA1 or receipt['source_manifest_sha256'] != manifest_digest:
            raise ValueError('candidate provenance does not match EU ROM and metadata')
        modules = receipt['candidates']
    else:
        # First reviewed module has no calls and exactly the same EU address.
        symbols = {name: value for name, value, index in elf_symbols(metadata / 'shiningsoul.elf')}
        undefined = [name for name, value, index in elf_symbols(metadata / 'src/input.o') if index == 0]
        bindings = {name: symbols[name] for name in undefined}
        if any(not 0x02000000 <= value < 0x04000000 for value in bindings.values()):
            raise ValueError('unproven EU input-module binding')
        modules = [{'object': 'src/input.o', 'source': 'src/input.c', 'eu_start': 0x0800076C, 'size': 292,
                    'bindings': bindings, 'object_sha256': hashlib.sha256((metadata / 'src/input.o').read_bytes()).hexdigest()}]
    modules = sorted(modules, key=lambda module: module['eu_start'])
    if not modules:
        raise ValueError('no candidate C modules')
    previous = 0xC0
    for module in modules:
        name = module['object']
        source = module['source']
        if not re.fullmatch(r'src/(?:[A-Za-z0-9_]+/)*[A-Za-z0-9_]+\.o', name) or source != name[:-2] + '.c' or source not in manifest['inputs_sha256']:
            raise ValueError('candidate is not a known shared C module')
        obj = metadata / name
        module['_object_bytes'] = obj.read_bytes()
        if hashlib.sha256(module['_object_bytes']).hexdigest() != module['object_sha256']:
            raise ValueError('stale candidate object: ' + name)
        recorded_objects = {key.replace('\\', '/'): value for key, value in manifest['objects_sha256'].items()}
        if recorded_objects.get('build/metadata/' + name) != module['object_sha256']:
            raise ValueError('object does not match compiled metadata provenance: ' + name)
        guard_relocations(obj, allow_calls=bool(candidates))
        _, object_sections, _ = elf_sections(obj)
        if object_sections['.text'][5] != module['size']:
            raise ValueError('candidate size differs from complete object text')
        start = module['eu_start'] - 0x08000000
        if start < previous or module['size'] <= 0 or start + module['size'] > CODE_END:
            raise ValueError('candidate overlaps another module, header or EU data')
        previous = start + module['size']
    out = root / 'build/eu'
    out.mkdir(parents=True, exist_ok=True)
    output_path(root, 'report.json').unlink(missing_ok=True)
    output_path(root, 'metadata-manifest.json').write_bytes(manifest_bytes)
    def posix(path):
        value = Path(path).resolve().as_posix()
        return '/' + value[0].lower() + value[2:] if re.match(r'^[A-Za-z]:/', value) else value
    def run(command):
        script = 'export PATH=/ucrt64/bin:/usr/bin:$PATH; cd ' + shlex.quote(posix(root)) + '; ' + command
        proc = subprocess.run([str(bash), '-lc', script], capture_output=True, text=True)
        if proc.returncode:
            raise RuntimeError(proc.stdout + proc.stderr)
        return proc.stdout
    # Native Windows assembler reads paths embedded in assembly itself;
    # MSYS argv conversion cannot translate an embedded /d/... incbin path.
    rom_asm = rom.resolve().as_posix().replace('"', '\\"')
    fragments, layout, bindings, defined = [], [], {}, set()
    cursor = 0
    for index, module in enumerate(modules):
        start = module['eu_start'] - 0x08000000
        if start > cursor:
            section = f'.gap{index}'
            fragments.append(f'.section {section},"a"\n.incbin "{rom_asm}", {cursor}, {start - cursor}\n')
            layout.append(f'build/eu/fallback.o({section});')
        objname = f'module{index}.o'
        output_path(root, objname).write_bytes(module['_object_bytes'])
        layout.append(f'build/eu/{objname}(.text);')
        for name, value, section in elf_symbols(metadata / module['object']):
            if section:
                defined.add(name)
        for name, value in module['bindings'].items():
            if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name) or not isinstance(value, int) or not 0 <= value <= 0xFFFFFFFF:
                raise ValueError('unsafe candidate symbol binding')
            if name in bindings and bindings[name] != value:
                raise ValueError('conflicting EU symbol bindings: ' + name)
            bindings[name] = value
        cursor = start + module['size']
    fragments.append(f'.section .suffix,"a"\n.incbin "{rom_asm}", {cursor}, {ROM_SIZE - cursor}\n')
    layout.append('build/eu/fallback.o(.suffix);')
    output_path(root, 'fallback.s').write_text(''.join(fragments))
    bindings = {name: value for name, value in bindings.items() if name not in defined}
    calls = {relocation['symbol'] for module in modules for relocation in module.get('relocations', []) if relocation['type'] == 10}
    calls &= bindings.keys()
    # Linker-script ABS assignments lose Thumb function typing and produce
    # interworking veneers. Typed absolute Thumb symbols preserve original BLs.
    output_path(root, 'bindings.s').write_text('\n'.join(
        f'.global {name}\n.type {name}, %function\n.thumb_set {name}, 0x{bindings[name]:X}' for name in sorted(calls)) + '\n')
    assignments = '\n'.join(f'{name} = 0x{value:X};' for name, value in bindings.items() if name not in calls)
    output_path(root, 'linker.ld').write_text('OUTPUT_ARCH(arm)\n' + assignments + '\nSECTIONS { . = 0x08000000; .rom : { ' + ' '.join(layout) + ' build/eu/bindings.o(.text); } /DISCARD/ : { *(*) } }\n')
    run('arm-none-eabi-as -mcpu=arm7tdmi -o build/eu/fallback.o build/eu/fallback.s')
    run('arm-none-eabi-as -mcpu=arm7tdmi -o build/eu/bindings.o build/eu/bindings.s')
    run('arm-none-eabi-ld -T build/eu/linker.ld -Map build/eu/shiningsoul_eu.map -o build/eu/shiningsoul_eu.elf')
    run('arm-none-eabi-objcopy -O binary build/eu/shiningsoul_eu.elf build/eu/shiningsoul_eu.gba')
    rebuilt = output_path(root, 'shiningsoul_eu.gba').read_bytes()
    credited = sum(module['size'] for module in modules)
    proof = verify_rebuild(original, rebuilt, credited)
    receipt_inputs = {name: hashlib.sha256((root / name).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
                      for name in manifest['inputs_sha256']}
    receipt_inputs['tools/scripts/eu_build.py'] = hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
    for name in ('tools/scripts/metadata_build.py', 'tools/scripts/eu_module_match.py'):
        receipt_inputs[name] = hashlib.sha256((root / name).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
    proof.update({'region': 'EU', 'game_code': 'AHUP', 'original_rom_verified_sha1': EXPECTED_SHA1,
                  'code_end_offset': CODE_END, 'cartridge_header_bytes': 188, 'executable_code_bytes': CODE_END - 188,
                  'credited_c_modules': [{'source': module['source'], 'start': module['eu_start'] - 0x08000000,
                    'end': module['eu_start'] - 0x08000000 + module['size'], 'bytes': module['size'],
                    'linked_span_sha256': hashlib.sha256(rebuilt[module['eu_start'] - 0x08000000:module['eu_start'] - 0x08000000 + module['size']]).hexdigest(),
                    'object_sha256': module['object_sha256']} for module in modules],
                  'pending_fallback_code_bytes': CODE_END - 188 - credited, 'preserved_asset_bytes': ROM_SIZE - CODE_END,
                  'data_ids_claimed': 0, 'languages': ['English', 'French', 'German', 'Spanish', 'Italian'],
                  'scope': 'Only listed compiled complete C modules receive credit. Every other byte comes from the verified owned EU ROM; raw fallback code remains pending.',
                  'source_hash_mode': 'sha256-lf', 'inputs_sha256': receipt_inputs, 'symbol_bindings': bindings,
                  'compiler_sha256': manifest.get('compiler_sha256', {}),
                  'compiler_flags': manifest.get('compiler_flags'),
                  'builder_sha256': manifest['builder_sha256'],
                  'compiler_headers_sha256': manifest['compiler_headers_sha256'],
                  'source_manifest_sha256': manifest_digest})
    output_path(root, 'report.json').write_text(json.dumps(proof, indent=2) + '\n')
    return proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--metadata-dir', type=Path, required=True)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--candidates', type=Path)
    parser.add_argument('--bash', type=Path, default=Path('C:/msys64/usr/bin/bash.exe') if os.name == 'nt' else Path('/bin/bash'))
    args = parser.parse_args()
    print(json.dumps(build(args.root.resolve(), args.metadata_dir.resolve(), args.rom.resolve(), args.bash, args.candidates), indent=2))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Build ROM-free layout metadata, never a playable or verified ROM."""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess

OBJECT = re.compile(r'(?<![\w./])([A-Za-z0-9_/]+\.o)')
EXPECTED = {
    'asm/crt0.s': (4, 0xBC),
    'data/data.s': (0x5289C,),
}
GAME_FLAGS = '-mthumb-interwork -Wimplicit -Wparentheses -O2 -fhex-asm -fprologue-bugfix'
OLD_FLAGS = '-mthumb-interwork -Wimplicit -Wparentheses -O2 -fhex-asm'


def replace_incbin(text, source):
    """Accept exactly the two known ROM holes; reject every other incbin."""
    expected = EXPECTED.get(source)
    count = 0
    lines = []
    for line in text.splitlines(keepends=True):
        if re.search(r'\.incbin\b', line.split('@', 1)[0]):
            match = re.fullmatch(r'\s*\.incbin\s+"baserom\.gba"\s*,\s*(0x[0-9a-fA-F]+|\d+)(?:\s*,\s*(0x[0-9a-fA-F]+|\d+))?\s*(?:@[^\n]*)?\n?', line)
            values = tuple(int(v, 0) for v in match.groups() if v is not None) if match else ()
            if expected is None or values != expected or count:
                raise ValueError(f'unknown incbin in {source}: {line.strip()}')
            size = 0xBC if source == 'asm/crt0.s' else 0x800000 - 0x5289C
            line = f'\t.space 0x{size:X} @ metadata-only placeholder\n'
            count += 1
        lines.append(line)
    if expected is not None and count != 1:
        raise ValueError(f'expected exactly one ROM hole in {source}')
    return ''.join(lines)


def rewrite_linker(text):
    def rewrite(match):
        path = match.group(1)
        if not path.startswith(('asm/', 'src/', 'data/')) or '..' in path.split('/'):
            raise ValueError(f'unsafe object path: {path}')
        return 'build/metadata/' + path
    return OBJECT.sub(rewrite, text).replace('INCLUDE ld_symbols.ld', 'INCLUDE build/metadata/ld_symbols.ld')


def build(root, compiler, bash, jobs):
    out = root / 'build/metadata'
    out.mkdir(parents=True, exist_ok=True)
    manifest = out / 'manifest.json'
    manifest.unlink(missing_ok=True)  # A failed rebuild must not leave success evidence.
    def posix(path):
        path = Path(path).resolve().as_posix()
        return '/' + path[0].lower() + path[2:] if re.match(r'^[A-Za-z]:/', path) else path
    def run(command):
        script = 'export PATH=/ucrt64/bin:/usr/bin:$PATH; cd ' + shlex.quote(posix(root)) + '; ' + command
        result = subprocess.run([str(bash), '-lc', script], capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        return result.stdout
    linker = (root / 'ld_script.ld').read_text()
    objects = list(dict.fromkeys(OBJECT.findall(linker)))
    # Validate and stage all assembly before launching any compiler.
    for obj in objects:
        source = obj[:-2] + ('.c' if obj.startswith('src/') else '.s')
        if source.endswith('.s'):
            staged = out / source
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_text(replace_incbin((root / source).read_text(), source))
    # Inline the identical symbol assignments: Windows binutils 2.47 rejects
    # INCLUDE here as a duplicate script even with no positional input files.
    (out / 'ld_script.ld').write_text(rewrite_linker(linker).replace(
        'INCLUDE build/metadata/ld_symbols.ld', (root / 'ld_symbols.ld').read_text()))
    (out / 'ld_symbols.ld').write_bytes((root / 'ld_symbols.ld').read_bytes())
    compiler_path = posix(compiler)
    def compile_object(obj):
        target = 'build/metadata/' + obj
        (root / target).parent.mkdir(parents=True, exist_ok=True)
        if obj.startswith('src/'):
            source = obj[:-2] + '.c'
            assembly = target[:-2] + '.s'
            old = obj == 'src/lib/m4a.o'
            cc = compiler_path + '/bin/' + ('old_agbcc' if old else 'agbcc')
            flags = OLD_FLAGS if old else GAME_FLAGS
            # pipefail prevents successful agbcc output masking CPP failure.
            run('set -o pipefail; arm-none-eabi-cpp -nostdinc -I include -I ' + shlex.quote(compiler_path + '/include') + ' -iquote include ' + shlex.quote(source) + ' | ' + shlex.quote(cc) + ' ' + flags + ' -o ' + shlex.quote(assembly))
            with (root / assembly).open('a') as stream:
                stream.write('\t.text\n\t.align 2, 0\n')
        else:
            assembly = target[:-2] + '.s'
        run('arm-none-eabi-as -mcpu=arm7tdmi -I include -o ' + shlex.quote(target) + ' ' + shlex.quote(assembly))
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        list(pool.map(compile_object, objects))
    # The linker script already lists every object in order. Repeating them
    # also exceeds Windows command-line limits for this repository.
    run('arm-none-eabi-ld -T build/metadata/ld_script.ld -Map build/metadata/shiningsoul.map -o build/metadata/shiningsoul.elf')
    symbols = run('arm-none-eabi-nm -n build/metadata/shiningsoul.elf')
    data_address = next((int(line.split()[0], 16) for line in symbols.splitlines() if line.split()[-1:] == ['gRomData']), None)
    sections = run('arm-none-eabi-objdump -h build/metadata/shiningsoul.elf')
    text = re.search(r'^\s*\d+\s+\.text\s+([0-9a-fA-F]+)\s+([0-9a-fA-F]+)', sections, re.M)
    if not text or int(text[1], 16) + int(text[2], 16) != 0x0805289C or data_address != 0x0805289C:
        raise RuntimeError('metadata layout changed: code end and gRomData must be 0x0805289C')
    inputs = [root / 'ld_script.ld', root / 'ld_symbols.ld']
    inputs += [root / (obj[:-2] + ('.c' if obj.startswith('src/') else '.s')) for obj in objects]
    inputs += sorted((root / 'include').rglob('*.h')) + [root / 'asm/macros.inc']
    compiler_files = [p for p in (compiler / 'bin').iterdir() if p.is_file()]
    manifest.write_text(json.dumps({
        'metadata_only': True,
        'rom_match_verified': False,
        'cache': False,
        'object_count': len(objects),
        'code_end': data_address,
        'code_end_offset': data_address - 0x08000000,
        'modules': [{'source': obj[:-2] + ('.c' if obj.startswith('src/') else '.s'),
                     'object': 'build/metadata/' + obj} for obj in objects],
        'compiler_dir': str(compiler),
        'compiler_flags': {'game': GAME_FLAGS.split(), 'm4a': OLD_FLAGS.split(),
                           'preprocessor': ['-nostdinc', '-I', 'include', '-I', '<compiler>/include', '-iquote', 'include'],
                           'assembler': ['-mcpu=arm7tdmi', '-I', 'include']},
        'builder_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'compiler_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in compiler_files},
        'compiler_headers_sha256': {str(p.relative_to(compiler / 'include')): hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in sorted((compiler / 'include').rglob('*')) if p.is_file()},
        'objects_sha256': {'build/metadata/' + obj: hashlib.sha256((root / 'build/metadata' / obj).read_bytes()).hexdigest()
                          for obj in objects},
        'inputs_sha256': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
    }, indent=2) + '\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--compiler-dir', type=Path)
    parser.add_argument('--bash', type=Path, default=Path('C:/msys64/usr/bin/bash.exe') if os.name == 'nt' else Path('/bin/bash'))
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error('--jobs must be positive')
    root = args.root.resolve()
    print(build(root, (args.compiler_dir or root / 'tools/agbcc').resolve(), args.bash, args.jobs))


if __name__ == '__main__':
    main()

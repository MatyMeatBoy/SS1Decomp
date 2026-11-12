import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('eu_build', Path(__file__).resolve().parents[1] / 'tools/scripts/eu_build.py')
eu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eu)


class EuBuildTests(unittest.TestCase):
    def test_wrong_region_size_and_hash_are_rejected(self):
        for data in (b'', bytes(eu.ROM_SIZE), bytes(0xAC) + b'AHUP' + bytes(eu.ROM_SIZE - 0xB0)):
            with self.assertRaises(ValueError):
                eu.validate_rom(data)

    def test_credit_requires_full_identical_rebuild(self):
        with patch.object(eu, 'validate_rom'), patch.object(eu, 'EXPECTED_SHA1', eu.hashlib.sha1(b'original').hexdigest()):
            with self.assertRaisesRegex(ValueError, 'no C credit'):
                eu.verify_rebuild(b'original', b'originaX', 292)
            self.assertEqual(eu.verify_rebuild(b'original', b'original', 292)['credited_c_bytes'], 292)

    def test_output_paths_cannot_escape_isolated_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(eu.output_path(root, 'input.o'), root / 'build/eu/input.o')
            with self.assertRaises(ValueError):
                eu.output_path(root, '../../src/input.o')

    def test_output_inputs_are_rejected_before_any_write_or_unlink(self):
        for input_name in ('rom', 'metadata', 'candidates'):
            with self.subTest(input_name=input_name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                output = root / 'build/eu'
                output.mkdir(parents=True)
                report = output / 'report.json'
                report.write_bytes(b'keep existing receipt')
                owned = output / ('metadata' if input_name == 'metadata' else 'shiningsoul_eu.gba')
                if input_name == 'metadata':
                    owned.mkdir()
                    (owned / 'manifest.json').write_bytes(b'keep owned metadata')
                else:
                    owned.write_bytes(b'keep owned input')
                paths = {'rom': root / 'owned.gba', 'metadata': root / 'build/metadata', 'candidates': root / 'candidate.json'}
                paths[input_name] = owned
                before = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
                with self.assertRaisesRegex(ValueError, 'input must not be inside build/eu'):
                    eu.build(root, paths['metadata'], paths['rom'], Path('unused-bash'), paths['candidates'])
                self.assertEqual({p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}, before)

    def test_unknown_or_call_relocations_are_rejected(self):
        section = (0, 9, 0, 0, 0, 8, 0, 0, 0, 8)
        with patch.object(eu, 'elf_sections', return_value=(struct.pack('<II', 0, 10), {}, [section])):
            with self.assertRaisesRegex(ValueError, 'unsupported relocation'):
                eu.guard_relocations(Path('unused'))
        with patch.object(eu, 'elf_sections', return_value=(struct.pack('<II', 0, 2), {}, [section])):
            eu.guard_relocations(Path('unused'))
        with patch.object(eu, 'elf_sections', return_value=(struct.pack('<II', 0, 99), {}, [section])):
            with self.assertRaisesRegex(ValueError, 'unsupported relocation'):
                eu.guard_relocations(Path('unused'), allow_calls=True)

    def test_old_metadata_provenance_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'lacks required'):
            eu.verify_metadata_provenance({'inputs_sha256': {}})

    def test_changed_compiler_header_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'include').mkdir()
            (root / 'bin').mkdir()
            (root / 'include/global.h').write_bytes(b'changed')
            (root / 'bin/agbcc').write_bytes(b'compiler')
            recipe = root / 'metadata_build.py'
            recipe.write_bytes(b'recipe')
            manifest = {'compiler_dir': str(root), 'compiler_flags': eu.EXPECTED_FLAGS,
                        'builder_sha256': eu.hashlib.sha256(b'recipe').hexdigest(), 'objects_sha256': {'src/input.o': 'o'},
                        'compiler_sha256': {'agbcc': eu.hashlib.sha256(b'compiler').hexdigest()},
                        'compiler_headers_sha256': {'global.h': eu.hashlib.sha256(b'original').hexdigest()}}
            with self.assertRaisesRegex(ValueError, 'stale compiler provenance'):
                eu.verify_metadata_provenance(manifest, recipe)

    def test_changed_metadata_recipe_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            recipe = Path(directory) / 'metadata_build.py'
            recipe.write_bytes(b'new recipe')
            manifest = {'compiler_flags': eu.EXPECTED_FLAGS,
                        'builder_sha256': eu.hashlib.sha256(b'old recipe').hexdigest(),
                        'objects_sha256': {'object': 'hash'},
                        'compiler_sha256': {'compiler': 'hash'},
                        'compiler_headers_sha256': {'header': 'hash'}}
            with self.assertRaisesRegex(ValueError, 'stale metadata builder recipe'):
                eu.verify_metadata_provenance(manifest, recipe)


if __name__ == '__main__':
    unittest.main()

import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('metadata_build', Path(__file__).resolve().parents[1] / 'tools/scripts/metadata_build.py')
metadata = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metadata)


class MetadataBuildTests(unittest.TestCase):
    def test_known_holes(self):
        self.assertIn('.space 0xBC', metadata.replace_incbin('.incbin "baserom.gba", 0x4, 0xBC\n', 'asm/crt0.s'))
        self.assertIn('.space 0x7AD764', metadata.replace_incbin('.incbin "baserom.gba", 0x5289C\n', 'data/data.s'))

    def test_unknown_missing_duplicate_holes_fail(self):
        for text, source in [('.incbin "other.gba", 4, 188\n', 'asm/crt0.s'), ('.incbin "baserom.gba", 4, 188\n', 'asm/code.s'), ('', 'asm/crt0.s'), ('.incbin "baserom.gba", 4, 188\n' * 2, 'asm/crt0.s')]:
            with self.subTest(text=text, source=source), self.assertRaises(ValueError):
                metadata.replace_incbin(text, source)

    def test_all_linker_objects_are_isolated(self):
        original = 'INCLUDE ld_symbols.ld\n asm/crt0.o(.text); src/lib/m4a.o(.text); data/data.o(.rodata);'
        rewritten = metadata.rewrite_linker(original)
        self.assertIn('INCLUDE build/metadata/ld_symbols.ld', rewritten)
        self.assertEqual(metadata.OBJECT.findall(rewritten), ['build/metadata/asm/crt0.o', 'build/metadata/src/lib/m4a.o', 'build/metadata/data/data.o'])
        self.assertNotIn('build/metadata/', original)

    def test_unknown_object_root_fails(self):
        with self.assertRaises(ValueError):
            metadata.rewrite_linker('elsewhere/file.o(.text);')

    def test_repository_linker_has_no_normal_object_references(self):
        root = Path(__file__).resolve().parents[1]
        original = (root / 'ld_script.ld').read_text()
        expected = metadata.OBJECT.findall(original)
        actual = metadata.OBJECT.findall(metadata.rewrite_linker(original))
        self.assertTrue(expected)
        self.assertEqual(actual, ['build/metadata/' + path for path in expected])


if __name__ == '__main__':
    unittest.main()

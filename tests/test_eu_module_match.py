import pathlib
import struct
import sys
import types
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]/'tools/scripts'))
import eu_module_match as e


def bl(displacement):
    return struct.pack('<HH', 0xF000 | ((displacement >> 12) & 0x7FF),
                       0xF800 | ((displacement >> 1) & 0x7FF))


class ModuleTests(unittest.TestCase):
    def test_thumb_forward_backward_and_pipeline(self):
        for displacement in [-4194304, -4, 0, 200, 4194302]:
            self.assertEqual(e.thumb_displacement(bl(displacement)), displacement)
            self.assertEqual(e.thumb_target(bl(displacement), 0, e.BASE+20),
                             e.BASE+24+displacement)

    def test_only_relocations_mask_and_unknown_rejected(self):
        text = b'\x12\x34\x56\x08'+bl(-4)+b'\x10\x20\x30\x40'
        mask = e.relocation_mask(text, [{'offset':4, 'type':10}])
        self.assertEqual(mask[:4], b'\xff'*4)  # ROM-looking constants remain fixed.
        self.assertEqual(mask[4:8], b'\0'*4)
        self.assertEqual(e.relocation_mask(text, [{'offset':8,'type':40}]), b'\xff'*12)
        with self.assertRaises(ValueError):
            e.relocation_mask(text, [{'offset':0,'type':99}])
        with self.assertRaises(ValueError):
            e.relocation_mask(bl(0), [{'offset':0,'type':10}])

    def test_bindings_addends_and_conflicts(self):
        sym = dict(name='target', section=0, value=0)
        elf = types.SimpleNamespace(text=struct.pack('<II', 12, 4), text_index=1,
            relocs=[dict(offset=0,type=2,symbol=sym),dict(offset=4,type=2,symbol=sym)])
        bindings, _ = e.bind_relocations(elf, struct.pack('<II',0x0300100C,0x03001004),e.BASE)
        self.assertEqual(bindings, {'target':0x03001000})
        with self.assertRaisesRegex(ValueError, 'conflicting'):
            e.bind_relocations(elf, struct.pack('<II',0x0300100C,0x03002004),e.BASE)

    def test_thumb_binding_sets_bit_and_internal_is_not_external(self):
        sym = dict(name='function',section=0,value=0)
        elf = types.SimpleNamespace(text=bl(-4),text_index=1,
            relocs=[dict(offset=0,type=10,symbol=sym)])
        bindings,_=e.bind_relocations(elf,bl(100),e.BASE)
        self.assertEqual(bindings['function'], e.BASE+105)
        sym.update(section=1,value=104)
        bindings,_=e.bind_relocations(elf,bl(100),e.BASE)
        self.assertEqual(bindings,{})
        sym['value']=200
        with self.assertRaisesRegex(ValueError,'internal'):
            e.bind_relocations(elf,bl(100),e.BASE)

    def test_ambiguity_and_fixed_byte_corruption(self):
        text=bytes(range(24)); mask=e.relocation_mask(text,[])
        self.assertEqual(e.unique_sites(text,mask,text,24),[e.BASE])
        self.assertEqual(len(e.unique_sites(text,mask,text+text,48)),2)
        damaged=bytearray(text);damaged[3]^=1
        self.assertEqual(e.unique_sites(text,mask,damaged,24),[])

    def test_empty_manifest_cannot_support_credit(self):
        self.assertIn('missing inputs_sha256', e.validate_manifest(pathlib.Path('.'),{}))
        self.assertIn('missing compiler_sha256', e.validate_manifest(pathlib.Path('.'),{}))
        self.assertIn('never grants C credit', e.__doc__)

    def test_missing_flags_and_objects_are_rejected(self):
        stale=e.validate_manifest(pathlib.Path('.'), {})
        self.assertIn('missing or unexpected compiler_flags',stale)
        self.assertIn('missing objects_sha256',stale)
        self.assertIn('missing compiler_headers_sha256',stale)

    def test_stale_object_is_rejected_even_if_manifest_has_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp)
            obj=root/'build/metadata/src/example.o'
            obj.parent.mkdir(parents=True)
            obj.write_bytes(b'new object')
            manifest={'modules':[{'object':'build/metadata/src/example.o'}],
                      'objects_sha256':{'build/metadata/src/example.o':'old hash'}}
            self.assertIn('object/build/metadata/src/example.o',e.validate_manifest(root,manifest))


if __name__ == '__main__':
    unittest.main()

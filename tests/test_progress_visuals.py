import importlib.util
import pathlib
import sys
import unittest
import xml.etree.ElementTree as ET
SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / 'tools/scripts'
sys.path.insert(0, str(SCRIPTS))
import progress_visuals as p
import progress_render as render

class InventoryTests(unittest.TestCase):
    def test_alias_dedup_ownership_and_header(self):
        sections=p.parse_map(' .text 0x08000000 0x104 build/metadata/asm/crt0.o\n .text 0x08000104 0x20 build/metadata/src/lib/multi_sio.o\n .text 0x08000124 0x10 build/metadata/src/game.o\n')
        symbols=p.parse_nm('08000000 T _start\n08000104 T sub_08000104\n08000104 T MultiSioInit\n08000124 T Game\n08000124 t $t\n')
        report=p.inventory(sections,symbols,code_end=0x08000134)
        self.assertEqual(report['header_excluded_bytes'],188)
        self.assertEqual(report['all']['bytes'],120)
        self.assertEqual(report['all']['functions'],3)
        self.assertEqual(report['lib']['c_bytes'],32)
        self.assertEqual(report['modules'][1]['funcs'][0]['name'],'MultiSioInit')
        self.assertEqual(report['legacy_compatibility']['game_code_bytes'],276)
    def test_library_trampoline_and_pending_game_assembly(self):
        sections=p.parse_map(' .text 0x0804faa8 0x4 asm/code_0804FAA8.o\n .text 0x0804faac 0x10 asm/lib/m4a_1.o\n .text 0x0804fabc 0x8 asm/game.o\n')
        symbols=p.parse_nm('0804faa8 T umul3232H32\n0804faac T __umul3232H32\n0804fabc T sub_0804FABC\n')
        report=p.inventory(sections,symbols,code_end=0x0804fac4)
        self.assertEqual(report['lib']['original_asm_bytes'],20)
        self.assertEqual(report['game']['pending_asm_bytes'],8)
        self.assertEqual(report['all']['bytes'],28)
    def test_wrapped_map_and_mapping_symbols(self):
        sections=p.parse_map(' .text\n                0x0800023c 0x10 /tmp/out/src/a.o\n')
        self.assertEqual(sections[0]['object'],'src/a.o')
        self.assertEqual(len(p.parse_nm('0800023c T Function\n0800023c t $t\n08000240 T _08000240\n')),1)
    def test_metadata_cannot_verify_rom(self):
        self.assertFalse(p.rom_match_verified(pathlib.Path('.'),metadata=True))
    def test_scheduler_does_not_credit_adjacent_pending_wrapper(self):
        sections=p.parse_map(' .text 0x0800023c 0x280 asm/code.o\n')
        symbols=p.parse_nm('0800023c T RunThreads\n08000498 T GetCurrentThread\n080004a4 T sub_080004A4\n')
        report=p.inventory(sections,symbols,code_end=0x080004bc)
        self.assertEqual(report['game']['original_asm_bytes'],0x268)
        self.assertEqual(report['game']['pending_asm_bytes'],0x18)
    def test_render_is_accessible_xml(self):
        report=p.inventory(p.parse_map(' .text 0x0800023c 0x10 src/a.o\n'),p.parse_nm('0800023c T Name\n'),code_end=0x0800024c)
        for svg in [render.treemap_svg(report),render.names_treemap_svg(report),render.data_svg(report),render.badge_svg('a & b','0%', '#555')]:
            root=ET.fromstring(svg)
            self.assertEqual(root.attrib['role'],'img')
        self.assertIn('0x0800023C',render.treemap_svg(report))
        self.assertNotIn('verified progress',render.treemap_svg(report))

if __name__=='__main__':unittest.main()

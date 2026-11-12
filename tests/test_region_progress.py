import hashlib
import json
import pathlib
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tools/scripts'))
import region_progress as r

class RegionTests(unittest.TestCase):
    def receipt(self,root):
        (root/'src').mkdir();(root/'src/input.c').write_text('source')
        receipt={'region':'EU','game_code':'AHUP','expected_sha1':r.EXPECTED,'original_rom_verified_sha1':r.EXPECTED,'rebuilt_sha1':r.EXPECTED,'rom_match_verified':True,'full_rom_byte_compare':True,'code_end_offset':338736,'credited_c_modules':[{'source':'src/input.c','start':1900,'end':2192,'bytes':292,'linked_span_sha256':'a'*64,'object_sha256':'b'*64}],'inputs_sha256':{'src/input.c':hashlib.sha256(b'source').hexdigest()},'source_manifest_sha256':'c'*64,'builder_sha256':'d'*64,'compiler_sha256':{'agbcc':'e'*64,'old_agbcc':'f'*64},'compiler_headers_sha256':{'stddef.h':'a'*64},'compiler_flags':{'game':['-mthumb-interwork','-Wimplicit','-Wparentheses','-O2','-fhex-asm','-fprologue-bugfix'],'m4a':['-mthumb-interwork','-Wimplicit','-Wparentheses','-O2','-fhex-asm'],'preprocessor':['-nostdinc','-I','include','-I','<compiler>/include','-iquote','include'],'assembler':['-mcpu=arm7tdmi','-I','include']}}
        (root/'tools/scripts').mkdir(parents=True)
        for name in ['eu_build.py','metadata_build.py','eu_module_match.py']:
            (root/'tools/scripts'/name).write_bytes(b'recipe')
            receipt['inputs_sha256']['tools/scripts/'+name]=hashlib.sha256(b'recipe').hexdigest()
        return receipt
    def test_header_and_spans(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d);report=r.assess(self.receipt(root),root)
            self.assertTrue(report['rom_match_verified']);self.assertEqual(report['code_bytes'],338548);self.assertEqual(report['credited_c_bytes'],292);self.assertIsNone(report['functions'])
            self.assertEqual(sum(c['bytes'] for c in r.cells(report)),report['code_bytes'])
            self.assertTrue(report['source_inputs_current'])
            ET.fromstring(r.treemap_svg(report))
            self.assertNotIn('functions complete',r.treemap_svg(report))
    def test_invalid_receipts_never_credit(self):
        for field,value in [('rebuilt_sha1','bad'),('original_rom_verified_sha1','bad'),('expected_sha1','bad'),('game_code','AHUE'),('region','USA'),('full_rom_byte_compare',False)]:
            with tempfile.TemporaryDirectory() as d:
                root=pathlib.Path(d);receipt=self.receipt(root);receipt[field]=value;report=r.assess(receipt,root)
                self.assertFalse(report['rom_match_verified'],field);self.assertEqual(report['credited_c_bytes'],0,field)
    def test_stale_or_missing_input_hashes(self):
        for missing in [False,True]:
            with tempfile.TemporaryDirectory() as d:
                root=pathlib.Path(d);receipt=self.receipt(root)
                if missing:receipt['inputs_sha256']={}
                else:(root/'src/input.c').write_text('changed')
                report=r.assess(receipt,root);self.assertFalse(report['rom_match_verified']);self.assertEqual(report['credited_c_bytes'],0)
    def test_lf_mode_accepts_crlf_and_posix_or_windows_relative_paths(self):
        for data in [b'line one\nline two\n',b'line one\r\nline two\r\n']:
            with tempfile.TemporaryDirectory() as d:
                root=pathlib.Path(d);receipt=self.receipt(root)
                (root/'src/input.c').write_bytes(data)
                receipt['source_hash_mode']='sha256-lf'
                receipt['source_manifest_sha256']='c'*64
                receipt['compiler_sha256']={'agbcc':'e'*64,'old_agbcc':'f'*64}
                receipt['inputs_sha256'].pop('src/input.c')
                receipt['inputs_sha256']['src\\input.c']=hashlib.sha256(b'line one\nline two\n').hexdigest()
                receipt['inputs_sha256']={name.replace('/','\\'):digest for name,digest in receipt['inputs_sha256'].items()}
                report=r.assess(receipt,root)
                self.assertTrue(report['rom_match_verified'])
                self.assertIn('src/input.c',report['inputs_sha256'])
                self.assertEqual(report['source_manifest_sha256'],'c'*64)
                self.assertEqual(report['compiler_sha256'],{'agbcc':'e'*64,'old_agbcc':'f'*64})
                (root/'src/input.c').write_bytes(b'line one changed\r\nline two\r\n')
                self.assertFalse(r.assess(receipt,root)['rom_match_verified'])
    def test_unknown_source_hash_mode_refuses_credit(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d);receipt=self.receipt(root);receipt['source_hash_mode']='sha256-trim-whitespace'
            report=r.assess(receipt,root)
            self.assertFalse(report['rom_match_verified']);self.assertEqual(report['credited_c_bytes'],0)
    def test_windows_escape_path_refuses_credit(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d);receipt=self.receipt(root)
            receipt['inputs_sha256']['..\\outside.c']=hashlib.sha256(b'anything').hexdigest()
            self.assertFalse(r.assess(receipt,root)['rom_match_verified'])
    def test_stripped_span_hashes_refuse_all_credit(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d);receipt=self.receipt(root)
            for module in receipt['credited_c_modules']:
                module.pop('linked_span_sha256');module.pop('object_sha256')
            report=r.assess(receipt,root)
            self.assertFalse(report['rom_match_verified']);self.assertEqual(report['credited_c_bytes'],0)
    def test_invalid_core_provenance_refuses_credit(self):
        for field,value in [('source_manifest_sha256',None),('builder_sha256','bogus'),('compiler_sha256',{}),('compiler_sha256',{'agbcc':'z'*64,'old_agbcc':'a'*64}),('compiler_headers_sha256',{}),('compiler_flags',{})]:
            with tempfile.TemporaryDirectory() as d:
                root=pathlib.Path(d);receipt=self.receipt(root);receipt[field]=value
                report=r.assess(receipt,root)
                self.assertFalse(report['rom_match_verified'],field);self.assertEqual(report['credited_c_bytes'],0)
    def test_missing_receipt_overwrites_old_verified_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d);out=root/'out';out.mkdir();(out/'eu_progress.json').write_text('{"rom_match_verified":true}');(out/'progress.json').write_text('{"rom_match_verified":true}')
            r.main(['--report',str(root/'missing.json'),'--root',str(root),'--out',str(out)])
            report=json.loads((out/'eu_progress.json').read_text())
            self.assertFalse(report['rom_match_verified']);self.assertEqual(report['credited_c_bytes'],0)
            self.assertNotIn('verified locally',(out/'eu_badge_rom.svg').read_text())
            self.assertFalse(json.loads((out/'progress.json').read_text())['rom_match_verified'])
            self.assertIn('unverified',(out/'badge_rom.svg').read_text())
    def test_wrong_recipe_or_malformed_span_digest_refuses_credit(self):
        for mutation in ['recipe','span_digest']:
            with tempfile.TemporaryDirectory() as d:
                root=pathlib.Path(d);receipt=self.receipt(root)
                if mutation=='recipe':receipt['compiler_flags']['game'].append('-O0')
                else:receipt['credited_c_modules'][0]['object_sha256']='z'*64
                report=r.assess(receipt,root)
                self.assertFalse(report['rom_match_verified']);self.assertEqual(report['credited_c_bytes'],0)
    def test_malformed_json_fails_instead_of_publishing(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d);receipt=root/'broken.json';receipt.write_text('{broken')
            with self.assertRaises(json.JSONDecodeError):
                r.main(['--report',str(receipt),'--out',str(root/'out')])
            self.assertFalse((root/'out').exists())
    def test_missing_recipe_input_key_refuses_credit(self):
        for name in ['eu_build.py','metadata_build.py','eu_module_match.py']:
            with tempfile.TemporaryDirectory() as d:
                root=pathlib.Path(d);receipt=self.receipt(root)
                receipt['inputs_sha256'].pop('tools/scripts/'+name)
                report=r.assess(receipt,root)
                self.assertFalse(report['rom_match_verified'],name);self.assertEqual(report['credited_c_bytes'],0,name)
                self.assertFalse(report['source_inputs_current'])
    def test_primary_artifacts_are_europe_and_unknown_function_metrics(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d);receipt=self.receipt(root);path=root/'receipt.json';path.write_text(json.dumps(receipt));out=root/'out'
            r.main(['--report',str(path),'--root',str(root),'--out',str(out)])
            primary=json.loads((out/'progress.json').read_text())
            self.assertEqual(primary['game_code'],'AHUP');self.assertEqual(primary['region'],'EU');self.assertEqual(primary['credited_c_bytes'],292)
            self.assertEqual((out/'progress.json').read_bytes(),(out/'eu_progress.json').read_bytes())
            for name in ['treemap.svg','badge_decompiled.svg','badge_rom.svg','names_treemap.svg','badge_names.svg','badge_functions.svg','data.svg','badge_data.svg']:
                svg=(out/name).read_text();ET.fromstring(svg);self.assertIn('EU',svg,name)
            self.assertIn('not measured',(out/'badge_functions.svg').read_text())
            self.assertIn('not measured',(out/'badge_names.svg').read_text())
            self.assertIn('0%',(out/'badge_data.svg').read_text())
    def test_overlapping_or_header_spans_rejected(self):
        for span in [{'source':'src/input.c','start':4,'end':192,'bytes':188},{'source':'src/input.c','start':1900,'end':2192,'bytes':10}]:
            with tempfile.TemporaryDirectory() as d:
                root=pathlib.Path(d);receipt=self.receipt(root);receipt['credited_c_modules'].append(span)
                with self.assertRaises(ValueError):r.assess(receipt,root)

if __name__=='__main__':unittest.main()

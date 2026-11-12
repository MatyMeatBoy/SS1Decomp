#!/usr/bin/env python3
"""Present an owned EU full-ROM verification receipt without publishing assets.

A receipt is evidence about a local rebuild, not evidence that CI owns a ROM.
Only current, hashed source inputs plus full byte equality earn C-span credit.
"""
import argparse
import hashlib
import json
import re
from html import escape
from pathlib import Path, PurePosixPath
import progress_render as render

EXPECTED='6e80a65cca65236e405940c880b144d77f3f4f08'
CODE_END=338736
HEADER_START=4
HEADER_END=192
ROOT=Path(__file__).resolve().parents[2]


EXPECTED_COMPILER_FLAGS={
    'game':['-mthumb-interwork','-Wimplicit','-Wparentheses','-O2','-fhex-asm','-fprologue-bugfix'],
    'm4a':['-mthumb-interwork','-Wimplicit','-Wparentheses','-O2','-fhex-asm'],
    'preprocessor':['-nostdinc','-I','include','-I','<compiler>/include','-iquote','include'],
    'assembler':['-mcpu=arm7tdmi','-I','include'],
}


def valid_sha256(value):
    return isinstance(value,str) and re.fullmatch(r'[0-9a-fA-F]{64}',value) is not None


def valid_hashes(values):
    return isinstance(values,dict) and bool(values) and all(isinstance(name,str) and bool(name) and valid_sha256(digest) for name,digest in values.items())


def provenance_issues(receipt):
    issues=[]
    for key in ('source_manifest_sha256','builder_sha256'):
        if not valid_sha256(receipt.get(key)):issues.append(f'{key} missing or invalid')
    tools=receipt.get('compiler_sha256')
    if not valid_hashes(tools) or not {'agbcc','old_agbcc'}.issubset({name.removesuffix('.exe') for name in tools}):
        issues.append('compiler hashes missing or invalid')
    if not valid_hashes(receipt.get('compiler_headers_sha256')):issues.append('compiler header hashes missing or invalid')
    if receipt.get('compiler_flags')!=EXPECTED_COMPILER_FLAGS:issues.append('compiler recipe differs from the expected original flags')
    return issues


def normalized_relative_path(name):
    """Interpret receipts independently of the producer OS, before filesystem I/O."""
    if not isinstance(name,str):return None
    name=name.replace('\\','/')
    path=PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or ':' in name or not path.parts:return None
    return path.as_posix()


def assess(receipt,root):
    if not isinstance(receipt,dict):raise ValueError('receipt must be a JSON object')
    root=Path(root).resolve();reasons=provenance_issues(receipt)
    for field,wanted in [('region','EU'),('game_code','AHUP'),('expected_sha1',EXPECTED),('original_rom_verified_sha1',EXPECTED),('rebuilt_sha1',EXPECTED)]:
        if receipt.get(field)!=wanted:reasons.append(f'{field} does not match the EU AHUP profile')
    if receipt.get('rom_match_verified') is not True:reasons.append('receipt does not assert ROM verification')
    if receipt.get('full_rom_byte_compare') is not True:reasons.append('full-ROM byte comparison not established')
    if receipt.get('code_end_offset')!=CODE_END:reasons.append('EU code boundary differs from the profile')
    inputs=receipt.get('inputs_sha256',{})
    if not isinstance(inputs,dict) or not inputs:reasons.append('source input hashes missing');inputs={}
    mode=receipt.get('source_hash_mode','sha256')
    mode_valid=mode in ('sha256','sha256-raw','sha256-lf')
    if not mode_valid:reasons.append('unsupported source hash mode')
    stale=[];normalized_inputs={}
    for original_name,digest in inputs.items():
        name=normalized_relative_path(original_name)
        if name is None:
            stale.append(str(original_name));continue
        if name in normalized_inputs and normalized_inputs[name]!=digest:
            stale.append(name)
        normalized_inputs[name]=digest
        path=(root/name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            stale.append(name);continue
        data=path.read_bytes()
        if mode=='sha256-lf':data=data.replace(b'\r\n',b'\n')
        if hashlib.sha256(data).hexdigest()!=digest:stale.append(name)
    inputs=normalized_inputs
    required_recipes={'tools/scripts/eu_build.py','tools/scripts/metadata_build.py','tools/scripts/eu_module_match.py'}
    missing_recipes=required_recipes-inputs.keys()
    if missing_recipes:reasons.append('recipe input hashes missing: '+', '.join(sorted(missing_recipes)))
    if stale:reasons.append('source inputs stale or missing')
    spans=[];previous_end=0
    for module in sorted(receipt.get('credited_c_modules',[]),key=lambda m:m['start']):
        start,end=module['start'],module['end'];source=normalized_relative_path(module['source'])
        if not isinstance(start,int) or not isinstance(end,int) or start<0 or end<=start or end>CODE_END or start<previous_end or max(start,HEADER_START)<min(end,HEADER_END) or module.get('bytes')!=end-start:
            raise ValueError('invalid, overlapping, or header-containing C span')
        if source is None or not source.startswith('src/') or not source.endswith('.c') or '..' in Path(source).parts:
            raise ValueError('C spans require repository source paths')
        if source not in inputs:reasons.append(f'source input hash missing: {source}')
        span={'source':source,'start':start,'end':end,'bytes':end-start}
        for key in ('linked_span_sha256','object_sha256'):
            if not valid_sha256(module.get(key)):reasons.append(f'{key} missing or invalid: {source}')
            if key in module:span[key]=module[key]
        spans.append(span);previous_end=end
    verified=not reasons
    # Keep public JSON bounded to profile, hashes and span evidence, never ROM data.
    credited=sum(s['bytes'] for s in spans) if verified else 0
    code_bytes=CODE_END-(HEADER_END-HEADER_START)
    result={'schema_version':1,'region':'EU','game_code':'AHUP','expected_sha1':EXPECTED,'receipt_original_sha1':receipt.get('original_rom_verified_sha1'),'receipt_rebuilt_sha1':receipt.get('rebuilt_sha1'),'rom_match_verified':verified,'verification_scope':'owned local ROM rebuild receipt; CI does not obtain or rebuild the owned ROM','stale_inputs':stale,'source_hash_mode':mode,'source_inputs_current':mode_valid and bool(inputs) and not stale and not missing_recipes and all(m['source'] in inputs for m in spans),'verification_issues':sorted(set(reasons)),'header_excluded_bytes':HEADER_END-HEADER_START,'code_end_offset':CODE_END,'code_bytes':code_bytes,'credited_c_bytes':credited,'c_percent':round(100*credited/code_bytes,5),'pending_raw_code_bytes':code_bytes-credited,'functions':None,'named_functions':None,'identification_status':'not measured','credited_c_modules':spans if verified else [],'receipt_c_bytes':sum(s['bytes'] for s in spans),'inputs_sha256':inputs,'data_identified_bytes':0,'preserved_asset_bytes':0x800000-CODE_END,'notes':['Raw code spans are pending; they are not disassembled functions.','Original multilingual data unchanged by the verified full-ROM build.' if verified else 'Current inputs do not establish a verified full-ROM build.','USA source coverage is a separate regional measurement; percentages are not combined.']}
    # Retain raw build provenance separately from portable text-input hashes.
    for key in ('source_manifest_sha256','compiler_sha256','compiler_headers_sha256','compiler_flags','builder_sha256'):
        if key in receipt:result[key]=receipt[key]
    return result


def cells(report):
    result=[];cursor=0
    boundaries=[{'source':'Cartridge header (excluded)','start':HEADER_START,'end':HEADER_END,'exclude':True}]+[dict(s,exclude=False) for s in report['credited_c_modules']]
    for span in sorted(boundaries,key=lambda s:s['start']):
        if cursor<span['start']:result.append({'name':'Pending raw code','start':cursor,'bytes':span['start']-cursor,'state':'pending'})
        if not span['exclude']:result.append({'name':span['source'],'start':span['start'],'bytes':span['end']-span['start'],'state':'c'})
        cursor=span['end']
    if cursor<CODE_END:result.append({'name':'Pending raw code','start':cursor,'bytes':CODE_END-cursor,'state':'pending'})
    return result


def treemap_svg(report):
    title='EU AHUP | '+('verified C spans' if report['rom_match_verified'] else 'unverified receipt; no C credit')
    parts=['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="560" viewBox="0 0 1000 560" role="img" aria-labelledby="title desc" font-family="Segoe UI,Helvetica,Arial,sans-serif">',f'<title id="title">{title}</title>','<desc id="desc">Byte-weighted linked C modules and raw pending code. Function count unknown. Cartridge header excluded.</desc>',f'<rect width="100%" height="100%" fill="{render.BG}"/>',f'<text x="14" y="27" fill="{render.FG}" font-size="18">{title}</text>',f'<text x="14" y="52" fill="{render.FG}" font-size="13">C: {report["credited_c_bytes"]:,} / {report["code_bytes"]:,} bytes ({report["c_percent"]:.3f}%) | functions: unknown</text>']
    for cell,x,y,w,h in render.squarify([(c['bytes'],c) for c in cells(report)],8,70,984,390):
        color=render.GREEN if cell['state']=='c' else render.GREY
        tooltip=f"{cell['name']} | 0x{0x08000000+cell['start']:08X} | {cell['bytes']} bytes | {cell['state']}"
        parts.append(f'<rect x="{x:.3f}" y="{y:.3f}" width="{w:.3f}" height="{h:.3f}" fill="{color}" stroke="{render.BG}" stroke-width="0.5"><title>{escape(tooltip)}</title></rect>')
        if w>140 and h>30:parts.append(f'<text x="{x+8:.2f}" y="{y+21:.2f}" fill="{render.FG}" font-size="12">{escape(cell["name"])}</text>')
    lines=['Green: verified C module spans | Grey: pending raw code; no function counts claimed.','Header: 188 bytes excluded. EU and USA percentages measure separate regions.',report['notes'][1],'Evidence: owned local full-ROM rebuild receipt; CI does not own or reproduce the ROM.']
    parts += [f'<text x="14" y="{484+i*20}" fill="{render.FG}" font-size="12">{escape(line)}</text>' for i,line in enumerate(lines)]
    return '\n'.join(parts+['</svg>'])


def markdown(report):
    status='verified against the owned local EU ROM' if report['rom_match_verified'] else 'unverified; no C credit'
    lines=['# Shining Soul Europe (AHUP)','',f'ROM rebuild: **{status}**.',f"Expected SHA1: `{EXPECTED}`.",'',f"Verified C spans: **{report['credited_c_bytes']:,} / {report['code_bytes']:,} bytes ({report['c_percent']:.3f}%)**.",'','The 188-byte cartridge header is excluded. Function count is unknown. Grey regions are raw pending code, not claimed disassembly or functions.','',report['notes'][1],'','This receipt records an owned local ROM rebuild. CI does not obtain or rebuild that ROM. USA source coverage is separate; regional percentages are not combined.']
    if report['verification_issues']:lines+=['','Receipt issues: '+ '; '.join(report['verification_issues'])+'.']
    return '\n'.join(lines)+'\n'


def banner_svg(title,lines):
    """Show unavailable metrics explicitly rather than borrowing USA counts."""
    height=70+28*len(lines)
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="{height}" viewBox="0 0 1000 {height}" role="img" aria-labelledby="title desc" font-family="Segoe UI,Helvetica,Arial,sans-serif">',f'<title id="title">{escape(title)}</title>',f'<desc id="desc">{escape(" ".join(lines))}</desc>',f'<rect width="100%" height="100%" fill="{render.BG}"/>',f'<text x="16" y="30" fill="{render.FG}" font-size="18">{escape(title)}</text>']
    parts += [f'<text x="16" y="{64+i*28}" fill="{render.FG}" font-size="13">{escape(line)}</text>' for i,line in enumerate(lines)]
    return '\n'.join(parts+['</svg>'])


def write_outputs(report,out):
    code_badge=render.badge_svg('EU AHUP verified C',f"{report['c_percent']:.3f}%",render.GREEN if report['rom_match_verified'] else render.GREY)
    rom_badge=render.badge_svg('EU ROM rebuild','verified locally' if report['rom_match_verified'] else 'unverified',render.GREEN if report['rom_match_verified'] else render.GREY)
    # EU is the primary profile. The eu_* filenames remain compatibility aliases.
    content={'progress.json':json.dumps(report,indent=2)+'\n','progress.md':markdown(report),'treemap.svg':treemap_svg(report),'badge_decompiled.svg':code_badge,'badge_rom.svg':rom_badge,
             'names_treemap.svg':banner_svg('EU AHUP | names and functions: not measured',['Complete European function boundaries and name totals are not measured.','Verified C module byte spans earn code credit; no function denominator is invented.','USA names and function totals belong to a separate regional inventory.']),
             'badge_names.svg':render.badge_svg('EU function names','not measured',render.GREY),
             'badge_functions.svg':render.badge_svg('EU C functions','not measured',render.GREY),
             'data.svg':banner_svg('EU AHUP | data preservation and identification',[f"Original asset region: {report['preserved_asset_bytes']:,} bytes.",report['notes'][1],'Identified data formats: 0 bytes (0% credited).','Preservation of multilingual bytes is separate from understanding their formats.']),
             'badge_data.svg':render.badge_svg('EU data identified','0%',render.GREY)}
    for alias,primary in {'eu_progress.json':'progress.json','eu_progress.md':'progress.md','eu_treemap.svg':'treemap.svg','eu_badge_code.svg':'badge_decompiled.svg','eu_badge_rom.svg':'badge_rom.svg'}.items():content[alias]=content[primary]
    for filename,text in content.items():(out/filename).write_text(text,encoding='utf-8')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--report',type=Path,required=True);parser.add_argument('--out',type=Path,default=Path('docs/progress'));parser.add_argument('--root',type=Path,default=ROOT);args=parser.parse_args(argv)
    receipt=json.loads(args.report.read_text()) if args.report.is_file() else {}
    report=assess(receipt,args.root);args.out.mkdir(parents=True,exist_ok=True)
    write_outputs(report,args.out)
    print(json.dumps({k:report[k] for k in ['rom_match_verified','credited_c_bytes','code_bytes','c_percent','verification_issues']},indent=2))
    return 0

if __name__=='__main__':raise SystemExit(main())

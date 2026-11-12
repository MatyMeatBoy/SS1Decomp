#!/usr/bin/env python3
"""ROM-free linked-source inventory; legacy progress.py remains unchanged.

Addresses are deduplicated aliases. Attributed spans include pools/alignment,
not just instructions. Names describe existing symbols, not verified semantics.
"""
import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import shutil
import os
from collections import defaultdict

CODE_END=0x0805289C
HEADER=(0x08000004,0x080000C0)
EXPECTED='14723ead8634959b4fad027d9618c0860b82ea67'
ROOT=pathlib.Path(__file__).resolve().parents[2]


def original_object(path):
    path=path.replace('\\','/')
    match=re.search(r'(?:^|/)((?:src|asm|data)/.+\.o)$',path)
    return match[1] if match else path


def parse_map(text):
    """GNU ld input sections, including line-wrapped section names."""
    result=[]
    pending=None
    for line in text.splitlines():
        match=re.match(r'^\s+(\.\w+)\s+0x([\da-fA-F]+)\s+0x([\da-fA-F]+)\s+(\S+\.o)\s*$',line)
        if match:
            sec,addr,size,obj=match.groups()
        else:
            short=re.match(r'^\s+(\.\w+)\s*$',line)
            if short: pending=short[1];continue
            wrapped=re.match(r'^\s+0x([\da-fA-F]+)\s+0x([\da-fA-F]+)\s+(\S+\.o)\s*$',line)
            if not wrapped or not pending:pending=None;continue
            sec=pending;addr,size,obj=wrapped.groups()
        pending=None
        if int(size,16) and int(addr,16)>=0x08000000:
            result.append({'section':sec,'addr':int(addr,16),'size':int(size,16),'object':original_object(obj)})
    return result


def parse_nm(text):
    """Legacy nm filter, then canonicalize aliases by normalized address."""
    addresses=defaultdict(set)
    for line in text.splitlines():
        parts=line.split()
        if len(parts)==3 and parts[1] in 'Tt' and not parts[2].startswith(('_0','$','.')):
            addresses[int(parts[0],16)&~1].add(parts[2])
    return [{'addr':a,'name':sorted(ns,key=lambda n:(n.startswith('sub_'),n))[0],
             'aliases':sorted(ns)} for a,ns in sorted(addresses.items())]


def category(obj):
    return 'lib' if obj.startswith(('src/lib/','asm/lib/')) or obj=='asm/code_0804FAA8.o' else 'game'


def original_asm(obj, address=None):
    # SDK m4a assembly and CPU context/startup routines are written in assembly.
    # emmkay's cross-game comparison identifies the cooperative scheduler as
    # hand-written in both games (SS2 issue79, comment6508603523). The next
    # function at 0x080004A4 is a separate pending division wrapper.
    if obj == 'asm/code.o' and address is not None:
        return 0x0800023C <= address < 0x080004A4
    return obj in {'asm/crt0.o','asm/code_0804FAA8.o','asm/lib/m4a_1.o','asm/lib/libagbsyscall.o','asm/lib/libgcc.o'}


def subtract_header(lo,hi):
    return max(0,hi-lo)-max(0,min(hi,HEADER[1])-max(lo,HEADER[0]))


def inventory(sections,symbols,code_end=CODE_END):
    modules=[];compat={'game_code_bytes':0,'game_code_c_bytes':0,'lib_code_bytes':0,'lib_code_c_bytes':0}
    for sec in sections:
        if sec['section']!='.text' or sec['addr']>=code_end:continue
        lo=sec['addr'];hi=min(lo+sec['size'],code_end);obj=sec['object'];cat=category(obj)
        legacy='lib' if obj.startswith(('src/lib/','asm/lib/')) else 'game'
        compat[legacy+'_code_bytes']+=hi-lo
        if obj.startswith('src/'):compat[legacy+'_code_c_bytes']+=hi-lo
        functions=[];inside=[s for s in symbols if lo<=s['addr']<hi]
        for i,symbol in enumerate(inside):
            end=inside[i+1]['addr'] if i+1<len(inside) else hi
            size=subtract_header(symbol['addr'],end)
            if size:
                functions.append(dict(symbol,size=size,state='done' if obj.startswith('src/') else 'asm' if original_asm(obj,symbol['addr']) else 'todo',named=any(not n.startswith(('sub_','_start')) for n in symbol['aliases'])))
        # Account for bytes before the first eligible symbol without inventing a function.
        prefix=subtract_header(lo,inside[0]['addr'] if inside else hi)
        modules.append({'name':obj,'object':obj,'cat':cat,'size':subtract_header(lo,hi),'funcs':functions,'unattributed_bytes':prefix})
    result={'schema_version':1,'measurement':'linked source coverage; not ROM match verification','rom_match_verified':False,'header_excluded_bytes':sum(max(0,min(s['addr']+s['size'],HEADER[1])-max(s['addr'],HEADER[0])) for s in sections if s['section']=='.text'),'modules':modules,'legacy_compatibility':compat}
    for cat in ('game','lib','all'):
        mods=[m for m in modules if cat=='all' or m['cat']==cat];fs=[f for m in mods for f in m['funcs']];total=sum(m['size'] for m in mods);c=sum(m['size'] for m in mods if m['object'].startswith('src/'))
        result[cat]={'bytes':total,'c_bytes':c,'c_percent':round(100*c/total,3) if total else 0,'functions':len(fs),'c_functions':sum(f['state']=='done' for f in fs),'named_functions':sum(f['named'] for f in fs),'original_asm_bytes':sum(f['size'] for f in fs if f['state']=='asm'),'pending_asm_bytes':sum(f['size'] for f in fs if f['state']=='todo'),'unattributed_bytes':sum(m['unattributed_bytes'] for m in mods)}
    result['data']={'preserved_bytes':sum(s['size'] for s in sections if s['section']=='.rodata'),'identified_bytes':0,'identified_percent':0,'note':'Opaque data preserved by the original build; metadata substitutes zeros. No format-identification credit.'}
    return result


def rom_match_verified(root,metadata=False):
    if metadata:return False
    files=[root/'baserom.gba',root/'shiningsoul.gba']
    return all(f.is_file() and hashlib.sha1(f.read_bytes()).hexdigest()==EXPECTED for f in files)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metadata-dir',type=pathlib.Path)
    parser.add_argument('--root',type=pathlib.Path,default=ROOT)
    parser.add_argument('--out',type=pathlib.Path,default=pathlib.Path('docs/progress'))
    nm = shutil.which('arm-none-eabi-nm')
    if not nm and os.name == 'nt':
        candidate = pathlib.Path('C:/msys64/ucrt64/bin/arm-none-eabi-nm.exe')
        if candidate.is_file():
            nm = str(candidate)
    parser.add_argument('--nm',default=nm or 'arm-none-eabi-nm')
    args=parser.parse_args(argv);directory=args.metadata_dir or args.root
    symbols=subprocess.run([args.nm,'-n','--defined-only',str(directory/'shiningsoul.elf')],check=True,capture_output=True,text=True).stdout
    report=inventory(parse_map((directory/'shiningsoul.map').read_text()),parse_nm(symbols))
    report['metadata_only']=bool(args.metadata_dir)
    report['rom_match_verified']=rom_match_verified(args.root,bool(args.metadata_dir))
    report['notes']=['Aliases deduplicated by address; legacy compatibility bytes retain upstream object classification and include header.','Function areas include literal pools/alignment; existing names are not independently confirmed semantics.','Green means linked C source coverage. Only the separate ROM verification status establishes an exact build match.']
    import progress_render as render
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/'progress.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    for filename,svg in [('treemap.svg',render.treemap_svg(report)),('names_treemap.svg',render.names_treemap_svg(report)),('data.svg',render.data_svg(report))]:
        (args.out/filename).write_text(svg,encoding='utf-8')
    for filename,label,value in [('badge_decompiled.svg','C source coverage',f"{report['all']['c_percent']:.2f}%"),('badge_functions.svg','C functions',f"{report['all']['c_functions']}/{report['all']['functions']}"),('badge_names.svg','existing game names',f"{report['game']['named_functions']}/{report['game']['functions']}"),('badge_data.svg','data identified','0%'),('badge_rom.svg','ROM match','verified' if report['rom_match_verified'] else 'not verified')]:
        (args.out/filename).write_text(render.badge_svg(label,value,render.GREEN if report['rom_match_verified'] or filename!='badge_rom.svg' else render.GREY),encoding='utf-8')
    (args.out/'progress.md').write_text(render.markdown(report),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('metadata_only','rom_match_verified','game','lib','all')},indent=2))
    return 0

if __name__=='__main__':raise SystemExit(main())

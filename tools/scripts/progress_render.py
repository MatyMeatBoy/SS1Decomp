"""Dark SVG progress rendering adapted from SS2Decomp tools/scripts/progress.py.
Rendering code from MatyMeatBoy/SS2Decomp and its contributors.
Original SS1 project: emmkay440; SS1 continuation: MatyMeatBoy. Source revision:
MatyMeatBoy/SS2Decomp@698bbe6af4968fa6b9eefb01bcf0ae16639da681
(tools/scripts/progress.py); preserves emmkay440 attribution.
"""
from html import escape
BG='#0d1117'
FG='#e6edf3'
GREEN='#238636'
MINT='#39c5aa'
GREY='#484f58'
def squarify(items, x, y, w, h):
    """items: list of (weight, obj). Returns list of (obj, x, y, w, h)."""
    items = [(v, o) for v, o in items if v > 0]
    items.sort(key=lambda t: -t[0])
    total = sum(v for v, _ in items)
    if total <= 0 or w <= 0 or h <= 0:
        return []
    scale = w * h / total
    rects = []
    rest = [(v * scale, o) for v, o in items]

    def worst(row, side):
        s = sum(r for r, _ in row)
        if s == 0:
            return float("inf")
        mx = max(r for r, _ in row)
        mn = min(r for r, _ in row)
        return max(side * side * mx / (s * s), (s * s) / (side * side * mn))

    while rest:
        side = min(w, h)
        row = [rest[0]]
        i = 1
        while i < len(rest) and worst(row + [rest[i]], side) <= worst(row, side):
            row.append(rest[i])
            i += 1
        rest = rest[i:]
        s = sum(r for r, _ in row)
        if w >= h:
            cw = s / h
            cy = y
            for r, o in row:
                ch = r / cw
                rects.append((o, x, cy, cw, ch))
                cy += ch
            x += cw
            w -= cw
        else:
            rh = s / w
            cx = x
            for r, o in row:
                cwid = r / rh
                rects.append((o, cx, y, cwid, rh))
                cx += cwid
            y += rh
            h -= rh
    return rects


def badge_svg(label, value, color):
    def tw(s):
        return int(len(s) * 6.6 + 12)
    lw, vw = tw(label), tw(value)
    w = lw + vw
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="20" role="img" aria-label="%s: %s">'
            '<linearGradient id="s" x2="0" y2="100%%"><stop offset="0" stop-color="#bbb" stop-opacity=".1"/>'
            '<stop offset="1" stop-opacity=".1"/></linearGradient>'
            '<clipPath id="r"><rect width="%d" height="20" rx="3" fill="#fff"/></clipPath>'
            '<g clip-path="url(#r)"><rect width="%d" height="20" fill="#555"/>'
            '<rect x="%d" width="%d" height="20" fill="%s"/><rect width="%d" height="20" fill="url(#s)"/></g>'
            '<g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" '
            'font-size="11"><text x="%.1f" y="15" fill="#010101" fill-opacity=".3">%s</text>'
            '<text x="%.1f" y="14">%s</text><text x="%.1f" y="15" fill="#010101" fill-opacity=".3">%s</text>'
            '<text x="%.1f" y="14">%s</text></g></svg>') % (
        w, escape(label), escape(value), w, lw, lw, vw, color, w,
        lw / 2, escape(label), lw / 2, escape(label), lw + vw / 2, escape(value), lw + vw / 2, escape(value))


def _code_treemap_svg(report,names=False,width=1000,height=620):
    """Function area is proportional to attributed bytes within each partition."""
    title='Shining Soul | '+('existing function names' if names else 'linked C source coverage')
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc" font-family="Segoe UI,Helvetica,Arial,sans-serif">',f'<title id="title">{title}</title>','<desc id="desc">Byte-weighted function spans include literal pools and alignment. Game and SDK panels use separate scales. ROM verification is a separate status.</desc>',f'<rect width="100%" height="100%" fill="{BG}"/>',f'<text x="12" y="24" fill="{FG}" font-size="17">{title}</text>']
    status='verified' if report['rom_match_verified'] else 'not verified'
    parts.append(f'<text x="12" y="46" fill="{FG}" font-size="12">ROM match: {status} | metadata is never ROM verification | cartridge header excluded</text>')
    for cat,x,w,label in [('game',0,width*.80,'Game code'),('lib',width*.80,width*.20,'SDK libraries')]:
        total=report[cat]
        detail=f"{total['named_functions']}/{total['functions']} named" if names else f"{total['c_percent']:.2f}% C"
        parts.append(f'<text x="{x+6:.1f}" y="72" fill="{FG}" font-size="12">{label}: {detail}</text>')
        mods=[m for m in report['modules'] if m['cat']==cat]
        for module,mx,my,mw,mh in squarify([(m['size'],m) for m in mods],x+2,82,w-4,height-150):
            parts.append(f'<g><title>{escape(module["name"])}: {module["size"]} bytes</title>')
            cells=list(module['funcs'])
            if module['unattributed_bytes']:
                cells.append({'name':'Unattributed span','addr':0,'size':module['unattributed_bytes'],'state':'todo','named':False,'aliases':[]})
            for f,fx,fy,fw,fh in squarify([(f['size'],f) for f in cells],mx,my,mw,mh):
                color=(GREEN if f['named'] else GREY) if names else {'done':GREEN,'asm':MINT,'todo':GREY}[f['state']]
                state=('existing name' if f['named'] else 'unnamed') if names else {'done':'linked C source','asm':'original assembly','todo':'pending assembly'}[f['state']]
                tooltip=f"{f['name']} | 0x{f['addr']:08X} | {f['size']} bytes | {state} | {module['name']} | aliases: {', '.join(f['aliases'])}"
                parts.append(f'<rect x="{fx:.3f}" y="{fy:.3f}" width="{max(0,fw):.3f}" height="{max(0,fh):.3f}" fill="{color}" stroke="{BG}" stroke-width="0.5"><title>{escape(tooltip)}</title></rect>')
                if fw>100 and fh>26:
                    text=f['name'];limit=max(4,int((fw-8)/5.5));text=text if len(text)<=limit else text[:limit-3]+'...'
                    parts.append(f'<text x="{fx+4:.2f}" y="{fy+14:.2f}" fill="{FG}" font-size="10" pointer-events="none">{escape(text)}</text>')
            parts.append('</g>')
    legend=[(GREEN,'existing name'),(GREY,'unnamed')] if names else [(GREEN,'linked C source'),(MINT,'original assembly'),(GREY,'pending assembly')]
    x=12
    for color,label in legend:
        parts.extend([f'<rect x="{x}" y="{height-49}" width="12" height="12" fill="{color}"/>',f'<text x="{x+18}" y="{height-39}" fill="{FG}" font-size="11">{label}</text>']);x+=len(label)*6+45
    parts.append(f'<text x="12" y="{height-16}" fill="{FG}" font-size="11">Area = attributed bytes incl. pools/alignment; SDK panel enlarged. Names earn no C or ROM-match credit.</text></svg>')
    return '\n'.join(parts)


def treemap_svg(report):return _code_treemap_svg(report)
def names_treemap_svg(report):return _code_treemap_svg(report,names=True)


def data_svg(report):
    data=report['data'];title='Shining Soul | data preservation and identification'
    lines=[f"Opaque preserved data: {data['preserved_bytes']:,} bytes",'Identified formats: 0 bytes (0% credited)','Metadata-only builds substitute zero storage; game assets are not published.','Cartridge header: 188 excluded bytes; startup branch remains code.','Preservation is not identification or ROM verification.']
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="210" role="img" aria-labelledby="title desc" font-family="Segoe UI,Helvetica,Arial,sans-serif"><title id="title">{title}</title><desc id="desc">Opaque data receives no format-identification credit.</desc>',f'<rect width="100%" height="100%" fill="{BG}"/>',f'<text x="16" y="28" fill="{FG}" font-size="17">{title}</text>']
    parts += [f'<text x="16" y="{62+i*27}" fill="{FG}" font-size="13">{escape(line)}</text>' for i,line in enumerate(lines)]
    return '\n'.join(parts+['</svg>'])


def markdown(report):
    lines=['# Shining Soul progress','',f"ROM match: **{'verified' if report['rom_match_verified'] else 'not verified'}**.",'','Linked source coverage; function spans include literal pools/alignment. Aliases are deduplicated by address. Cartridge header bytes are excluded.','','| Partition | C bytes / code bytes | C functions / functions | Existing names |','|---|---:|---:|---:|']
    for cat,label in [('game','Game'),('lib','SDK libraries'),('all','All code')]:
        s=report[cat];lines.append(f"| {label} | {s['c_bytes']:,} / {s['bytes']:,} ({s['c_percent']:.3f}%) | {s['c_functions']} / {s['functions']} | {s['named_functions']} / {s['functions']} |")
    lines+=['',f"Opaque data preserved: {report['data']['preserved_bytes']:,} bytes. Identified formats: 0 bytes (0%).",'','Green cells mean linked C source coverage. Existing names do not establish semantics. Original assembly is separate from pending assembly.','', 'Generated from the linked ELF/map. Metadata-only output cannot establish an exact ROM match.','']
    return '\n'.join(lines)

# Reusing the completed SS2 decompilation

SS1 upstream baseline: `52c0fa73870fab238941e32be7eff172e9bad71f`.
The [candidate manifest](ss2-transfer-candidates.json) pins both source revisions.
Its similarity numbers are historical leads from emmkay440's issue79 comparison,
not newly measured matching scores.

All eleven historical candidates are still linked assembly at this baseline.
Their combined address spans are 10,180 bytes, including pools and alignment.
None has been imported or credited as matching C by this investigation.

| Priority | SS1 | SS2 | SS1 span | Useful reference and constraints |
|---|---|---|---:|---|
| 1 | `sub_0802CA30` | `sub_08075088` | 1,040 | Three-projectile control flow. Replace resource IDs, Q8 with Q12 positions, speed/damage formulas and game-specific structure strides. |
| 2 | `sub_08004AE4` | `sub_08009594` | 764 | Shared scrolling core. SS1 selects a map-layer bank; SS2 uses different globals and level dispatch. |
| 3 | `sub_0800C8F8` | `sub_08096154` | 244 | Player-distance ordering. SS1 uses six-bit layer filtering, ordinary paired swaps, Q12 coordinates and an integer radius. |

The upstream queue and `docs/NEXT.md` reference near-match drafts in ignored
`tmp/drafts/`; those files are absent from the fresh fork. Recovering the
historical four-normalized-difference `sub_0802CA30` draft is preferable to
starting that work again. The historical nearest-player draft was also closer
than a fresh implementation.

## First bounded experiment

A fresh nearest-player C draft was tried in an isolated checkout using nineteen
natural source forms. Its best output was 236 bytes against the original
244-byte assembly span, with 83 changed normalized instruction lines. It was
not integrated. The scratch draft and attempt log remain local for follow-up.
No full-ROM verification was possible without the owner's AHUE ROM.

## Working sequence

1. Verify the USA ROM SHA1 and reproduce the untouched upstream build.
2. Recover existing near-match drafts before repeating register-allocation work.
3. Read both complete bodies and follow helper aliases and data consumers.
4. Adapt one SS1 function at a time in an isolated checkout; compare assembly
   at SS1 addresses, not against SS2 bytes or a universal address delta.
5. Run the real `make compare`; only successful byte-identical builds earn C
   credit. Keep failed attempts in `tmp/drafts/`, preserving linked assembly.

The [SS2 giant-function playbook](https://github.com/MatyMeatBoy/SS2Decomp/blob/claude/rom-decompilation-research-obsal6/docs/agents/GIANT_FUNCTION_PLAYBOOK.md)
also transfers useful compiler lessons: fix source structure before register
pins, separate genuine control-flow differences from allocation noise, and
validate the real linked build after each successful local experiment.

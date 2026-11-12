# SS1Decomp — contributor notes

Matching decompilation of Shining Soul. Europe (`AHUP`) is the primary profile;
the original USA (`AHUE`) source tree is preserved. See README.md for the
layout and tools, docs/NEXT.md for the task list, docs/RESEARCH.md for the
mGBA tracing workflow, docs/variables.md for RAM/struct findings.

## Rules

- The affected regional full-ROM gate must pass after every game-code,
  assembly, header, linker, ROM-profile or ordinary compiler-rule change.
  Default `make compare` verifies Europe; `make REGION=us compare` verifies USA. Use
  `make check FUNC=Name` / `make diff` to find mismatches.
- Never commit or copy game data. Everything that isn't code is `.incbin`'d
  from the user's `baserom.gba`.
- The PC port (`../shiningsoul-pc`) is not a focus for now. Don't spend
  effort on it; matching the ROM comes first. (Using the `include/gba/`
  register macros instead of raw addresses is still the normal style.)
- Names you can't verify are guesses: say so in a comment.
- Git: commit progress whenever `make compare` succeeds (gate on its exit
  status: `make compare && git commit`, no pipes)
  (check that no ROM, saves, traces or build output are staged). Never
  commit a non-matching build. Never push; pushing is only done when the
  user explicitly asks.

### Reporting-only work in this fork

The MatyMeatBoy fork also publishes ROM-free progress in the SS2 style. A change
limited to documentation, progress tooling/tests, isolated metadata targets and
their CI may use the metadata/test gate when no game sources, assembly, headers,
linker files, ROM profiles or existing game compiler recipes change. Run the
focused tests, rebuild all isolated metadata objects, verify the expected code
boundary and inspect the generated views. This exception does not establish a
matching ROM or permit integration of a game-code draft.

Metadata objects must remain under `build/metadata/`; they must never replace
ordinary objects or create a ROM. Publish only the JSON/Markdown/SVG reports,
with `rom_match_verified: false`. Keep the ordinary USA `make compare` gate for
all game-code work. A Europe AHUP dump cannot satisfy the USA AHUE SHA1 check.

For the European profile, `make compare-eu` must reproduce the owned AHUP ROM
exactly (full bytes and SHA1) before any shared C span earns EU credit. Its raw
fallback spans remain pending, not decompiled assembly. Keep USA and EU metrics
separate and preserve all multilingual assets. `make record-eu` records only the
verification receipt after the complete EU gate succeeds. A shared-source change
requires verification for every affected build profile; use isolated EU-specific
source work rather than silently breaking the preserved USA build.

## Current state (2026-10-19)

841 / 977 game functions are matching C (`make progress`); every module in
`src/` matches. Next steps are in docs/NEXT.md; trace sessions still to
analyze are in docs/TRACES.md. RAM/struct findings: docs/variables.md;
ROM data formats: docs/data.md.

## Local-model loop (tools/autodecomp)

The user may run `tools/autodecomp/run.sh` on a work branch: a local model
decompiles small functions into `src/ad_<name>.c` and commits matches. Before
working, check it isn't running (`pgrep -f autodecomp.py`); if it is, ask
the user or `touch tools/autodecomp/STOP` and wait. Its output needs review:
merge `ad_*` files into real modules, name things, fix style.

## Workflow

- Decompiling: `tools/scripts/split_asm.py asm/code.s First Next module` →
  write `src/module.c` → switch `asm/module.o` to `src/module.o` in
  `ld_script.ld` → `make compare`. Example: `src/copy_queue.c`.
- Nintendo library C goes in `src/lib/` (counted as library by `make progress`).
- Game code is built with `agbcc -fprologue-bugfix` (without the flag,
  leaf functions with branches get a `push {lr}` the original doesn't have;
  `old_agbcc` gets that right but allocates registers differently). Only
  the m4a library uses `old_agbcc` (Makefile override).
- Functions that come close but don't match go to `tmp/drafts/` and stay asm.
- Fake matches are accepted when nothing natural is found, as long as the
  code does the same thing (never a permuter candidate that reads an
  uninitialized variable). Mark each with a `FAKE (who found it): what it
  does` comment and add it to docs/FAKES.md.
- Permuter queue: once a draft's logic is right and only registers, stack
  slots or instruction order are off, don't keep tuning it by hand. Add it
  to `config/permute_queue.txt` and move on to other functions; the
  permuter runs over the queue for long periods
  (`tools/scripts/permute_queue.sh [secs_each] [jobs]`, detached with
  `nohup setsid ... &`; `touch tmp/permute/STOP` ends it after the current
  function). The user approved ~85% CPU (2026-10-27): run it as two queues
  with `tools/scripts/permute_split.sh 3600 7 6` (7 + 6 jobs of 16 cores). Check `tmp/permute/queue.log` and the best outputs later:
  build them (`tools/scripts/dcheck.sh`, then the real tree) before
  accepting, and record fakes as above.
- Matching tricks that worked: return-0/1 layout follows if/else order
  (flip the condition or use a result variable); `x & (1 << i)` vs
  `(1 << i) & x` changes scheduling; per-layer code duplicated in both
  branches (compiler merges tails); an unused parameter or `return arg` to
  keep r0 live; separate `rest`/temp variables to change register choice;
  an `inline` function's standalone copy moves to the end of the file.
- Bitfields read with `ldrb` + `lsls`/`lsrs` extraction (not `ldr`): a
  `__attribute__((packed))` struct of `u8` bitfields, with the field read
  into a temporary before comparing (`src/equipment.c`). Comparing the field
  directly with a constant folds into an `ands`/`cmp` mask test instead.
  For a halfword load (`ldrh`) of a bitfield: `__attribute__((packed, aligned(2)))`
  on a struct of `u16` bitfields (`src/stats.c`, sub_0801702C).
- Thread setup (`t->stack = Alloc(n); t->sp = stack + n - 4`) comes in three
  shapes that allocate registers differently: a `u8 *stack` local, a chained
  `t->sp = (u8 *)(t->stack = Alloc(n)) + n - 4`, or no local with
  `t->sp = (u8 *)t->stack + n - 4` (it doesn't reload). Try all three
  (`src/thread_starters.c`, `src/item_use_effect.c`). A free-slot loop over
  an in-use mask that re-reads the mask each iteration means the mask is
  `volatile` (`src/effect_pool.c`).
- Code that looks like an inlined call with a constant argument (e.g.
  `EnableIntr(INTR_FLAG_HBLANK)` inside another function) matches with a
  `static inline` helper taking the value as a parameter.
- The game read REG_VCOUNT without `volatile` (`*(u16 *)REG_ADDR_VCOUNT`
  matched FrameUpdate; the volatile macro didn't).
- agbcc quirks: every struct/union is 4-byte aligned (so a nested struct
  can't sit at offset 2); bitfield stores use the narrowest access that
  covers the bits; separate globals give one literal per variable while
  struct fields give base + offset; `&array[i].field` folds into one literal,
  loading the field doesn't.
- More shapes that mattered (2026-10-10):
  - `ldr rX, =gPtr` before a `bl Alloc` whose result is stored there: a
    pointer local (`void **p = &gPtr; *p = Alloc(n);`). Same for a loop that
    should load the struct base once and add the offset
    (`struct PlayerStats *stats = &gPlayerStats;`).
  - Two compares for a range (`cmp #43; bgt; cmp #40; bge`) instead of a
    subtract + unsigned compare: a `switch` with one `case` per value.
  - An `||` chain comparing adjacent fields gets merged into one wider
    compare; separate `if (...) return TRUE;` statements keep them apart.
  - A value known to equal the tested variable is passed as the register
    (`if (step == 1) f(..., 1)` passes `step`'s register): write the constant.
  - `u8`/`u16` parameters whose `lsrs` happens at each use, not at entry:
    declare them `u32` and let the callee's prototype narrow them.
  - Chunk loops `for (i = 0; i < count; i++) f(src + i * N, ...)` count down
    only when `i` and `count` are `s32`.
  - Base + small offsets (`strb r0, [r4, #2]`) on a global struct that the
    code otherwise reaches as `&g.field`: use a struct with plain byte fields
    (`struct MenuSlotBytes`), not the `u8 *` cast macros.
  - A byte built as `14 | (x << 4)` with `movs r0, #14; orrs r0, r2`: two
    4-bit bitfield stores, not shifts.
  - `while (--n != -1)` (not `n-- != 0`) for `subs; cmp rX, #-1`.
  - Compare trees: three case values tested as `== 2; <= 2 -> out; == 3;
    == 4` (pivot on the second of four) mean the switch had a fourth case
    below them that does nothing (`case 1: return;`). Cases that share one
    body but are tested one by one each had their own copy of the statement
    (`case 2: x = f(); break; case 3: x = f(); break;`).
  - A 4-bit field read as `ldrb; lsls #28; lsrs #28; cmp`: read the `u8`
    bitfield into a `u32` local first (`u32 kind = e->unk4.k.kind;`);
    comparing it directly folds into a mask test.
  - Swapped callee-saved registers in a search loop: cache the global count
    in a local (`for (i = 0, count = gCount; i < count; ...)`).
  - Selecting one of two globals and then updating a field: write the update
    in both branches (`if (c) gA.flags |= 0xC; else gB.flags |= 0xC;`).
  - Don't swap the local `bzero`/`memcpy` prototypes for agbcc's `<string.h>`:
    with the real `size_t` prototype the compiler expands `memcpy` inline and
    the ROM stops matching (the "conflicting types for built-in" warning in
    `src/palette_save.c` is expected).
- Variable reuse decides registers. When everything matches except which
  register holds a value, look for a variable the original used twice:
  a parameter used as a temporary (`b = (b * t) / 1024;` in Lerp1024,
  `layers &= 0x1F00`), one `u8` for two unrelated bytes (`hi` in Random),
  one pointer for two globals (`thread` in sub_0803F060). Other things that
  showed up the same day: a `u8`-returning `static inline` keeps the
  `movs r0, #1 / #0; cmp r0, #0` of an inlined bool test (sub_08041208);
  32-bit temporaries for 16-bit register math (EnableDisplayLayers);
  `record[0]` twice instead of `*record++` (sub_080060A0).
- Shapes decomp-permuter found (2026-10-10/11), worth trying by hand when a
  function is a few lines off:
  - `do { ... } while (0)` around a statement, a branch or the whole body
    (probably macros in the original). It changes loop depth, and with it
    register priority and what gets hoisted (`sub_08013B94`,
    `sub_0800EDBC`, `Free`).
  - A loop entered by a jump to its test (`b check` and no duplicated
    test): `do { goto check; } while (0); do { ...; check: ; } while (c);`.
  - Constants in local variables (`last = 11; first = 9;` in
    `sub_08045D80`), an `int` temporary for an index, a value copied to a
    second variable before it is stored to a register (`DisableDisplayLayers`).
  - A read through a `vu16 *` when a global is loaded into its own register
    before being combined.
- Other shapes from the same days: the flags argument computed by an
  `if/else` right before the call, with `item++` as the argument
  (`src/menu_draw.c`); a signed class compare (`bgt`) from
  `switch ((s32)GetPlayerClass())`; `if (p != NULL) {...} else { return 0; }`
  to put that `return 0` last; a 2D view of a flat array
  (`((u16 (*)[16])gPaletteBuffer)[i][j]`) for `row * 32 + (col * 2 + base)`.
- Shapes from 2026-10-12:
  - Colors are `struct Color { u16 r:5; u16 g:5; u16 b:5; }`, not packed
    (`src/palette_fade_*.c`, `palette_fill.c`). Through a pointer the
    value is read with a 32-bit `ldr`, a `!= 0` test becomes a byte or
    halfword mask test, and stores use the narrowest access. Indexing the
    global array (`gUnknown_03000A58[row][i].r`) reads with `ldrb`/`ldrh`
    instead; a `saved = &array[row][i]` pointer turns those into `ldr`.
    The struct is 4 bytes, which is why the saved palette has a word per
    color.
  - A byte load in a loop whose result is never used: a volatile read
    (`*(vu8 *)&p[i].kind;`). An unused local struct still gets its stack
    space (`src/save_select_mode3_add.c`).
  - `cmp count, #0; beq` before a loop that then tests `i < count` at the
    bottom: `i = 0; if (count != 0) { do { ...; i++; } while (i < count); }`.
    A `for` gives `cmp i, count; bhs`.
  - A constant that stays grouped with one operand (`r1 = offset - 0x40;
    r0 = x - r1`): a narrowing cast on the group, `x - (s16)(offset - 0x40)`.
    Without it the compiler reassociates.
  - `a + b` and `b + a` give different operand order in the `adds` and can
    change which loop invariant is hoisted first (`sub_0804E464`).
  - Arguments narrowed in a different order than the parameters, or after
    other entry code: `s32` parameters copied into `s16` locals in that
    order (`sub_0800C9EC`).
  - A caller that sign-extends `s16` arguments for a function taking `u16`,
    or passes an argument to a function that takes none, called it without
    a prototype: keep it in another file and declare it with `s32`
    parameters there (`sub_0804A074`, still asm).
  - A stack parameter loaded right before the loop rather than at entry: a
    local copy made there (`out = dest;` in `sub_08004288`).
  - Two distances that end up in the registers of their inputs: the
    result was stored back into the input variable (`x = abs(x - otherX)`,
    `sub_08016C34`). It also keeps the sign extension of a value the
    compiler would otherwise know to be small.
- Shapes from 2026-10-13:
  - The sprite object wrappers (`sub_08026C40`, `sub_08026B90` in
    `src/sprite_obj.c`) are also inlined into callers: the tell is a
    constant argument loaded into a register before the other arguments
    (`movs r0, #1` ahead of `ldr r3, [r5, #8]`), `&local` recomputed for
    the call although it is hoisted in a register, or a `u16` constant
    built as `movs #2; lsls #16; ... lsrs #16`. Write `static inline`
    copies in the file (`src/player_rise_effect.c`).
  - A small count/search loop whose result is copied to a second register
    (`adds r4, r3, #0`) before the next call is an inlined function too
    (`CountActive` in `src/save_select_mode4_add.c`, `FindFreeParticle`
    in `src/save_select_mode7.c`).
  - `s16` parameters are narrowed at entry with `lsls`/`lsrs` like `u16`
    ones and sign-extended (`lsls`/`asrs`) at each use; a `== 0` test on
    one is `lsls r0, rX, #16; cmp r0, #0`. A `u16` parameter with `(s16)`
    casts gives different code (`sub_0804C0A8`).
  - `asrs; cmp #0; bge; rsbs` right after a call: the builtin `abs()`
    (declare `int abs(int x);`), not a temporary and an `if`.
  - A call followed by a lone `lsls r0, r0, #16` whose result is not used:
    an `if (Random() > 0) x = 2; else x = 2;` with both arms the same. The
    arms get merged late, the shift stays (`sub_0804AA10`).
  - `sub sp` larger than the locals in use, with word-sized stores through
    `mov rX, sp`: a local array (`s16 pos[2]`), which always lives on the
    stack (`src/map_edge.c`).
  - `(a + 0x60) - b` kept in that order: `(s16)(a + 0x60) - b`. Same cast
    trick as `x - (s16)(offset - 0x40)`.
  - A `u16` countdown tested as `subs; ...; cmp old, #0` (the old value)
    is `while (n-- > 0)`; `n-- != 0` compares the new value with 0xFFFF.
  - Loop-invariant values appear before the loop in the order the loop
    uses them. If `x << 16` is stored before the hoisted `&local`
    addresses, it was a variable set before the loop (`fixedX = x << 16`,
    used as `fixedX >> 16`), not a hoisted `(s16)x` (`sub_08018058`).
  - Stack layout follows the order in which locals get their slot: arrays
    at their declaration, scalars when their address is first taken. A
    slot order that doesn't fit one declaration list means an inner block
    (see the draft of `sub_08024320`).
- Shapes from 2026-10-13, second batch:
  - A value and a copy of it in two registers (`lsrs r1, r0, #1; adds r3,
    r1, #0`), one used for stores and one in compares: an `s32` variable
    plus a `u16` copy (`size = w >> 1; half = size;`). Which register each
    gets depends on whether the neighbouring variable is shared between
    two similar blocks or separate (`posX`/`posY` in `sub_08021874`):
    variables that live across blocks are allocated by priority over the
    whole function. A small grid search over types / shared-or-separate /
    declaration order with `fcheck.py` in a loop settles these in a minute.
  - `x + ((w >> 1) + 1)` computed as `r0 = w >> 1; r0 += 1; r0 = x + r0`:
    an `s32` temporary for the group (`t = (w >> 1) + 1; p->x = x + t;`).
  - A `cmp #2; blt`-style lower bound, output-address temporaries taken
    at the top of a loop body (they set giv order), declaration order
    (it sets spill-slot order), and a callee declared as returning `int`
    (removes the caller's narrowing) all mattered in `sub_08029560` /
    `sub_0803ECBC`.
  - A table's address loaded before the index is scaled (`ldr r1, =table;
    ldr r2, [sp]; lsls r0, r2, #4; adds r0, r0, r1`): a pointer local for
    the table (`table = gTable; entry = &table[kind];`, `sub_08029688`).
  - `ands #15` followed by `asrs #6` that the compiler didn't fold to 0:
    a signed division, `(x & 0xF) / 64` (`CalcDamageToPlayer`). `>> 6`,
    an unsigned divide or temporaries all fold.
  - A bitfield compared with 0 as `lsls; lsrs; cmp #0` instead of a mask
    test: read it into a `u32` local first (same rule as the `u8` ones;
    `layer` in `sub_0800B78C`).
  - `ldrsh` of a `u16` field next to a separate `ldrh` of the same field:
    `(s16)p->field` at each use, not a local and not an `s16` field.
  - Loop exit tests: `expand_end_loop` (tools/agbcc/gcc/stmt.c) moves the
    code from the loop start up to the *first* jump to the loop's exit
    label to the bottom (once that test is more than 30 insns in, it
    stops looking). So in `while (a && b)` with a long `a` only `a` ends
    up at the bottom and `b` stays at the top of the body. To get both at
    the bottom the first one must not be a plain exit jump:
    `while (a ? b : FALSE)` (`AddItemToInventory`).
    The same rule for a `do { } while (a && b && c)` whose tests all sit
    at the bottom in the original: with `&&` the body up to the first
    test is moved below the others. Write `do { ...; if (!a || !b || !c)
    break; } while (1);` (one `if`, one `break`; `sub_08033CC8`).
  - `asrs r0, rX, #16` of a hoisted `pos << 16` next to an in-loop
    `lsls; asrs` of the other half: `u16 x = pos; u16 y = pos >> 16;`
    passed as `(s16)x, (s16)y` (`(s16)pos` hoists both).
  - `count = field; count++;` (not `field + 1`) for `mov r8, r0; movs r0,
    #1; add r8, r0` (`sub_0800BF50`).
  - Functions the disassembler cut short: a "function" that ends in
    `bl _08xxxxxx` to local labels far away is the head of a much larger
    one (`sub_0801B210`, `EnemyThread`). Check before starting.
  - A value computed in one register and then shifted or copied into
    another (`subs r0, r0, r1; asrs r3, r0, #12` where `asrs r2, r2, #12`
    would do): the destination variable is assigned more than once, so
    the compiler doesn't tie it to its source. Look for the second use:
    `dx`/`dy` reused for the pushed position and `hit` for the table
    value in `sub_0800B594` (134 lines of register noise went away),
    `dx`/`dy` assigned in both branches at function scope in
    `sub_08049C58`, a flag variable set before a switch that never
    changes it in `StartMessageWindow` (found by the permuter).
  - A table base loaded before the base of the table that gives its
    index: the index is assigned inside the subscript,
    `sine[(index = other[direction]) * 16 + 64]` (`sub_0800B594`).
  - Unused stack (`sub sp` larger than needed, low part never touched):
    an unused local array, declared first (`sub_0800E49C`).
  - `i < gCount` re-read after a search loop but cached during it
    (`adds r6, r3, #0`): no local for the count, the loop test reads the
    global and the compiler hoists it (`sub_08027940`). Inline helpers
    for such a search show up as `mov ip, sp` / a copied result; here
    there were none.
  - A parameter reused for an unrelated value (`column` for the roll in
    `sub_080130F4`) puts that value in the parameter's register.
  - `if ((a && x < N) || (!a && x >= N)) { body }` rather than two
    `continue`s for `ble body; b next` in both arms (`sub_08049508`).
  - Two identical `return FALSE` blocks that the original keeps apart
    (`movs r0, #0; b end` twice): one of them comes from a `static
    inline` (`SetSlot` in `AddItemToInventory`). Worth trying on the
    "identical tails not merged" near misses (`DropItem`,
    `GetDataRecord`, `sub_08048240`).
  - A bitfield whose store reads a halfword and a following byte, and
    writes both back: a packed struct with a field crossing the halfword
    (`u32 unk0:4; u32 flags:20;` at gPlayerStats +0x272, `sub_0801CC68`).
    The field's width shows in the store: no mask on the last byte means
    the field takes all of it.
  - decomp-permuter's score isn't always 0 for a matching function here:
    the score 10 candidate of `sub_08029688` matched in the real tree
    (the reason wasn't looked into; `sub_080298C0` at 10 is really 2
    lines off). Build the best candidate before deciding.
- Shapes from 2026-10-14:
  - `adds rD, off, base` (offset first) where `&p[i]` gives `adds rD,
    base, off`: integer address math, `(T *)(i * sizeof(T) + (u32)p)`
    (`sub_08040120`), or offsets kept as `u32` (`anims = (u32)rec +
    rec->anims; entry = (T *)(i * 12 + anims)`, draft of `sub_08002F48`).
  - `(x & 1) << 6` built as `movs r1, #1; ands r0, r1` with the 1 reused
    later: `(x % 2) << 6` (`sub_08047570`).
  - One `movs rX, #0` before both arms of an `if/else` that each set the
    same variable: a `? :` in each arm (`x = a > 1 ? 0x78 : 0;`).
  - A function from another file that returns `bool32` but is followed by
    `lsls r0, #24` in the caller: declare it `u8` in the caller's file.
  - An `if (a) ... else ...` order of `adds` that `x + (c + K)` can't give
    (the compiler reassociates the constant): the function's own
    `(level + 1)` written inline in the product rather than in a local
    (`sub_0802DA2C`), or a temporary.
  - Variable-length arrays (`u8 lit[state->count];`) are what the
    `r7` frame pointer and `mov sp, rX` adjustments mean (`src/area_markers.c`).
    decomp-permuter handles them; it found the last piece there (an `s16`
    temporary declared between the two arrays).
  - decomp-permuter: `tmp/perm.sh FUNC asm_module draft.c SECONDS JOBS`
    (scratch script; kills its workers at the time limit). It needs the
    function alone in its asm module or at least no jump table after it,
    else the base score is in the thousands and it finds nothing.
- Shapes from 2026-10-14, second batch:
  - A `void`-looking function that never uses r0 as scratch (everything
    in r1-r3, r0 untouched after the prologue): declare it `u32` with no
    `return` (`sub_0800588C`, 330 diff lines to 0 with that alone).
  - A loop helper written as a macro with its own block-local loop
    variables (`ADD_ABILITIES` in src/item_flags.c), and a block-local
    record pointer per case.
  - A `switch` whose cases are one-statement bodies tested one by one
    (`cmp #3; beq; bgt; cmp #2`): give each case its own copy of the body
    (src/item_price.c).
  - `cmp; beq; movs #1` is `if (v) v = 1;`, not `v = v ? 1 : 0`.
  - Case order in the source sets the order of the bodies; of several
    identical bodies the last one is kept (CanEquipItem draft,
    `sub_08047570`).
  - Bogus function starts: a "function" with a `pop` but no `push`, or
    that reads the stack before setting up a frame, is a label inside
    another function; turn it into a local label (`5857b9d`, `b6c6152`).
  - `tmp/dcheck.sh FUNC module draft.c [-v [N]]` compiles a draft alone and
    diffs it against the asm (branch targets and pc loads normalized), no
    tree build needed; good for quick variant sweeps.
- Shapes from 2026-10-14, third batch:
  - A "found" tail placed before the search loop (right after the early
    `bne; b fail`): an assignment in the early-exit branch, `if (bad) {
    field = gFieldItems; goto fail; }` (decomp-permuter; src/drop_spot.c).
  - Base loaded before the index (`ldr r4, [base]` first): `p = gTable;
    p[n].x = 0;` instead of `gTable[n].x = 0`.
  - `abs(a)` and `abs(b)` both computed before the `<= 7` tests: locals
    `dx = abs(..); dy = abs(..); if (dx <= 7 && dy <= 7)`.
  - A table read twice at one index keeps its base in a register (and
    adds +2 to the base) as a 2D array `t[n][1]`, `t[n][0]`; struct
    fields `t[n].b`, `t[n].a` CSE `&t[n]` instead (SpawnEnemy).
  - Every ROM address loaded from the literal pool on its own (no base +
    offset): separate symbols, not one array (src/start_equipment.c).
  - Stack space nothing uses: an unused local array (`u8 unused[12]`);
    `&cnt` hoisted before a loop: the `cnt` union declared inside the
    block that uses it (src/field_session.c).
  - A 1-bit field tested as `lsls #29; cmp #0; bge`: the bitfield's
    container is `u32` (a `u8` container gives `movs #4; ands`).
  - PlayerStats fields at large offsets (`ldr base; movs #off;
    adds`) need direct member access; a cast pointer to the field folds
    `sym+off` into one literal.
  - A call that copies a whole struct to the stack (`memcpy` of size - 16,
    then r0-r3 from the first 16 bytes): the callee was declared taking
    the struct by value in that file (src/player_setup.c).
  - A `for` whose step does two things in the original order:
    `for (i = 0; i < 60; i++, angle += 2)`.
  - A `u16` local for a call result moves its `u8` conversion to the
    argument setup (src/enemy_projectile.c).
  - Accepted fakes from decomp-permuter when nothing natural was found:
    see docs/FAKES.md.
- Shapes from 2026-10-15:
  - A `switch` over a `u8`/`u16` gives signed compares (`cmp #1; bgt;
    cmp #0; blt`) without any cast; an added `(s8)`/`(s16)` cast puts in
    a sign extension. A plain `if (x <= 1 && x >= 0)` on a `u16` drops
    the `>= 0` test (src/name_entry_move.c).
  - The out-of-range branch of a jump table going to the function end:
    `case 0: default: return;` (src/item_icon draft).
  - A retry loop with the success path first and the retry jump at the
    end: a label and `goto retry` (src/link_save_reset.c).
  - A 4-byte size difference with otherwise equal listings is an extra
    literal pool word: look for the first `ldr rX, [pc, #N]` whose offset
    differs.
  - A decompress-and-store with the destination's address loaded before
    the call: `void **p = &gPtr; *p = f();` in a block, for each global
    (src/save_select_bg.c).
  - decomp-permuter runs leave their results in `tmp/permute/<func>/
    output-<score>-N/source.c`; `tmp/perm.sh` now times out each compile
    (an agbcc process once hung for a day on a bad candidate).
- Shapes from 2026-10-17:
  - The area 0 characters (src/npc_gift*.c, module asm/code_0801E014.s
    and asm/code_08020604.s) are one family: the same message/item state
    machine with different spot offsets, items, messages and draw cases.
    Start a new one from the closest matched file and diff the
    instruction streams (`diff` of the asm with labels normalized).
  - The case order of a `switch` sets the body order; a case whose body
    is a `return` placed last in the original goes last in the source.
  - A register copy of a byte value right before two calls that take it
    (`adds r5, r6, #0`): the variable is a `u32` holding the `u8` result
    (`priority = (u8)f();`), so passing it to a `u8` parameter is a move
    (src/npc_gift_0604.c, npc_gift_f9c8.c).
  - `ldrsh` of an `s16` field before `lsls #19; asrs #16`: `(s16)(p->x *
    8)`; `(s16)(p->x << 3)` lets the compiler use `ldrh`
    (src/npc_gift_f160.c).
  - decomp-permuter scores count `bl` offsets: an output of score 5-10 can
    already match. Copy it to src/ and run `fcheck.py` before dismissing
    it (sub_0801F9C8 matched at score 5).
  - Still open, seen in `sub_08004AE4` and the spell threads: the original
    sign-extends an `s16` before an add whose result is truncated to 16
    bits again (`lsls; asrs; adds; lsls; lsrs`); every C form tried drops
    the extension (`old_agbcc` too).
- Shapes from 2026-10-18 (the OAM family, src/oam_*.c):
  - A sign extension done in place (`lsls r3, r0, #23; asrs r3, r3, #23`,
    one register for both shifts): two statements on the variable,
    `x = field << 23; x >>= 23;` (the 9-bit OAM x as an unsigned
    bitfield). A signed bitfield or a single `(s32)(v << 23) >> 23`
    expression puts the first shift in another register.
  - A narrowed `u16` parameter copied to a second register at entry
    (`lsrs r2, r2, #16; adds r5, r2, #0`): the parameter is compared in a
    separate `if` from an earlier test. `if (a > N || p->n < anim)` makes
    one pseudo; `if (a > N) return; if (p->n < anim) return;` gives the copy.
  - A pointer copied to a new register just before the loop (`adds r6,
    r2, #0` above the loop label): the loop indexes it (`src =
    &oams[i]`) and strength reduction made the copy; a `src++` pointer
    doesn't.
  - A 1-bit field stored with a doubled `ands` (`movs r3, #1; ands r0,
    r3; ands r0, r3`): `(m / 4) % 2`; `(m >> 2) & 1` gives one `ands`.
  - `list + frame * 4` keeping the list in the destination register:
    `list += frame * 4;` as its own statement.
  - The same `do { ... } while (0)` around the copy-and-position code
    fixed the dest/position register swap in three of these functions
    (probably a macro).
  - The affine ones (`sub_08003724`, `sub_080039C8`, `sub_08003CF8`)
    took `src = oams; for (...; i++, dest++, src++) { obj = src; ... }`
    with `obj` used in the body: that gives the `adds r6, r2, #0` copy
    above the loop label where `&oams[i]` didn't. The `do/while (0)` is
    needed in two of them and has to go in `sub_080039C8`: try both
    whenever dest and the y position swap registers.
  - A matrix number read with `ldrb [obj, #3]` and shifts: the
    `SpriteOam` u16 bitfields (`matrixLo:3, matrix2:1, matrix3:1`); a
    byte-struct pointer at +3 added a register.
  - A call whose result is the last argument of another call, made
    before the other arguments are loaded (`bl f; lsls r0, #24; lsrs r3,
    r0, #24; ldrsh r2, ...`): the result goes in a local first (`color =
    f(a, b); g(x, y, value, color);`). Written inline, the compiler loads
    `value` first and keeps it in a callee-saved register across the call
    (src/menu_stats_diff.c).
  - A two-byte out-parameter read back as `ldrb [rX]` for the first
    byte but `add rY, sp, #N; ldrb [rY, #1]` for the second: a local
    `struct { u8 x; u8 y; } pos;`, not `u8 pos[2]` (src/menu_cursor_draw.c,
    92 -> 11 lines).
  - A switch that the original compiles to a jump table starting at 0
    where the C only has the higher cases: list the low cases explicitly
    (`case 0: ... case 5: break;`).
  - A zero argument passed from a register that held an earlier call's
    result (`str r4, [sp]` after `if ((b = f()) != 0) ... else`): reuse
    that result variable as the argument; and give each unrelated result
    its own local, since one shared `r` stretches its live range and moves
    registers everywhere.
  - `a - (b - 0x40)` kept unfolded (`subs r0, #64; subs r2, r2, r0`) with
    `a` computed first: `y = a; off = b - 0x40; f(y - off)`.
  - Repeated inlined helpers: a function built from already-matched
    helpers (queue pushes, the pop) matched with each written as a
    `static inline` copy, plus one more inline for a duplicated wait loop
    (src/queue_thread.c).
  - A table pick that branches to a shared `ldrb`/`ldr` tail (with a
    literal pool after the first arm's `b`): `size = A[i]; tile += size;`
    written out in each arm, merged by cross-jumping. `table = c ? A :
    B; size = table[i];` loads A before the test instead.
- Shapes from 2026-10-18, second batch (player attack, src/player_attack_damage.c):
  - `y + (off + 0x22)` with the constant kept on the offset (the compiler
    reassociates it onto y): an assignment inside the argument,
    `y + (t = off + 0x22)` (src/save_select_chars.c). A temporary set in
    its own statement moves the computation earlier.
  - `switch (f())` compiled as `subs r0, #1; cmp r0, #1; bls`: the source
    switched on `f() - 1` (cases 0, 1, 2); with a `u32` result the range
    test is unsigned.
  - A call result kept un-narrowed and sign-extended at its use
    (`lsls; asrs` after a `bl` of an `s16` function, no `lsrs` first):
    declare the callee `int` in this file and use `(s16)v`.
  - A value sign-extended for one call and zero-extended for the return
    from the same `x << 16` register: `t = v << 16; f(t >> 16); return
    (u32)t >> 16;` (nothing more natural found).
  - A `u16` local that the compiler keeps writing back to its home
    register (`ands r5, r0; mov r8, r5`): try `s16`.
  - `index * size + list` with the offset first again
    (src/enemy_hit.c), and a copy-loop `memcpy` placed out of line:
    `if (...) goto found;` after the loop.
- Shapes from 2026-10-19 (src/area_exit_thread.c, UseItem draft):
  - The same position read twice from `p + 0x8C` (base kept, then
    `[rX]`, `[rX, #2]`) where `p->x`/`p->y` fold each offset: a pointer to
    the nested struct, in a macro block (`struct AreaPos *pos =
    &spot->pos;`) or assigned inside the first use (`abs(x - (pos =
    &spot->pos)->x)`). Identical blocks in two loops are a macro.
  - A literal loaded early for an index computation: write the indexed
    access inline (`gPlayers[GetMultiplayerId()].layer = ...`) instead of a
    pointer local.
  - A switch where each case tests a global and the default paths each load
    its address before a shared increment (`ldr r2, =gPlayerStats; b inc`):
    plain `gPlayerStats.field` accesses and GCSE doing the rest; no pointer
    variable.
  - `tmp/ndiff.sh FUNC module draft.c` counts dcheck differences with the
    registers normalized: a better guide for structure than raw lines.
- Shapes from 2026-10-19, second batch (src/menu_drop_item.c, 1480 bytes,
  matched from scratch in about ten variants):
  - `ble ok; b fail` where the draft gives `ble skip; b fail; skip: b ok`
    (a far `bgt fail` rewritten by final): the test was inverted in the
    source, `if (x <= cap) break; goto fail;`. Same for `cmp; beq L; b
    done; L: b fail`: `if (count != 0) goto done; goto fail;`.
  - An error block placed after the success path: `if (!(a) && !(b)) {
    ...; goto done; } PlaySE(0x61); return 1;`.
  - A global's address *not* hoisted out of a small loop while the others
    are: index the global directly each time (`gTable[i] == ...;
    gTable[i] = ...`), not through a `p = &gTable[i]` pointer local.
  - A swap that stores the held item first: `raw = *a; *a = *b; *b = raw;`
    with no temporary for `*b` (it reuses the load from the category
    test).
  - `sub sp, #0x20` with only `[sp, #0x1c]` used (a spilled flag): an
    unused `u8 unused[28]` declared first.
  - A `u32 id = item->id;` temporary before `result = 7; if (id != 6)
    result = 6;` puts the `movs #7` after the id extraction.
- Shapes from 2026-10-20 (src/draw_sorted.c, EnemySpawnerThread draft):
  - A list walk entered by a jump to its test, with the step (`p =
    p->next`) placed *above* the test: `p = head; goto check; for (;;) {
    p = p->next; check: if (p != NULL) { body } else break; }`. A plain
    `for`/`while` moves the test to the bottom; a goto-only loop loses
    the loop notes (registers change). The `else break` keeps
    expand_end_loop from moving the test, since the first exit jump comes
    after the body.
  - A block that the original places before the loop it exits from
    (`insert at head` in a search): `if (0) { label: ...; return x; }`
    ahead of the loop and a `goto label` inside.
  - One register for several unrelated values (spawn kind, then the
    trigger; the next-index and the inner counter): reuse one variable in
    the source; separate variables get separate registers.
  - A position read as `[rX]` and `[rX, #2]` from one pointer taken in the
    first use: `*(px = &spot->pos.x)` and `px[1]`.
- Shapes from 2026-10-20, second batch (src/menu_help_line.c, 54 -> 0
  normalized by layout alone):
  - "Identical tails not merged" (`bl f; adds r4, r0; b draw` kept twice):
    the compiler merges a tail into an *identical* one that jumps to the
    same label. The original wrote the shared code (a macro) out in some
    branches (`record += 10; DRAW_CENTERED(...); return;`) and used
    `goto draw` in others; which branches get the copy decides which tails
    survive. Try the macro inline in each branch whose tail the original keeps.
  - A shared call placed after an if-chain (`if (a) r = f(1); else if (b)
    r = f(2); ... else goto other; g(); draw:`) where each arm had `g()`.
  - A block placed after the function's main exit in the original (here
    the item drawing after the help-line draw): move it behind a label at
    the end and `goto` it from its `else`.
  - Case bodies come in source order: read it from the code addresses,
    not the jump table order (case 7 before case 5 here).
  - A `b` from an unrelated branch straight to a case label's literal load
    (`ldr r0, =X` included): a `goto` into that case.
- Shapes from 2026-10-20, third batch (sub_08012AD0 draft, the drop roll):
  - Bitfield stores with *word* access (`ldr r0, [sp]; ands; orrs; str`,
    the value computed first, the next field's mask derived as `subs r2,
    #0x78` from the previous constant): the variable is a `union { u32
    raw; struct Item item; }` (a plain struct gives halfword/byte RMWs).
  - `lsls r1, r0, #16; movs 0xFF << 16; ands; lsrs #16` after a call: a
    `u16` assigned first, masked in a second statement (`roll =
    abs(Random()); roll &= 0xFF;`); written as one expression the mask
    folds away the narrowing. Same for `x % 101 + 100` added in the
    shifted domain (`p = x % 101; p += 100;`).
  - Don't mask a value stored into a bitfield (`item.id = list[i]`, not
    `list[i] & 0x7F`): the store masks it anyway, and the explicit mask
    changes which constant gets hoisted (24 -> 11 lines here).
  - `x ? a == 0 : a != 0` as a `do/while` condition for a retry loop
    whose two exit tests sit at the loop top and bottom.
- Shapes from 2026-10-21 (src/can_equip.c, 63 -> 0 lines):
  - A record pointer that stays in r0 within one case (no copy to a
    callee-saved register) while another case keeps one: a block-local
    pointer in that case (`{ u8 *armor = GetDataRecord(...); ... }`),
    not the function-wide `record`.
  - `adds r0, #0xF1` from the base where the build derives it from the
    previous address (`subs r0, #7`): compare the second field directly
    (`if (rec[0xF1] > x)`) instead of through a local.
  - A final `bne; movs r0, #0` / `movs r0, #1` order: `if (!cond) return
    FALSE; return TRUE;`.
- A switch compare tree with one test per case although several cases
  do nothing (`cmp #1; beq J; cmp #1; ble J; cmp #2; beq J; cmp #3`):
  the cases had different bodies at expand time that later vanished,
  e.g. a mapping with self-assignments (`case 1: kind = 1; break;`).
  Empty cases with the same target are merged into ranges instead
  (sub_08026D98 draft).
- Shapes from 2026-10-21, second batch (src/number_draw.c,
  src/number_above.c; a function and its inlined copy, solved together):
  - A global object's base loaded once before a loop with `adds r0, rB,
    #0x1C` per call (instead of one `sym+0x1C` literal): the field is
    read inside a `static inline` that takes the object pointer
    (`DrawAnim(&gObj, ...)`); the hoisted invariant is the base.
  - Increment order at a loop's end follows the `for` step: `adds i; adds
    p` is `for (...; i++, p++)`, `*p++ = ...` puts p first.
  - An inline whose `kind` argument is a constant but whose code still
    does `lsls #16` (hoisted) / `lsrs #16` per call: the inline's
    parameter is `u32` and narrowed at the call to a `u16` parameter.
- From sub_08023330 (src/item_name.c, 77 -> 0 normalized with the
  permuter's hint): one variable for unrelated small values (`j` as the
  name start and the digit), a separate saved index for the first digit
  (`at = i; ... i++; buf[at] = ...`), `buf[i] = x; k++; i++;` in that
  order, a loop-invariant `item->id + 1` written in the loop test (the
  compiler hoists it after the loop setup), and table pointers walked
  with `for (...; k++, table++)`.
- Families: many functions are copies with different constants. Check
  for one before starting (same mnemonic sequence, or the same first 30
  instructions); solve one, then generate the rest. Done so far: the nine
  save select mode setups (`src/save_select_mode*_setup.c`), the effect
  threads (`src/effect_obj.c`, `effect_anim.c`, `effect_number.c`), the
  queue pushes, the palette fades (`src/palette_fade_*.c`). Open: the
  `ItemUseEffectThread` copies (`sub_0802C3D4`, `sub_0802C798`).
- Return layout: `if (ok) { ... } else { return FALSE; }` in each branch
  and one `return TRUE` at the end puts the shared failure block right
  before the final `movs r0, #1` (`sub_0803FC00`). A table that the code
  reloads after a call isn't `const`.
- decomp-permuter (`tools/decomp-permuter`, driven like
  `tools/autodecomp/autodecomp.py:permute`) rarely finishes a function, but
  its best candidates point at the idea (a reused variable, a volatile
  read). Its compile script must delete the `.s` it writes next to the
  output: otherwise /tmp fills with millions of files (happened 2026-10-10).
- `split_asm.py FILE Func -` takes everything from Func to the end of the
  file. Only use `-` after checking Func is the last `func_start`.
- Before replacing an asm module with C, check it holds only the functions
  you wrote (`grep func_start`), and look for `.byte` runs after literal
  pools: those are uncalled functions and need C too.
- Names: `tools/scripts/rename.py old new` (records in config/names.txt).
  RAM globals: `config/ram_symbols.txt`; ROM tables and link-time constants:
  `config/rom_symbols.txt`. Then run `tools/scripts/apply_syms.py` (regenerates
  `ld_symbols.ld`).
- After a batch: `make progress RECORD=1`.
- Helpers: `tools/scripts/simple_runs.py` (runs of small adjacent functions
  to decompile next), `tools/scripts/dumpfuncs.py FIRST END` (print their
  asm), `tools/scripts/fcheck.py FUNC...` (build + per-function match,
  ignoring bl offsets). Typical loop: split_asm → write C → fcheck → fix
  shapes → `make compare` → retire asm to tmp/ → commit.
- When one function won't match after a few tries, split it back out as
  its own asm module (split_asm on the module file), keep the draft in
  tmp/drafts/, list it in docs/NEXT.md, and move on.
- The user can run mGBA with the GDB server; with it running you can read
  RAM directly (tools/research/gdbstub.py, reads of <= 0x80 bytes) instead
  of asking them for values.
- Retired asm goes to `tmp/` (gitignored scratch) when its C matches.
- Reference sources: `tmp/pokeemerald` (m4a, agb_flash), `tmp/sigmatch.txt`
  (which library functions match pokeemerald byte-for-byte).

## Toolchain

agbcc (`agbcc -fprologue-bugfix` for the game, `old_agbcc` for m4a) via `tools/setup.sh`; the
preprocessor is `arm-none-eabi-cpp` with `-nostdinc`, which defaults to C23,
so avoid `__STDC_VERSION__` checks that pick C23-only syntax.

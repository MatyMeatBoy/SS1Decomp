# Shining Soul (USA) decompilation
# Requires baserom.gba (your own dump, SHA1 in shiningsoul.sha1) in this directory.

PREFIX  ?= arm-none-eabi-
AS      := $(PREFIX)as
LD      := $(PREFIX)ld
OBJCOPY := $(PREFIX)objcopy
CC1     := tools/agbcc/bin/agbcc
CPP     := $(PREFIX)cpp

ASFLAGS  := -mcpu=arm7tdmi -I include
CC1FLAGS := -mthumb-interwork -Wimplicit -Wparentheses -O2 -fhex-asm -fprologue-bugfix
CPPFLAGS := -nostdinc -I include -I tools/agbcc/include -iquote include

ROM     := shiningsoul.gba
ELF     := $(ROM:.gba=.elf)
MAP     := $(ROM:.gba=.map)
BASEROM := baserom.gba

# ld_script.ld decides what gets linked (and in what order): each object is
# either asm/<x>.o (not decompiled yet) or src/<x>.o (decompiled C).
OBJS    := $(shell grep -oE '[A-Za-z0-9_/]+\.o' ld_script.ld)
S_SRCS  := $(wildcard asm/*.s asm/lib/*.s) data/data.s
C_SRCS  := $(wildcard src/*.c src/lib/*.c)

.PHONY: all compare clean check_baserom progress diff check
.SECONDARY:

all: $(ROM)

compare: $(ROM)
	@sha1sum -c shiningsoul.sha1

# How far along the decomp is, and whether the ROM still matches.
# RECORD=1 also appends to progress.csv to track the trend.
progress: $(ROM)
	@python3 tools/scripts/progress.py $(if $(RECORD),--record)

# Which functions differ from the original (after a change broke matching).
diff: $(ROM)
	@python3 tools/scripts/romdiff.py

# Instruction-level diff of one function: make check FUNC=QueueCopy
check: $(ROM)
	@python3 tools/scripts/checkfunc.py $(FUNC)

check_baserom:
	@test -f $(BASEROM) || { echo "error: $(BASEROM) not found. Dump your cartridge and place it here (see README.md)."; exit 1; }
	@sha1sum -c baserom.sha1 >/dev/null 2>&1 || { echo "error: $(BASEROM) does not match the expected SHA1 (see README.md)."; exit 1; }

# Objects that .incbin from the baserom depend on it.
asm/crt0.o data/data.o: $(BASEROM) | check_baserom
$(S_SRCS:.s=.o): asm/macros.inc
$(C_SRCS:.c=.o): $(wildcard include/*.h include/*/*.h)

# The Nintendo m4a sound library was built with an older agbcc.
src/lib/m4a.o: CC1 := tools/agbcc/bin/old_agbcc
src/lib/m4a.o: CC1FLAGS := -mthumb-interwork -Wimplicit -Wparentheses -O2 -fhex-asm

%.o: %.s
	$(AS) $(ASFLAGS) -o $@ $<

src/%.o: src/%.c
	$(CPP) $(CPPFLAGS) $< | $(CC1) $(CC1FLAGS) -o src/$*.s
	printf '\t.text\n\t.align 2, 0\n' >> src/$*.s
	$(AS) $(ASFLAGS) -o $@ src/$*.s

$(ELF): $(OBJS) ld_script.ld ld_symbols.ld
	$(LD) -T ld_script.ld -Map $(MAP) -o $@ $(OBJS)

$(ROM): $(ELF)
	$(OBJCOPY) -O binary $< $@

clean:
	rm -f $(ROM) $(ELF) $(MAP) $(S_SRCS:.s=.o) $(C_SRCS:.c=.o) $(C_SRCS:.c=.s)

# ROM-free source inventory. These isolated objects never enter the game build.
JOBS ?= 4
.PHONY: metadata progress-map test-progress
metadata:
	python3 tools/scripts/metadata_build.py --jobs $(JOBS)

progress-map: metadata
	python3 tools/scripts/progress_visuals.py --metadata-dir build/metadata --out docs/progress

test-progress:
	python3 -m unittest discover -s tests -v

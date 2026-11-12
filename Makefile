# Shining Soul regional decompilation. Europe is the primary profile.
REGION ?= eu
ifneq ($(REGION),eu)
ifneq ($(REGION),us)
$(error Unsupported REGION '$(REGION)'; use eu or us)
endif
endif
.DEFAULT_GOAL := all

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

ifeq ($(REGION),us)
all: $(ROM)
compare: $(ROM)
	@sha1sum -c shiningsoul.sha1
progress: $(ROM)
	@python3 tools/scripts/progress.py $(if $(RECORD),--record)
else
all: compare-eu
compare: compare-eu
progress: compare-eu
endif

.PHONY: compare-us progress-us
compare-us:
	$(MAKE) REGION=us compare
progress-us:
	$(MAKE) REGION=us progress $(if $(RECORD),RECORD=$(RECORD))

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

progress-map:
	python3 tools/scripts/update_progress.py

test-progress:
	python3 -m unittest discover -s tests -v

# European multilingual build: only proven C modules replace raw pending spans.
EU_ROM ?= baserom_eu.gba
.PHONY: compare-eu record-eu
compare-eu: metadata
	python3 tools/scripts/eu_module_match.py --metadata-dir build/metadata --rom "$(EU_ROM)" --out build/eu-candidates.json
	python3 tools/scripts/eu_build.py --metadata-dir build/metadata --rom "$(EU_ROM)" --candidates build/eu-candidates.json
	python3 tools/scripts/region_progress.py --report build/eu/report.json --out docs/progress

# Record only the successful verification metadata, never the ROM or objects.
record-eu: compare-eu
	python3 -c "from pathlib import Path; import shutil; Path('config/regions').mkdir(exist_ok=True); shutil.copyfile('build/eu/report.json', 'config/regions/eu_verified.json')"

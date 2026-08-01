/*
 * Headless libmGBA execution backend for gba-playtest.
 *
 * The core setup and frame-driving shape are adapted from
 * scripts/shiftcheck/mgba_oracle.c in this repository. That oracle remains
 * unchanged; this backend adds a declarative plan and RAM probes.
 */
#include <mgba/core/core.h>
#include <mgba/core/interface.h>
#include <mgba/core/log.h>

#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if BYTES_PER_PIXEL != 4
#error "gba-playtest requires libmGBA's standard 32-bit color_t build"
#endif

#define GBA_SRAM_BASE 0x0E000000u
#define GBA_SRAM_SIZE 0x8000u

struct InputRange {
	uint32_t start;
	uint32_t end;
	uint32_t keys;
};

struct Probe {
	uint32_t address;
	unsigned size;
};

/* A [offset, offset+length) byte range within the 0x8000-byte SRAM image
 * excluded from a checkpoint's SRAM hash (see hash_sram()). */
struct ByteRange {
	uint32_t offset;
	uint32_t length;
};

/* A rectangular [x, x+width) x [y, y+height) sub-region of the 240x160
 * framebuffer, hashed on its own (see hash_region()) so a checkpoint can
 * prove a *specific screen area* changed/differs -- e.g. a locale-specific
 * visible decoration marker -- without that proof being diluted by (or
 * mistaken for) a whole-screen hash difference that could come from any
 * unrelated pixel anywhere on screen. */
struct Region {
	uint32_t x;
	uint32_t y;
	uint32_t width;
	uint32_t height;
};

/* A single (x, y) framebuffer coordinate whose canonical R,G,B byte triple
 * (same extraction as hash_framebuffer()/hash_region(), host-endianness-
 * and alpha/padding-independent) is read back directly -- the finest-
 * grained possible real visible-pixel assertion, one exact on-screen
 * color value at a time. */
struct PixelProbe {
	uint32_t x;
	uint32_t y;
};

struct Checkpoint {
	uint32_t frame;
	size_t probe_count;
	struct Probe* probes;
	bool sram_hash;
	size_t exclude_range_count;
	struct ByteRange* exclude_ranges;
	size_t region_count;
	struct Region* regions;
	size_t pixel_probe_count;
	struct PixelProbe* pixel_probes;
};

struct Plan {
	size_t range_count;
	struct InputRange* ranges;
	size_t checkpoint_count;
	struct Checkpoint* checkpoints;
};

static void silent_log(struct mLogger* logger, int category,
                       enum mLogLevel level, const char* format, va_list args)
{
	(void) logger;
	(void) category;
	(void) level;
	(void) format;
	(void) args;
}

static void free_plan(struct Plan* plan)
{
	if (plan->checkpoints) {
		for (size_t i = 0; i < plan->checkpoint_count; ++i) {
			free(plan->checkpoints[i].probes);
			free(plan->checkpoints[i].exclude_ranges);
			free(plan->checkpoints[i].regions);
			free(plan->checkpoints[i].pixel_probes);
		}
	}
	free(plan->checkpoints);
	free(plan->ranges);
	memset(plan, 0, sizeof(*plan));
}

static bool read_plan(const char* path, struct Plan* plan)
{
	FILE* file = fopen(path, "r");
	if (!file) {
		fprintf(stderr, "cannot open plan: %s\n", path);
		return false;
	}
	char word[32];
	unsigned version;
	if (fscanf(file, "%31s %u", word, &version) != 2 ||
	    strcmp(word, "GBA_PLAYTEST_PLAN") != 0 || version != 3) {
		fprintf(stderr, "malformed plan header\n");
		goto fail;
	}
	if (fscanf(file, "%31s %zu", word, &plan->range_count) != 2 ||
	    strcmp(word, "RANGES") != 0 || plan->range_count > 10000) {
		fprintf(stderr, "malformed RANGES record\n");
		goto fail;
	}
	plan->ranges = calloc(plan->range_count, sizeof(*plan->ranges));
	if (plan->range_count && !plan->ranges) {
		fprintf(stderr, "out of memory reading ranges\n");
		goto fail;
	}
	for (size_t i = 0; i < plan->range_count; ++i) {
		struct InputRange* range = &plan->ranges[i];
		if (fscanf(file, "%" SCNu32 " %" SCNu32 " %" SCNu32,
		           &range->start, &range->end, &range->keys) != 3) {
			fprintf(stderr, "malformed input range %zu\n", i);
			goto fail;
		}
	}
	if (fscanf(file, "%31s %zu", word, &plan->checkpoint_count) != 2 ||
	    strcmp(word, "CHECKPOINTS") != 0 || plan->checkpoint_count == 0 ||
	    plan->checkpoint_count > 10000) {
		fprintf(stderr, "malformed CHECKPOINTS record\n");
		goto fail;
	}
	plan->checkpoints = calloc(plan->checkpoint_count, sizeof(*plan->checkpoints));
	if (!plan->checkpoints) {
		fprintf(stderr, "out of memory reading checkpoints\n");
		goto fail;
	}
	for (size_t i = 0; i < plan->checkpoint_count; ++i) {
		struct Checkpoint* checkpoint = &plan->checkpoints[i];
		unsigned sram_hash_flag;
		if (fscanf(file, "%" SCNu32 " %zu %u %zu %zu %zu", &checkpoint->frame,
		           &checkpoint->probe_count, &sram_hash_flag,
		           &checkpoint->exclude_range_count, &checkpoint->region_count,
		           &checkpoint->pixel_probe_count) != 6 ||
		    checkpoint->probe_count > 1024 ||
		    checkpoint->exclude_range_count > 64 ||
		    checkpoint->region_count > 64 ||
		    checkpoint->pixel_probe_count > 256 ||
		    (sram_hash_flag != 0 && sram_hash_flag != 1)) {
			fprintf(stderr, "malformed checkpoint %zu\n", i);
			goto fail;
		}
		checkpoint->sram_hash = sram_hash_flag != 0;
		checkpoint->exclude_ranges = calloc(checkpoint->exclude_range_count,
		                                     sizeof(*checkpoint->exclude_ranges));
		if (checkpoint->exclude_range_count && !checkpoint->exclude_ranges) {
			fprintf(stderr, "out of memory reading exclude ranges\n");
			goto fail;
		}
		for (size_t j = 0; j < checkpoint->exclude_range_count; ++j) {
			struct ByteRange* range = &checkpoint->exclude_ranges[j];
			if (fscanf(file, "%" SCNu32 " %" SCNu32, &range->offset,
			           &range->length) != 2 ||
			    range->length == 0 ||
			    range->offset >= GBA_SRAM_SIZE ||
			    range->length > GBA_SRAM_SIZE - range->offset) {
				fprintf(stderr, "malformed exclude range %zu at checkpoint %zu\n", j, i);
				goto fail;
			}
		}
		checkpoint->probes = calloc(checkpoint->probe_count,
		                            sizeof(*checkpoint->probes));
		if (checkpoint->probe_count && !checkpoint->probes) {
			fprintf(stderr, "out of memory reading probes\n");
			goto fail;
		}
		for (size_t j = 0; j < checkpoint->probe_count; ++j) {
			struct Probe* probe = &checkpoint->probes[j];
			if (fscanf(file, "%" SCNu32 " %u", &probe->address,
			           &probe->size) != 2 ||
			    (probe->size != 1 && probe->size != 2 && probe->size != 4)) {
				fprintf(stderr, "malformed probe %zu at checkpoint %zu\n", j, i);
				goto fail;
			}
		}
		checkpoint->regions = calloc(checkpoint->region_count,
		                             sizeof(*checkpoint->regions));
		if (checkpoint->region_count && !checkpoint->regions) {
			fprintf(stderr, "out of memory reading regions\n");
			goto fail;
		}
		for (size_t j = 0; j < checkpoint->region_count; ++j) {
			struct Region* region = &checkpoint->regions[j];
			if (fscanf(file, "%" SCNu32 " %" SCNu32 " %" SCNu32 " %" SCNu32,
			           &region->x, &region->y, &region->width,
			           &region->height) != 4 ||
			    region->width == 0 || region->height == 0 ||
			    region->x >= 240 || region->y >= 160 ||
			    region->width > 240 - region->x ||
			    region->height > 160 - region->y) {
				fprintf(stderr, "malformed region %zu at checkpoint %zu\n", j, i);
				goto fail;
			}
		}
		checkpoint->pixel_probes = calloc(checkpoint->pixel_probe_count,
		                                  sizeof(*checkpoint->pixel_probes));
		if (checkpoint->pixel_probe_count && !checkpoint->pixel_probes) {
			fprintf(stderr, "out of memory reading pixel probes\n");
			goto fail;
		}
		for (size_t j = 0; j < checkpoint->pixel_probe_count; ++j) {
			struct PixelProbe* pixel = &checkpoint->pixel_probes[j];
			if (fscanf(file, "%" SCNu32 " %" SCNu32, &pixel->x, &pixel->y) != 2 ||
			    pixel->x >= 240 || pixel->y >= 160) {
				fprintf(stderr, "malformed pixel probe %zu at checkpoint %zu\n", j, i);
				goto fail;
			}
		}
	}
	if (fscanf(file, "%31s", word) == 1) {
		fprintf(stderr, "unexpected trailing plan data\n");
		goto fail;
	}
	fclose(file);
	return true;

fail:
	fclose(file);
	free_plan(plan);
	return false;
}

static uint64_t hash_framebuffer(const color_t* buffer, unsigned width, unsigned height)
{
	/* FNV-1a over canonical R,G,B bytes; ignore host endianness and alpha/padding. */
	uint64_t hash = UINT64_C(14695981039346656037);
	for (size_t i = 0; i < (size_t) width * height; ++i) {
		uint32_t pixel = buffer[i];
		for (unsigned shift = 0; shift < 24; shift += 8) {
			hash ^= (pixel >> shift) & 0xFF;
			hash *= UINT64_C(1099511628211);
		}
	}
	return hash;
}

/* Same FNV-1a construction/pixel-byte extraction as hash_framebuffer(),
 * restricted to a single rectangular sub-region -- proves a *specific*
 * screen area changed/differs (e.g. a locale-specific visible decoration
 * marker) independently of every other pixel on screen, unlike a
 * whole-frame hash which cannot distinguish "this exact area changed"
 * from "something, somewhere on screen, changed". Scans row-major within
 * the region only, so is deterministic and stable across builds exactly
 * like hash_framebuffer() itself. */
static uint64_t hash_region(const color_t* buffer, unsigned width,
                            const struct Region* region)
{
	uint64_t hash = UINT64_C(14695981039346656037);
	for (uint32_t row = 0; row < region->height; ++row) {
		const color_t* line = buffer + (size_t) (region->y + row) * width + region->x;
		for (uint32_t col = 0; col < region->width; ++col) {
			uint32_t pixel = line[col];
			for (unsigned shift = 0; shift < 24; shift += 8) {
				hash ^= (pixel >> shift) & 0xFF;
				hash *= UINT64_C(1099511628211);
			}
		}
	}
	return hash;
}

/* Reads back a single pixel's canonical 24-bit color value, re-packed as
 * a conventional 0xRRGGBB integer (R in bits 16-23, G in bits 8-15, B in
 * bits 0-7) so its printed hex text reads in the familiar left-to-right
 * RRGGBB order -- host endianness/alpha/padding-independent, using the
 * exact same per-byte extraction as hash_framebuffer()/hash_region()
 * (shifts 0/8/16 = R/G/B of the source color_t). The finest-grained real
 * visible-pixel proof available: one exact on-screen color at a time. */
static uint32_t read_pixel(const color_t* buffer, unsigned width,
                           const struct PixelProbe* pixel)
{
	uint32_t value = buffer[(size_t) pixel->y * width + pixel->x];
	uint32_t r = value & 0xFFu;
	uint32_t g = (value >> 8) & 0xFFu;
	uint32_t b = (value >> 16) & 0xFFu;
	return (r << 16) | (g << 8) | b;
}

static uint32_t read_probe(struct mCore* core, const struct Probe* probe)
{
	switch (probe->size) {
	case 1:
		return core->busRead8(core, probe->address);
	case 2:
		return core->busRead16(core, probe->address);
	default:
		return core->busRead32(core, probe->address);
	}
}

static bool offset_excluded(const struct ByteRange* ranges, size_t range_count,
                            uint32_t offset)
{
	for (size_t i = 0; i < range_count; ++i) {
		if (offset >= ranges[i].offset && offset < ranges[i].offset + ranges[i].length)
			return true;
	}
	return false;
}

static uint64_t hash_sram(struct mCore* core, const struct ByteRange* exclude_ranges,
                           size_t exclude_range_count)
{
	/* Same FNV-1a construction as hash_framebuffer(), applied to the raw
	 * cart SRAM bus range (0x0E000000..0x0E007FFF): proves the entire
	 * 0x8000-byte image -- minus any `exclude_ranges` bytes -- is
	 * byte-for-byte unchanged across a checkpoint without needing one
	 * probe per byte (the plan format caps probes per checkpoint at
	 * 1024). With no exclude ranges (the common case) this proves the
	 * *entire* image unchanged, exactly as before. `exclude_ranges` exists
	 * only for checkpoints whose SRAM legitimately contains intentionally
	 * build-variable diagnostic bytes (ExpansionSaveMeta's buildCommitShort
	 * and its dependent checksum -- see docs/save_format.md's "SRAM hash
	 * policy: exact vs. normalized"); excluded bytes are skipped entirely
	 * (never substituted/zeroed), so the hash is still sensitive to every
	 * other byte in the image. */
	uint64_t hash = UINT64_C(14695981039346656037);
	for (uint32_t offset = 0; offset < GBA_SRAM_SIZE; ++offset) {
		if (offset_excluded(exclude_ranges, exclude_range_count, offset))
			continue;
		uint8_t byte = core->busRead8(core, GBA_SRAM_BASE + offset);
		hash ^= byte;
		hash *= UINT64_C(1099511628211);
	}
	return hash;
}

static int run(const char* rom_path, const struct Plan* plan, const char* sram_path)
{
	struct mCore* core = mCoreFind(rom_path);
	if (!core) {
		fprintf(stderr, "no mGBA core recognizes ROM: %s\n", rom_path);
		return 2;
	}
	if (!core->init(core)) {
		fprintf(stderr, "mGBA core initialization failed\n");
		core->deinit(core);
		return 2;
	}
	mCoreInitConfig(core, NULL);
	if (!mCoreLoadFile(core, rom_path)) {
		fprintf(stderr, "mGBA could not load ROM: %s\n", rom_path);
		mCoreConfigDeinit(&core->config);
		core->deinit(core);
		return 2;
	}
	if (sram_path) {
		/*
		 * Loaded before core->reset() so the pre-boot SRAM image is what
		 * the game's own boot-time classifier (ClassifySramSaveCompat)
		 * observes on the very first frame, exactly as a real cartridge
		 * with existing save data would present it.
		 *
		 * `temporary=true` is required here: it maps to
		 * GBACoreLoadTemporarySave -> GBASavedataMask(), which copies the
		 * file's bytes into the in-memory savedata buffer once and then
		 * detaches from the backing file. `temporary=false` instead keeps
		 * the opened O_RDWR VFile as the live savedata backing store, so
		 * every in-game SRAM write (including the compatibility menu's
		 * whole-chip erase) is flushed straight back to sram_path on disk
		 * -- silently mutating the input fixture and making repeated runs
		 * against the same file non-reproducible (confirmed empirically:
		 * identical re-invocations diverged once the fixture had been
		 * quietly rewritten by a prior run).
		 */
		if (!mCoreLoadSaveFile(core, sram_path, true)) {
			fprintf(stderr, "mGBA could not load SRAM image: %s\n", sram_path);
			mCoreConfigDeinit(&core->config);
			core->deinit(core);
			return 2;
		}
	}
	unsigned width;
	unsigned height;
	core->desiredVideoDimensions(core, &width, &height);
	if (width != 240 || height != 160) {
		fprintf(stderr, "unexpected GBA framebuffer dimensions: %ux%u\n", width, height);
		mCoreConfigDeinit(&core->config);
		core->deinit(core);
		return 2;
	}
	color_t* buffer = calloc((size_t) width * height, sizeof(*buffer));
	if (!buffer) {
		fprintf(stderr, "out of memory allocating framebuffer\n");
		mCoreConfigDeinit(&core->config);
		core->deinit(core);
		return 2;
	}
	core->setVideoBuffer(core, buffer, width);
	core->reset(core);

	size_t range_index = 0;
	size_t checkpoint_index = 0;
	uint32_t last_frame = plan->checkpoints[plan->checkpoint_count - 1].frame;
	for (uint32_t frame = 0; frame <= last_frame; ++frame) {
		while (range_index < plan->range_count &&
		       plan->ranges[range_index].end < frame)
			++range_index;
		uint32_t keys = 0;
		if (range_index < plan->range_count &&
		    plan->ranges[range_index].start <= frame)
			keys = plan->ranges[range_index].keys;
		core->setKeys(core, keys);
		core->runFrame(core);
		if (checkpoint_index < plan->checkpoint_count &&
		    plan->checkpoints[checkpoint_index].frame == frame) {
			const struct Checkpoint* checkpoint =
			    &plan->checkpoints[checkpoint_index];
			uint64_t hash = hash_framebuffer(buffer, width, height);
			printf("CHECKPOINT\t%zu\t%" PRIu32 "\t%016" PRIx64 "\n",
			       checkpoint_index, frame, hash);
			for (size_t probe_index = 0;
			     probe_index < checkpoint->probe_count; ++probe_index) {
				printf("PROBE\t%zu\t%zu\t%" PRIu32 "\n",
				       checkpoint_index, probe_index,
				       read_probe(core, &checkpoint->probes[probe_index]));
			}
			if (checkpoint->sram_hash) {
				uint64_t sram = hash_sram(core, checkpoint->exclude_ranges,
				                           checkpoint->exclude_range_count);
				printf("SRAMHASH\t%zu\t%016" PRIx64 "\n",
				       checkpoint_index, sram);
			}
			for (size_t region_index = 0;
			     region_index < checkpoint->region_count; ++region_index) {
				uint64_t region_hash = hash_region(
				    buffer, width, &checkpoint->regions[region_index]);
				printf("REGIONHASH\t%zu\t%zu\t%016" PRIx64 "\n",
				       checkpoint_index, region_index, region_hash);
			}
			for (size_t pixel_index = 0;
			     pixel_index < checkpoint->pixel_probe_count; ++pixel_index) {
				uint32_t rgb = read_pixel(
				    buffer, width, &checkpoint->pixel_probes[pixel_index]);
				printf("PIXEL\t%zu\t%zu\t%06" PRIx32 "\n",
				       checkpoint_index, pixel_index, rgb);
			}
			++checkpoint_index;
		}
	}
	free(buffer);
	mCoreConfigDeinit(&core->config);
	core->deinit(core);
	return checkpoint_index == plan->checkpoint_count ? 0 : 2;
}

int main(int argc, char** argv)
{
	if (argc != 3 && argc != 4) {
		fprintf(stderr, "usage: %s <rom.gba> <plan> [sram-image]\n", argv[0]);
		return 2;
	}
	struct mLogger logger = {.log = silent_log, .filter = NULL};
	mLogSetDefaultLogger(&logger);
	struct Plan plan = {0};
	if (!read_plan(argv[2], &plan))
		return 2;
	int result = run(argv[1], &plan, argc == 4 ? argv[3] : NULL);
	free_plan(&plan);
	return result;
}

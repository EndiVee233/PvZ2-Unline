#include <android/log.h>
#include <dlfcn.h>
#include <link.h>
#include <elf.h>
#include <sys/mman.h>
#include <unistd.h>
#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <vector>
#include <atomic>
#include <pthread.h>
#include <sys/stat.h>
#include <time.h>
#ifdef PVZ2_DECODE_DIAGNOSTICS
#include <signal.h>
#include <ucontext.h>
static struct sigaction previous_decode_segv;
static void decode_fault(int signal, siginfo_t *info, void *context) {
    auto &r = static_cast<ucontext_t *>(context)->uc_mcontext;
    __android_log_print(ANDROID_LOG_ERROR, "AsterDecodeFault",
        "signal=%d address=%p PC=%08lx LR=%08lx SP=%08lx CPSR=%08lx "
        "r0=%08lx r1=%08lx r2=%08lx r3=%08lx r4=%08lx r5=%08lx r6=%08lx "
        "r7=%08lx r8=%08lx r9=%08lx r10=%08lx fp=%08lx ip=%08lx",
        signal, info ? info->si_addr : nullptr, r.arm_pc, r.arm_lr, r.arm_sp, r.arm_cpsr,
        r.arm_r0, r.arm_r1, r.arm_r2, r.arm_r3, r.arm_r4, r.arm_r5, r.arm_r6,
        r.arm_r7, r.arm_r8, r.arm_r9, r.arm_r10, r.arm_fp, r.arm_ip);
    if (previous_decode_segv.sa_flags & SA_SIGINFO)
        previous_decode_segv.sa_sigaction(signal, info, context);
    else if (previous_decode_segv.sa_handler != SIG_DFL && previous_decode_segv.sa_handler != SIG_IGN)
        previous_decode_segv.sa_handler(signal);
    else { ::signal(signal, SIG_DFL); raise(signal); }
}
#endif
#include <GLES2/gl2.h>
#include <astc-codec/astc-codec.h>

#define TAG "GLShim"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, TAG, __VA_ARGS__)

#ifndef PVZ2_GL_CACHE_ROOT
#define PVZ2_GL_CACHE_ROOT "/data/data/com.popcap.pvz2cthd/cache"
#endif
#ifndef PVZ2_ASTC_MAX_THREADS
#define PVZ2_ASTC_MAX_THREADS 4
#endif
static_assert(PVZ2_ASTC_MAX_THREADS >= 1 && PVZ2_ASTC_MAX_THREADS <= 16,
              "ASTC worker limit must be between 1 and 16");

typedef void (*PFN_glTexImage2D)(GLenum, GLint, GLint, GLsizei, GLsizei, GLint, GLenum, GLenum, const void *);
typedef void (*PFN_glTexSubImage2D)(GLenum, GLint, GLint, GLint, GLsizei, GLsizei, GLenum, GLenum, const void *);
typedef void (*PFN_glCompressedTexImage2D)(GLenum, GLint, GLenum, GLsizei, GLsizei, GLint, GLsizei, const void *);

static PFN_glTexImage2D real_tex = nullptr;
static PFN_glTexSubImage2D real_sub = nullptr;
static PFN_glCompressedTexImage2D real_ctex = nullptr;
typedef void (*PFN_etc1_decode)(const uint8_t *, uint8_t *, int, int);
static PFN_etc1_decode etc1_decode = nullptr;
static int tex_logs = 0;
static int ctex_logs = 0;

struct ModInfo {
    uintptr_t base = 0;
    const Elf32_Phdr *phdr = nullptr;
    int phnum = 0;
    const char *name = nullptr;
};

static int find_cb(struct dl_phdr_info *info, size_t, void *data) {
    ModInfo *out = (ModInfo *)data;
    if (info->dlpi_name && strstr(info->dlpi_name, out->name)) {
        out->base = (uintptr_t)info->dlpi_addr;
        out->phdr = (const Elf32_Phdr *)info->dlpi_phdr;
        out->phnum = info->dlpi_phnum;
        return 1;
    }
    return 0;
}

static void patch_got(ModInfo &m, const char *symname, void *replacement) {
    const Elf32_Dyn *dyn = nullptr;
    for (int i = 0; i < m.phnum; i++) {
        if (m.phdr[i].p_type == PT_DYNAMIC) {
            dyn = (const Elf32_Dyn *)(m.base + m.phdr[i].p_vaddr);
        }
    }
    if (!dyn) { LOGI("no PT_DYNAMIC"); return; }

    uintptr_t symtab = 0, strtab = 0, jmprel = 0, rel = 0;
    size_t pltrelsz = 0, relsz = 0;
    for (const Elf32_Dyn *d = dyn; d->d_tag != DT_NULL; d++) {
        switch (d->d_tag) {
            case DT_SYMTAB: symtab = d->d_un.d_ptr; break;
            case DT_STRTAB: strtab = d->d_un.d_ptr; break;
            case DT_JMPREL: jmprel = d->d_un.d_ptr; break;
            case DT_PLTRELSZ: pltrelsz = d->d_un.d_val; break;
            case DT_REL: rel = d->d_un.d_ptr; break;
            case DT_RELSZ: relsz = d->d_un.d_val; break;
        }
    }
    if (symtab < m.base) symtab += m.base;
    if (strtab < m.base) strtab += m.base;
    if (jmprel && jmprel < m.base) jmprel += m.base;
    if (rel && rel < m.base) rel += m.base;

    const Elf32_Sym *syms = (const Elf32_Sym *)symtab;
    const char *strs = (const char *)strtab;

    auto process = [&](uintptr_t addr, size_t bytes) {
        if (!addr) return;
        for (size_t off = 0; off + sizeof(Elf32_Rel) <= bytes; off += sizeof(Elf32_Rel)) {
            const Elf32_Rel *r = (const Elf32_Rel *)(addr + off);
            unsigned type = ELF32_R_TYPE(r->r_info);
            unsigned sym = ELF32_R_SYM(r->r_info);
            if (type != R_ARM_JUMP_SLOT && type != R_ARM_GLOB_DAT) continue;
            const char *n = strs + syms[sym].st_name;
            if (strcmp(n, symname) != 0) continue;
            uintptr_t *slot = (uintptr_t *)(m.base + r->r_offset);
            uintptr_t page = (uintptr_t)slot & ~(uintptr_t)(getpagesize() - 1);
            if (mprotect((void *)page, getpagesize(), PROT_READ | PROT_WRITE) != 0) {
                LOGI("mprotect failed for %s", symname);
                continue;
            }
            uintptr_t old = *slot;
            *slot = (uintptr_t)replacement;
            __builtin___clear_cache((char *)slot, (char *)slot + sizeof(*slot));
            mprotect((void *)page, getpagesize(), PROT_READ);
            LOGI("patched %s at %p: %p -> %p", symname, slot, (void *)old, replacement);
        }
    };
    process(jmprel, pltrelsz);
    process(rel, relsz);
}

extern "C" void glTexImage2D(GLenum target, GLint level, GLint internalformat, GLsizei width,
                             GLsizei height, GLint border, GLenum format, GLenum type,
                             const void *pixels) {
    if (tex_logs < 300) {
        tex_logs++;
        if (internalformat == 0x8033 || internalformat == 0x8045 ||
            internalformat == 0x8D64 || internalformat == 0x8D65 ||
            internalformat == 0x8D66 || internalformat == 0x8C00 ||
            tex_logs <= 20) {
            LOGI("glTexImage2D internal=0x%x format=0x%x type=0x%x %dx%d border=%d",
                 internalformat, format, type, width, height, border);
        }
    }
    // GL_UNSIGNED_SHORT_4_4_4_4 (0x8033) used as internalformat: expand to RGBA8888
    if (internalformat == 0x8033 && type == 0x8033 && format == GL_RGBA) {
        if (!pixels) {
            if (real_tex) real_tex(target, level, GL_RGBA, width, height, border, GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
            return;
        }
        if (width > 0 && height > 0) {
            size_t n = (size_t)width * (size_t)height;
            uint8_t *out = (uint8_t *)malloc(n * 4);
            if (out) {
                const uint16_t *src = (const uint16_t *)pixels;
                for (size_t i = 0; i < n; i++) {
                    uint16_t p = src[i];
                    out[i*4+0] = (uint8_t)(((p >> 12) & 0xF) * 17);
                    out[i*4+1] = (uint8_t)(((p >> 8) & 0xF) * 17);
                    out[i*4+2] = (uint8_t)(((p >> 4) & 0xF) * 17);
                    out[i*4+3] = (uint8_t)((p & 0xF) * 17);
                }
                if (real_tex) real_tex(target, level, GL_RGBA, width, height, border, GL_RGBA, GL_UNSIGNED_BYTE, out);
                free(out);
                return;
            }
        }
    }
    if (real_tex) real_tex(target, level, internalformat, width, height, border, format, type, pixels);
}

extern "C" void glTexSubImage2D(GLenum target, GLint level, GLint xoffset, GLint yoffset,
                                GLsizei width, GLsizei height, GLenum format, GLenum type,
                                const void *pixels) {
    if (format == GL_RGBA && type == 0x8033 && pixels && width > 0 && height > 0) {
        size_t n = (size_t)width * (size_t)height;
        uint8_t *out = (uint8_t *)malloc(n * 4);
        if (out) {
            const uint16_t *src = (const uint16_t *)pixels;
            for (size_t i = 0; i < n; i++) {
                uint16_t p = src[i];
                out[i*4+0] = (uint8_t)(((p >> 12) & 0xF) * 17);
                out[i*4+1] = (uint8_t)(((p >> 8) & 0xF) * 17);
                out[i*4+2] = (uint8_t)(((p >> 4) & 0xF) * 17);
                out[i*4+3] = (uint8_t)((p & 0xF) * 17);
            }
            if (real_sub) real_sub(target, level, xoffset, yoffset, width, height, GL_RGBA, GL_UNSIGNED_BYTE, out);
            free(out);
            return;
        }
    }
    if (real_sub) real_sub(target, level, xoffset, yoffset, width, height, format, type, pixels);
}

static inline uint8_t clamp8(int v) {
    return v < 0 ? 0 : (v > 255 ? 255 : (uint8_t)v);
}

static void etc1_decode_cpu(const uint8_t *data, uint8_t *out, int w, int h) {
    static const int mods[8][4] = {
        {2, 8, -2, -8}, {5, 17, -5, -17}, {9, 29, -9, -29}, {13, 42, -13, -42},
        {18, 60, -18, -60}, {24, 80, -24, -80}, {33, 106, -33, -106}, {47, 183, -47, -183}
    };
    int bw = (w + 3) / 4, bh = (h + 3) / 4;
    for (int by = 0; by < bh; by++) {
        for (int bx = 0; bx < bw; bx++) {
            const uint8_t *p = data + ((size_t)by * bw + bx) * 8;
            uint32_t hi = ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | p[3];
            uint32_t lo = ((uint32_t)p[4] << 24) | ((uint32_t)p[5] << 16) | ((uint32_t)p[6] << 8) | p[7];
            int R1 = (hi >> 28) & 15, R2 = (hi >> 24) & 15;
            int G1 = (hi >> 20) & 15, G2 = (hi >> 16) & 15;
            int B1 = (hi >> 12) & 15, B2 = (hi >> 8) & 15;
            int t1 = (hi >> 5) & 7, t2 = (hi >> 2) & 7;
            bool diff = (hi >> 1) & 1, flip = hi & 1;
            int r1, g1, b1, r2, g2, b2;
            if (diff) {
                int r5 = (R1 << 1) | (R1 >> 3), g5 = (G1 << 1) | (G1 >> 3), b5 = (B1 << 1) | (B1 >> 3);
                int dr = (R2 << 29) >> 29, dg = (G2 << 29) >> 29, db = (B2 << 29) >> 29;
                int r5b = r5 + dr, g5b = g5 + dg, b5b = b5 + db;
                r5b = r5b < 0 ? 0 : (r5b > 31 ? 31 : r5b);
                g5b = g5b < 0 ? 0 : (g5b > 31 ? 31 : g5b);
                b5b = b5b < 0 ? 0 : (b5b > 31 ? 31 : b5b);
                r1 = (r5 << 3) | (r5 >> 2); r2 = (r5b << 3) | (r5b >> 2);
                g1 = (g5 << 3) | (g5 >> 2); g2 = (g5b << 3) | (g5b >> 2);
                b1 = (b5 << 3) | (b5 >> 2); b2 = (b5b << 3) | (b5b >> 2);
            } else {
                r1 = R1 * 17; g1 = G1 * 17; b1 = B1 * 17;
                r2 = R2 * 17; g2 = G2 * 17; b2 = B2 * 17;
            }
            for (int y = 0; y < 4; y++) {
                for (int x = 0; x < 4; x++) {
                    int x2 = flip ? y : x, y2 = flip ? x : y;
                    int i = x2 * 4 + y2;
                    int msb = (lo >> (i + 16)) & 1, lsb = (lo >> i) & 1;
                    int idx = (msb << 1) | lsb;
                    int sub = (x2 >= 2) ? 1 : 0;
                    int m = mods[sub ? t2 : t1][idx];
                    int px = bx * 4 + x, py = by * 4 + y;
                    if (px < w && py < h) {
                        size_t o = ((size_t)py * w + px) * 4;
                        out[o + 0] = clamp8((sub ? r2 : r1) + m);
                        out[o + 1] = clamp8((sub ? g2 : g1) + m);
                        out[o + 2] = clamp8((sub ? b2 : b1) + m);
                        out[o + 3] = 255;
                    }
                }
            }
        }
    }
}

struct AstcStrip {
    int y;
    int h;
    size_t off;
    size_t size;
    uint8_t *out;
    bool ok;
    AstcStrip() : y(0), h(0), off(0), size(0), out(nullptr), ok(false) {}
};

struct AstcStripCtx {
    const uint8_t *data;
    size_t imageSize;
    int width;
    int bx;
    int by;
    astc_codec::FootprintType fp;
    std::vector<AstcStrip> *strips;
    std::atomic<int> *next;
};

static uint64_t astc_hash(const uint8_t *p, size_t n, int w, int h, int fmt, int size) {
    uint64_t x = 1469598103934665603ULL;
    for (size_t i = 0; i < n; i++) {
        x ^= p[i];
        x *= 1099511628211ULL;
    }
    x ^= (uint64_t)w * 73856093ULL;
    x ^= (uint64_t)h * 19349663ULL;
    x ^= (uint64_t)fmt * 83492791ULL;
    x ^= (uint64_t)size * 2654435761ULL;
    return x;
}

static void ensure_astc_cache_dir() {
    mkdir(PVZ2_GL_CACHE_ROOT, 0770);
    mkdir(PVZ2_GL_CACHE_ROOT "/glcache", 0770);
}

static uint8_t *cache_read_rgba(const char *path, int *w, int *h) {
    FILE *f = fopen(path, "rb");
    if (!f) return nullptr;
    uint32_t hdr[2];
    if (fread(hdr, sizeof(uint32_t), 2, f) != 2) {
        fclose(f);
        return nullptr;
    }
    int cw = (int)hdr[0], ch = (int)hdr[1];
    if (cw <= 0 || ch <= 0 || cw > 8192 || ch > 8192) {
        fclose(f);
        return nullptr;
    }
    size_t sz = (size_t)cw * (size_t)ch * 4;
    uint8_t *buf = (uint8_t *)malloc(sz);
    if (!buf) {
        fclose(f);
        return nullptr;
    }
    if (fread(buf, 1, sz, f) != sz) {
        free(buf);
        fclose(f);
        return nullptr;
    }
    fclose(f);
    *w = cw;
    *h = ch;
    return buf;
}

static void cache_write_rgba(const char *path, int w, int h, const std::vector<AstcStrip> &strips) {
    static std::atomic<unsigned> sequence{0};
    char temporary[320];
    snprintf(temporary,sizeof(temporary),"%s.tmp.%d.%u",path,getpid(),sequence.fetch_add(1));
    FILE *f = fopen(temporary, "wb");
    if (!f) return;
    uint32_t hdr[2] = {(uint32_t)w, (uint32_t)h};
    bool ok = fwrite(hdr, sizeof(uint32_t), 2, f) == 2;
    for (size_t i = 0; i < strips.size(); i++) {
        const AstcStrip &s = strips[i];
        if (!s.out) { ok=false; break; }
        long off = 8 + (long)s.y * w * 4;
        if (fseek(f, off, SEEK_SET) == 0) {
            size_t bytes=(size_t)w*s.h*4;
            if (fwrite(s.out, 1, bytes, f) != bytes) ok=false;
        } else ok=false;
    }
    if (fclose(f) != 0) ok=false;
    if (!ok || rename(temporary,path) != 0) unlink(temporary);
}

#include "decode_pool.inc"

static void decode_one_strip(AstcStripCtx *ctx, size_t i) {
    AstcStrip &s = (*ctx->strips)[i];
#ifdef PVZ2_DECODE_DIAGNOSTICS
    LOGI("demand strip width=%d y=%d h=%d off=%zu bytes=%zu fp=%d",
         ctx->width, s.y, s.h, s.off, s.size, int(ctx->fp));
#endif
    size_t outsz = (size_t)ctx->width * s.h * 4;
    s.out = (uint8_t *)malloc(outsz);
    s.ok = s.out && astc_codec::ASTCDecompressToRGBA(
        ctx->data+s.off,s.size,ctx->width,s.h,ctx->fp,s.out,outsz,(size_t)ctx->width*4);
}

static void *astc_strip_worker(void *arg) {
    AstcStripCtx *ctx = (AstcStripCtx *)arg;
    int i;
    while ((i = ctx->next->fetch_add(1)) < (int)ctx->strips->size()) {
        decode_one_strip(ctx,i);
    }
    return nullptr;
}

static int astc_worker_count(long online_cpus, size_t jobs) {
    if (jobs == 0) return 0;
    // sysconf may return -1. Keep that case and single-CPU devices serial.
    int count = online_cpus < 1 ? 1 :
        (online_cpus > PVZ2_ASTC_MAX_THREADS ? PVZ2_ASTC_MAX_THREADS : (int)online_cpus);
    if (jobs < (size_t)count) count = (int)jobs;
    return count;
}

static int astc_strip_block_rows(int width, int height, int by) {
    int rows = 256 / by;
    if (rows < 1) rows = 1;
    // Give large textures enough independent jobs to use the higher limit.
    // Keep every split on an ASTC block boundary, including 5x5 and 6x6.
    if ((long long)width * height >= 1024 * 1024) {
        const int count = astc_worker_count(sysconf(_SC_NPROCESSORS_ONLN),
                                            (size_t)((height + by - 1) / by));
        const int balanced = ((height + by - 1) / by + count - 1) / count;
        if (balanced < rows) rows = balanced;
    }
    return rows;
}

static bool astc_decode_parallel(const uint8_t *data, size_t imageSize,
                                 int width, int height, int bx, int by,
                                 astc_codec::FootprintType fp,
                                 std::vector<AstcStrip> &strips) {
    const int maxThreads = PVZ2_ASTC_MAX_THREADS;
    const int nthreads = decode_pool().threads();

    std::atomic<int> next(0);
    AstcStripCtx ctx;
    ctx.data = data;
    ctx.imageSize = imageSize;
    ctx.width = width;
    ctx.bx = bx;
    ctx.by = by;
    ctx.fp = fp;
    ctx.strips = &strips;
    ctx.next = &next;

    if (nthreads == 0) {
        astc_strip_worker(&ctx);
    } else {
        auto fence=std::make_shared<DecodeFence>(strips.size());
        for (size_t i=0;i<strips.size();++i) {
            decode_pool().submit(true,0,[&ctx,i,fence]{decode_one_strip(&ctx,i);fence->finish();});
        }
        fence->wait();
    }
    LOGI("ASTC workers limit=%d selected=%d started=%d strips=%zu",
         maxThreads, nthreads, nthreads, strips.size());

    bool ok = true;
    for (size_t i = 0; i < strips.size(); i++) {
        if (!strips[i].ok) {
            ok = false;
            break;
        }
    }
    if (!ok) {
        for (size_t i = 0; i < strips.size(); i++) {
            free(strips[i].out);
            strips[i].out = nullptr;
        }
    }
    return ok;
}

extern "C" void glCompressedTexImage2D(GLenum target, GLint level, GLenum internalformat,
                                       GLsizei width, GLsizei height, GLint border,
                                       GLsizei imageSize, const void *data) {
    if (ctex_logs < 500) {
        ctex_logs++;
        LOGI("glCompressedTexImage2D internal=0x%x %dx%d size=%d border=%d",
             internalformat, width, height, imageSize, border);
    }
    // ETC1 (0x8D64): decode to RGBA8888
    if (internalformat == 0x8D64 && data && width > 0 && height > 0 && real_tex) {
        uint8_t *out = (uint8_t *)malloc((size_t)width * (size_t)height * 4);
        if (out) {
            etc1_decode_cpu((const uint8_t *)data, out, width, height);
            real_tex(target, level, GL_RGBA, width, height, border, GL_RGBA, GL_UNSIGNED_BYTE, out);
            free(out);
            return;
        }
    }
    // ASTC (0x93B0..0x93BD): full-resolution decode, parallel strips + internal cache
    if (data && width > 0 && height > 0 && real_tex) {
        astc_codec::FootprintType fp;
        int bx = 4, by = 4;
        bool is_astc = true;
        switch (internalformat) {
            case 0x93B0: fp = astc_codec::FootprintType::k4x4; bx = 4; by = 4; break;
            case 0x93B1: fp = astc_codec::FootprintType::k5x4; bx = 5; by = 4; break;
            case 0x93B2: fp = astc_codec::FootprintType::k5x5; bx = 5; by = 5; break;
            case 0x93B3: fp = astc_codec::FootprintType::k6x5; bx = 6; by = 5; break;
            case 0x93B4: fp = astc_codec::FootprintType::k6x6; bx = 6; by = 6; break;
            case 0x93B5: fp = astc_codec::FootprintType::k8x5; bx = 8; by = 5; break;
            case 0x93B6: fp = astc_codec::FootprintType::k8x6; bx = 8; by = 6; break;
            case 0x93B7: fp = astc_codec::FootprintType::k8x8; bx = 8; by = 8; break;
            case 0x93B8: fp = astc_codec::FootprintType::k10x5; bx = 10; by = 5; break;
            case 0x93B9: fp = astc_codec::FootprintType::k10x6; bx = 10; by = 6; break;
            case 0x93BA: fp = astc_codec::FootprintType::k10x8; bx = 10; by = 8; break;
            case 0x93BB: fp = astc_codec::FootprintType::k10x10; bx = 10; by = 10; break;
            case 0x93BC: fp = astc_codec::FootprintType::k12x10; bx = 12; by = 10; break;
            case 0x93BD: fp = astc_codec::FootprintType::k12x12; bx = 12; by = 12; break;
            default: is_astc = false; break;
        }
        if (is_astc) {
            struct timespec ts0, ts1;
            clock_gettime(CLOCK_MONOTONIC, &ts0);
            char cpath[256];
            cpath[0] = 0;
            uint64_t hash = astc_hash((const uint8_t *)data, (size_t)imageSize,
                                      width, height, (int)internalformat, imageSize);
            if (level == 0) {
                ensure_astc_cache_dir();
                snprintf(cpath, sizeof(cpath),
                         PVZ2_GL_CACHE_ROOT "/glcache/%016llx.rgba",
                         (unsigned long long)hash);
                int cw = 0, ch = 0;
                uint8_t *cb = cache_read_rgba(cpath, &cw, &ch);
                if (!cb && join_prefetch(hash)) cb=cache_read_rgba(cpath,&cw,&ch);
                if (cb && (cw!=width || ch!=height)) {free(cb);cb=nullptr;}
                if (cb) {
                    LOGI("ASTC cache hit %dx%d", cw, ch);
                    real_tex(target, level, GL_RGBA, cw, ch, border, GL_RGBA, GL_UNSIGNED_BYTE, cb);
                    free(cb);
                    return;
                }
            }
            int blocksPerRow = (width + bx - 1) / bx;
            int blockRows = (height + by - 1) / by;
            int stripBlocks = astc_strip_block_rows(width, height, by);
            std::vector<AstcStrip> strips;
            for (int r = 0; r < blockRows; r += stripBlocks) {
                int rows = blockRows - r;
                if (rows > stripBlocks) rows = stripBlocks;
                AstcStrip s;
                s.y = r * by;
                s.h = rows * by;
                if (s.h > height - s.y) s.h = height - s.y;
                s.off = (size_t)r * blocksPerRow * 16;
                s.size = (size_t)rows * blocksPerRow * 16;
                if (s.off + s.size > (size_t)imageSize) s.size = (size_t)imageSize - s.off;
                strips.push_back(s);
            }
            bool ok = false;
            if (!strips.empty()) {
                ok = astc_decode_parallel((const uint8_t *)data, (size_t)imageSize,
                                          width, height, bx, by, fp, strips);
            }
            if (ok) {
                real_tex(target, level, GL_RGBA, width, height, border, GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
                for (size_t i = 0; i < strips.size(); i++) {
                    AstcStrip &s = strips[i];
                    if (real_sub) real_sub(target, level, 0, s.y, width, s.h, GL_RGBA, GL_UNSIGNED_BYTE, s.out);
                }
                if (cpath[0]) cache_write_rgba(cpath, width, height, strips);
                for (size_t i = 0; i < strips.size(); i++) free(strips[i].out);
                clock_gettime(CLOCK_MONOTONIC, &ts1);
                long long ms = (ts1.tv_sec - ts0.tv_sec) * 1000LL + (ts1.tv_nsec - ts0.tv_nsec) / 1000000LL;
                LOGI("ASTC %dx%d strips=%zu full-res %lldms", width, height, strips.size(), ms);
                return;
            }
            for (size_t i = 0; i < strips.size(); i++) free(strips[i].out);
            LOGI("ASTC decode failed internal=0x%x %dx%d size=%d", internalformat, width, height, imageSize);
        }
    }
    if (real_ctex) real_ctex(target, level, internalformat, width, height, border, imageSize, data);
}

__attribute__((constructor)) static void init_shim() {
    void *gles = dlopen("libGLESv2.so", RTLD_NOW | RTLD_GLOBAL);
    if (!gles) { LOGI("dlopen libGLESv2 failed: %s", dlerror()); }
    real_tex = (PFN_glTexImage2D)dlsym(RTLD_NEXT, "glTexImage2D");
    if (!real_tex) real_tex = (PFN_glTexImage2D)dlsym(gles, "glTexImage2D");
    real_sub = (PFN_glTexSubImage2D)dlsym(RTLD_NEXT, "glTexSubImage2D");
    if (!real_sub) real_sub = (PFN_glTexSubImage2D)dlsym(gles, "glTexSubImage2D");
    real_ctex = (PFN_glCompressedTexImage2D)dlsym(RTLD_NEXT, "glCompressedTexImage2D");
    if (!real_ctex) real_ctex = (PFN_glCompressedTexImage2D)dlsym(gles, "glCompressedTexImage2D");
    void *etc1 = dlopen("/system/lib/libETC1.so", RTLD_NOW | RTLD_GLOBAL);
    if (!etc1) etc1 = dlopen("libETC1.so", RTLD_NOW | RTLD_GLOBAL);
    if (etc1) etc1_decode = (PFN_etc1_decode)dlsym(etc1, "etc1_decode_image");
    LOGI("init: real tex=%p sub=%p ctex=%p etc1h=%p etc1=%p err=%s",
         real_tex, real_sub, real_ctex, etc1, etc1_decode, etc1 ? "" : dlerror());

    ModInfo mi;
    mi.name = "libSrc.so";
    dl_iterate_phdr(find_cb, &mi);
    if (!mi.base) { LOGI("libSrc not found"); return; }
    LOGI("libSrc base=%p", (void *)mi.base);
    patch_got(mi, "glTexImage2D", (void *)glTexImage2D);
    patch_got(mi, "glTexSubImage2D", (void *)glTexSubImage2D);
    patch_got(mi, "glCompressedTexImage2D", (void *)glCompressedTexImage2D);
    start_texture_prefetch();
#ifdef PVZ2_DECODE_DIAGNOSTICS
    struct sigaction diagnostic{};
    diagnostic.sa_sigaction = decode_fault;
    diagnostic.sa_flags = SA_SIGINFO;
    sigemptyset(&diagnostic.sa_mask);
    sigaction(SIGSEGV, &diagnostic, &previous_decode_segv);
#endif
    LOGI("done patching");
}


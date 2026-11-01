// CPU-only process-lifetime workers. No worker calls OpenGL.
#include <algorithm>
#include <condition_variable>
#include <deque>
#include <functional>
#include <memory>
#include <mutex>
#include <sys/resource.h>
#include <sys/statvfs.h>
#include <zlib.h>

struct DecodeWork {
    uint64_t owner;
    std::function<void()> run;
};

class DecodePool {
    std::mutex mutex;
    std::condition_variable wake;
    std::deque<DecodeWork> urgent, background;
    bool started = false;
    int count = 0;
    static void *entry(void *p) { static_cast<DecodePool *>(p)->loop(); return nullptr; }
    void loop() {
        for (;;) {
            DecodeWork job;
            bool foreground;
            {
                std::unique_lock<std::mutex> lock(mutex);
                wake.wait(lock, [&]{ return !urgent.empty() || !background.empty(); });
                foreground = !urgent.empty();
                auto &queue = foreground ? urgent : background;
                job = std::move(queue.front()); queue.pop_front();
            }
            job.run();
        }
    }
public:
    void start() {
        std::lock_guard<std::mutex> lock(mutex);
        if (started) return;
        started = true;
        long cpus = sysconf(_SC_NPROCESSORS_ONLN);
        int wanted = cpus >= 8 ? 4 : cpus >= 4 ? 3 : 2;
        for (int i = 0; i < wanted; ++i) {
            pthread_t id;
            if (pthread_create(&id, nullptr, entry, this) == 0) {
                pthread_detach(id); ++count;
            }
        }
        LOGI("persistent ASTC workers requested=%d started=%d", wanted, count);
    }
    int threads() { start(); std::lock_guard<std::mutex> lock(mutex); return count; }
    bool submit(bool high, uint64_t owner, std::function<void()> run) {
        start();
        std::lock_guard<std::mutex> lock(mutex);
        if (!count) return false;
        (high ? urgent : background).push_back({owner, std::move(run)});
        wake.notify_all(); return true;
    }
    void promote(uint64_t hash) {
        std::lock_guard<std::mutex> lock(mutex);
        for (auto it = background.begin(); it != background.end();) {
            if (it->owner == hash) { urgent.push_back(std::move(*it)); it = background.erase(it); }
            else ++it;
        }
        wake.notify_all();
    }
};

static DecodePool &decode_pool() {
    // Deliberately survives static destruction while Android terminates workers.
    static DecodePool *pool = new DecodePool;
    return *pool;
}

struct DecodeFence {
    std::mutex mutex;
    std::condition_variable changed;
    size_t remaining;
    explicit DecodeFence(size_t n) : remaining(n) {}
    void finish() { std::lock_guard<std::mutex> lock(mutex); if (--remaining == 0) changed.notify_all(); }
    void wait() { std::unique_lock<std::mutex> lock(mutex); changed.wait(lock,[&]{return remaining == 0;}); }
};

struct PrefetchTexture {
    const char *file;
    uint64_t fileSize, partOffset;
    uint32_t packed, raw, compressed, offset, bytes, width, height, format;
    uint64_t hash;
};
#include "prefetch_index.inc"

struct PrefetchState {
    uint64_t hash = 0;
    int width = 0, height = 0;
    astc_codec::FootprintType footprint=astc_codec::FootprintType::k5x5;
    uint8_t *source = nullptr;
    std::vector<AstcStrip> strips;
    std::atomic<int> remaining{0};
    std::mutex mutex;
    std::condition_variable changed;
    bool finished = false;
    char cache[256];
    ~PrefetchState() { free(source); for (auto &s : strips) free(s.out); }
    void wait() { std::unique_lock<std::mutex> lock(mutex); changed.wait(lock,[&]{return finished;}); }
};

struct PrefetchRegistry {
    std::mutex mutex;
    std::shared_ptr<PrefetchState> active;
    size_t next = 0;
    bool stopped = false;
};
static PrefetchRegistry &prefetch_registry() {
    static PrefetchRegistry *registry = new PrefetchRegistry;
    return *registry;
}

static bool join_prefetch(uint64_t hash) {
    std::shared_ptr<PrefetchState> state;
    {
        auto &r = prefetch_registry(); std::lock_guard<std::mutex> lock(r.mutex);
        if (r.active && r.active->hash == hash) state = r.active;
    }
    if (!state) return false;
    decode_pool().promote(hash);
    state->wait();
    return true;
}

static void prefetch_next();
static void queue_prefetch_next() {
    decode_pool().submit(false, 0, []{ prefetch_next(); });
}

static void prefetch_next() {
    const PrefetchTexture *texture;
    {
        auto &r = prefetch_registry(); std::lock_guard<std::mutex> lock(r.mutex);
        if (r.stopped || r.next >= kPrefetchTextureCount) return;
        texture = &kPrefetchTextures[r.next++];
    }
    const auto &t = *texture;
    char cache[256];
    snprintf(cache, sizeof(cache), PVZ2_GL_CACHE_ROOT "/glcache/%016llx.rgba", (unsigned long long)t.hash);
    struct stat st;
    uint64_t rgbaBytes = (uint64_t)t.width*t.height*4;
    if (!t.width || !t.height || t.width > 8192 || t.height > 8192 || t.raw > 128*1024*1024 ||
        (stat(cache, &st) == 0 && (uint64_t)st.st_size == 8+rgbaBytes)) {
        queue_prefetch_next(); return;
    }
    struct statvfs space;
    if (statvfs(PVZ2_GL_CACHE_ROOT, &space) == 0 &&
        (uint64_t)space.f_bavail*space.f_frsize < rgbaBytes+256*1024*1024) {
        auto &r = prefetch_registry(); std::lock_guard<std::mutex> lock(r.mutex);
        r.stopped = true; LOGI("background cache paused: insufficient free space"); return;
    }
    char path[512];
    snprintf(path, sizeof(path), "/sdcard/Android/data/com.popcap.pvz2cthd.reconstruction/files/%s", t.file);
    FILE *file = fopen(path, "rb");
    if (!file || fstat(fileno(file), &st) || (uint64_t)st.st_size != t.fileSize) {
        if (file) fclose(file); queue_prefetch_next(); return;
    }
    auto state = std::make_shared<PrefetchState>();
    state->hash=t.hash; state->width=t.width; state->height=t.height;
    state->footprint=t.format==0x93b4 ? astc_codec::FootprintType::k6x6 : astc_codec::FootprintType::k5x5;
    snprintf(state->cache,sizeof(state->cache),"%s",cache);
    state->source=(uint8_t *)malloc(t.bytes);
    bool readOK = false;
    if (state->source && (uint64_t)t.offset+t.bytes <= t.raw) {
        if (!t.compressed) {
            readOK = fseeko(file,(off_t)(t.partOffset+t.offset),SEEK_SET)==0 &&
                     fread(state->source,1,t.bytes,file)==t.bytes;
        } else if (t.packed <= 128*1024*1024) {
            auto packed=(uint8_t *)malloc(t.packed); auto raw=(uint8_t *)malloc(t.raw);
            if (packed && raw && fseeko(file,(off_t)t.partOffset,SEEK_SET)==0 &&
                fread(packed,1,t.packed,file)==t.packed) {
                uLongf size=t.raw;
                if (uncompress(raw,&size,packed,t.packed)==Z_OK && size==t.raw) {
                    memcpy(state->source,raw+t.offset,t.bytes); readOK=true;
                }
            }
            free(packed); free(raw);
        }
    }
    fclose(file);
    if (!readOK || astc_hash(state->source,t.bytes,t.width,t.height,t.format,t.bytes)!=t.hash) {
        queue_prefetch_next(); return;
    }
    const int by=t.format==0x93b4 ? 6 : 5, rowsPerStrip=32;
    int blockRows=(t.height+by-1)/by, blocksPerRow=(t.width+by-1)/by;
    for (int row=0;row<blockRows;row+=rowsPerStrip) {
        AstcStrip strip;
        int rows=std::min(rowsPerStrip,blockRows-row);
        strip.y=row*by; strip.h=std::min(rows*by,(int)t.height-strip.y);
        strip.off=(size_t)row*blocksPerRow*16;strip.size=(size_t)rows*blocksPerRow*16;
        state->strips.push_back(strip);
    }
    state->remaining=state->strips.size();
    {
        auto &r=prefetch_registry();std::lock_guard<std::mutex> lock(r.mutex);r.active=state;
    }
    for (size_t i=0;i<state->strips.size();++i) {
        decode_pool().submit(false,t.hash,[state,i]{
            auto &s=state->strips[i];size_t bytes=(size_t)state->width*s.h*4;
            s.out=(uint8_t *)malloc(bytes);
            s.ok=s.out && astc_codec::ASTCDecompressToRGBA(state->source+s.off,s.size,
                 state->width,s.h,state->footprint,s.out,bytes,(size_t)state->width*4);
            if (state->remaining.fetch_sub(1)==1) {
                bool ok=true;for (const auto &strip:state->strips) ok &= strip.ok;
                if (ok) cache_write_rgba(state->cache,state->width,state->height,state->strips);
                {
                    std::lock_guard<std::mutex> lock(state->mutex);state->finished=true;state->changed.notify_all();
                }
                {
                    auto &r=prefetch_registry();std::lock_guard<std::mutex> lock(r.mutex);r.active.reset();
                }
                queue_prefetch_next();
            }
        });
    }
}

static void start_texture_prefetch() {
    ensure_astc_cache_dir();
    if (decode_pool().threads()) queue_prefetch_next();
}

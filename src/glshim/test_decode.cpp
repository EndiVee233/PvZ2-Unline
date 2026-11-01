// Android differential test: production strip scheduling against a serial decode.
#include <pthread.h>
#include <unistd.h>
#include <errno.h>
#include <assert.h>
#include <algorithm>
#include <vector>

static long test_cpus = 20;
static int failure_mode = 0, create_calls = 0, join_calls = 0;
static std::vector<pthread_t> live_threads;
static long test_sysconf(int name) {
    return name == _SC_NPROCESSORS_ONLN ? test_cpus : sysconf(name);
}
static int test_create(pthread_t *id, const pthread_attr_t *attr,
                       void *(*worker)(void *), void *ctx) {
    ++create_calls;
    if (failure_mode == 2 || (failure_mode == 1 && create_calls % 2 == 1)) return EAGAIN;
    int result = pthread_create(id, attr, worker, ctx);
    if (result == 0) live_threads.push_back(*id);
    return result;
}
static int test_join(pthread_t id, void **result) {
    auto pos = std::find(live_threads.begin(), live_threads.end(), id);
    assert(pos != live_threads.end());
    live_threads.erase(pos);
    ++join_calls;
    return pthread_join(id, result);
}
#define sysconf test_sysconf
#define pthread_create test_create
#define pthread_join test_join
#include "glshim.cpp"
#undef sysconf
#undef pthread_create
#undef pthread_join

static long long millis() {
    timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000LL + ts.tv_nsec / 1000000;
}
static void check(const std::vector<uint8_t>& seed, int w, int h, int block,
                  astc_codec::FootprintType footprint, long cpus, int fail) {
    test_cpus = cpus;
    failure_mode = fail;
    create_calls = join_calls = 0;
    const int across = (w + block - 1) / block, rows = (h + block - 1) / block;
    std::vector<uint8_t> data((size_t)across * rows * 16);
    for (size_t i = 0; i < data.size(); i += 16)
        memcpy(data.data() + i, seed.data() + (i % seed.size()), 16);
    std::vector<uint8_t> serial((size_t)w * h * 4);
    assert(astc_codec::ASTCDecompressToRGBA(data.data(), data.size(), w, h,
                footprint, serial.data(), serial.size(), (size_t)w * 4));
    const int step = astc_strip_block_rows(w, h, block);
    std::vector<AstcStrip> strips;
    for (int row = 0; row < rows; row += step) {
        AstcStrip strip;
        strip.y = row * block;
        strip.h = std::min(std::min(step, rows - row) * block, h - strip.y);
        strip.off = (size_t)row * across * 16;
        strip.size = (size_t)std::min(step, rows - row) * across * 16;
        strips.push_back(strip);
    }
    long long start = millis();
    assert(astc_decode_parallel(data.data(), data.size(), w, h, block, block, footprint, strips));
    const long long elapsed = millis() - start;
    for (auto& strip : strips) {
        assert(memcmp(serial.data() + (size_t)strip.y * w * 4, strip.out,
                      (size_t)strip.h * w * 4) == 0);
        free(strip.out);
    }
    // Workers are detached once and reused for every later image. Changing the
    // simulated CPU count or creation-failure mode must not recreate the pool.
    static bool first = true;
    if (first) { assert(create_calls <= 4); first=false; }
    else assert(create_calls == 0);
    assert(join_calls == 0);
    assert(decode_pool().threads() >= 2 && decode_pool().threads() <= 4);
    printf("PASS block=%d size=%dx%d cpus=%ld strips=%zu created=%d failure=%d ms=%lld\n",
           block, w, h, cpus, strips.size(), join_calls, fail, elapsed);
    fflush(stdout);
}
int main(int argc, char **argv) {
    assert(argc == 2);
    assert(astc_worker_count(20, 100) == 4);
    assert(astc_worker_count(8, 100) == 4);
    assert(astc_worker_count(20, 3) == 3);
    assert(astc_worker_count(-1, 100) == 1);
    assert(astc_worker_count(1, 100) == 1);
    assert(astc_worker_count(20, 0) == 0);
    printf("WSA online_cpus=%ld; worker-cap selection checks passed\n", sysconf(_SC_NPROCESSORS_ONLN));
    for (int block : {4, 5, 6}) {
        char path[1024];
        snprintf(path, sizeof(path), "%s/atlas_small_%dx%d.astc", argv[1], block, block);
        FILE *file = fopen(path, "rb"); assert(file);
        fseek(file, 0, SEEK_END); long size = ftell(file); assert(size > 16);
        fseek(file, 16, SEEK_SET);
        std::vector<uint8_t> seed(size - 16);
        assert(fread(seed.data(), 1, seed.size(), file) == seed.size()); fclose(file);
        const auto fp = block == 4 ? astc_codec::FootprintType::k4x4 :
                        block == 5 ? astc_codec::FootprintType::k5x5 : astc_codec::FootprintType::k6x6;
        check(seed, 1031, 1027, block, fp, 20, 0);
        check(seed, 257, 259, block, fp, 1, 0);
        check(seed, 1031, 1027, block, fp, 20, 1);
        check(seed, 1031, 1027, block, fp, 20, 2);
        if (block == 6) {
            check(seed, 4096, 4096, block, fp, 4, 0);
            check(seed, 4096, 4096, block, fp, 20, 0);
        }
    }
    puts("PASS pixel comparisons and persistent pool reuse; later failure injections do not recreate workers");
}

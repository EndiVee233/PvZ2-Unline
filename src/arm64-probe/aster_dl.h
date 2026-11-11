// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <cstddef>
#include <cstdint>
#include <cstdio>
class DynarmicHost;
struct AAssetManager;
bool registerAsterDynamicLoader(DynarmicHost& host, AAssetManager* assets);
bool checkAsterDynamicLoader(DynarmicHost& host);
bool checkAsterLibraryQueries(DynarmicHost& host);
bool asterGuestImageRange(DynarmicHost& host, uint32_t address, uint64_t end, size_t pageSize);
FILE* asterOpenGuestProcMaps(DynarmicHost& host, const char* path, bool& handled);

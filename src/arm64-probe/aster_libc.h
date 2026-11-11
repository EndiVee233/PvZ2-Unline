// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <string>
#include <cstdint>

class DynarmicHost;

void registerAsterLibc(DynarmicHost& host);
int32_t asterGuestStringCompare(DynarmicHost& host,uint32_t a,uint32_t b,bool ignoreCase);
bool checkAsterLibc(DynarmicHost& host);
bool checkAsterThreads(DynarmicHost& host);
bool checkAsterPosix(DynarmicHost& host);
bool checkAsterMemory(DynarmicHost& host);
bool checkAsterLocale(DynarmicHost& host);
void configureAsterTemporaryFiles(const std::string& directory);
std::string asterTemporaryPattern();

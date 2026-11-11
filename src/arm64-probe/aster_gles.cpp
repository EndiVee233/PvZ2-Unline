// SPDX-License-Identifier: GPL-3.0-or-later
#define GL_GLEXT_PROTOTYPES 1
#include "aster_gles.h"
#include "dynarmic_host.h"
#include "thunk_manager.h"

#include <EGL/egl.h>
#include <GLES/gl.h>
#include <GLES/glext.h>
#include <array>
#include <bit>
#include <cstring>
#include <elf.h>
#include <android/log.h>

namespace {
using Host = DynarmicHost;
using Jit = Dynarmic::A32::Jit;

void* guestSpan(Host& host, uint32_t address, uint64_t size) {
    if (!address || size > host.GetGuestMemorySize() - address) {
        host.Fail("Invalid Aster GLES guest pointer");
        return nullptr;
    }
    return host.GetGuestMemoryBase() + address;
}

const void* arrayPointer(Host& host, uint32_t address) {
    GLint binding = 0;
    glGetIntegerv(GL_ARRAY_BUFFER_BINDING, &binding);
    if (binding || !address) return reinterpret_cast<const void*>(uintptr_t(address));
    return guestSpan(host, address, 1);
}

struct Pbuffer {
    EGLDisplay display = EGL_NO_DISPLAY;
    EGLContext context = EGL_NO_CONTEXT;
    EGLSurface surface = EGL_NO_SURFACE;
    bool initialized = false;

    bool open() {
        display = eglGetDisplay(EGL_DEFAULT_DISPLAY);
        initialized = display != EGL_NO_DISPLAY && eglInitialize(display, nullptr, nullptr);
        if (!initialized || !eglBindAPI(EGL_OPENGL_ES_API)) return false;
        const EGLint configAttrs[] = {EGL_SURFACE_TYPE, EGL_PBUFFER_BIT, EGL_RENDERABLE_TYPE,
                                     EGL_OPENGL_ES_BIT, EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8,
                                     EGL_BLUE_SIZE, 8, EGL_NONE};
        EGLConfig config;
        EGLint count;
        if (!eglChooseConfig(display, configAttrs, &config, 1, &count) || !count) return false;
        const EGLint surfaceAttrs[] = {EGL_WIDTH, 8, EGL_HEIGHT, 8, EGL_NONE};
        const EGLint contextAttrs[] = {EGL_CONTEXT_CLIENT_VERSION, 1, EGL_NONE};
        surface = eglCreatePbufferSurface(display, config, surfaceAttrs);
        context = eglCreateContext(display, config, EGL_NO_CONTEXT, contextAttrs);
        return surface != EGL_NO_SURFACE && context != EGL_NO_CONTEXT
            && eglMakeCurrent(display, surface, surface, context);
    }

    ~Pbuffer() {
        if (!initialized) return;
        eglMakeCurrent(display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
        if (context != EGL_NO_CONTEXT) eglDestroyContext(display, context);
        if (surface != EGL_NO_SURFACE) eglDestroySurface(display, surface);
        eglTerminate(display);
    }
};
}

void registerAsterGles(Host& host) {
    auto& manager = host.GetThunkManager();
    for (auto [name, function] : {std::pair{"glClientActiveTexture", &glClientActiveTexture},
                                  {"glEnableClientState", &glEnableClientState},
                                  {"glDisableClientState", &glDisableClientState},
                                  {"glMatrixMode", &glMatrixMode}, {"glShadeModel", &glShadeModel}}) {
        manager.RegisterThunk(name, [function](Jit& jit, Host&) { function(jit.Regs()[0]); });
    }
    for (auto [name, function] : {std::pair{"glPushMatrix", &glPushMatrix},
                                  {"glPopMatrix", &glPopMatrix}, {"glLoadIdentity", &glLoadIdentity}}) {
        manager.RegisterThunk(name, [function](Jit&, Host&) { function(); });
    }
    for (auto [name, function] : {std::pair{"glVertexPointer", &glVertexPointer},
                                  {"glColorPointer", &glColorPointer}, {"glTexCoordPointer", &glTexCoordPointer}}) {
        manager.RegisterThunk(name, [function](Jit& jit, Host& guest) {
            const auto& a = jit.Regs();
            const void* pointer = arrayPointer(guest, a[3]);
            if (!guest.HasFailed()) function(int32_t(a[0]), a[1], int32_t(a[2]), pointer);
        });
    }
    manager.RegisterThunk("glNormalPointer", [](Jit& jit, Host& guest) {
        const auto& a = jit.Regs();
        const void* pointer = arrayPointer(guest, a[2]);
        if (!guest.HasFailed()) glNormalPointer(a[0], int32_t(a[1]), pointer);
    });
    manager.RegisterThunk("glScalef", [](Jit& jit, Host&) {
        const auto& a = jit.Regs();
        glScalef(std::bit_cast<float>(a[0]), std::bit_cast<float>(a[1]), std::bit_cast<float>(a[2]));
    });
    manager.RegisterThunk("glLoadMatrixf", [](Jit& jit, Host& guest) {
        std::array<GLfloat, 16> matrix;
        if (const void* data = guestSpan(guest, jit.Regs()[0], sizeof(matrix))) {
            std::memcpy(matrix.data(), data, sizeof(matrix));
            glLoadMatrixf(matrix.data());
        }
    });
    manager.RegisterThunk("glTexEnvf", [](Jit& jit, Host&) {
        const auto& a = jit.Regs();
        glTexEnvf(a[0], a[1], std::bit_cast<float>(a[2]));
    });
    manager.RegisterThunk("glAlphaFunc", [](Jit& jit, Host&) {
        glAlphaFunc(jit.Regs()[0], std::bit_cast<float>(jit.Regs()[1]));
    });
    manager.RegisterThunk("glGenFramebuffersOES", [](Jit& jit, Host& guest) {
        const auto& a = jit.Regs();
        const int32_t count = int32_t(a[0]);
        if (count <= 0) glGenFramebuffersOES(count, nullptr);
        else if (void* data = guestSpan(guest, a[1], uint64_t(count) * sizeof(GLuint)))
            glGenFramebuffersOES(count, static_cast<GLuint*>(data));
    });
    manager.RegisterThunk("glDeleteFramebuffersOES", [](Jit& jit, Host& guest) {
        const auto& a = jit.Regs();
        const int32_t count = int32_t(a[0]);
        if (count <= 0) glDeleteFramebuffersOES(count, nullptr);
        else if (const void* data = guestSpan(guest, a[1], uint64_t(count) * sizeof(GLuint)))
            glDeleteFramebuffersOES(count, static_cast<const GLuint*>(data));
    });
    manager.RegisterThunk("glBindFramebufferOES", [](Jit& jit, Host&) {
        glBindFramebufferOES(jit.Regs()[0], jit.Regs()[1]);
    });
    manager.RegisterThunk("glFramebufferTexture2DOES", [](Jit& jit, Host& guest) {
        const auto& a = jit.Regs();
        glFramebufferTexture2DOES(a[0], a[1], a[2], a[3], int32_t(guest.ReadStackWord(jit, 0)));
    });
    manager.RegisterThunk("glCheckFramebufferStatusOES", [](Jit& jit, Host&) {
        jit.Regs()[0] = glCheckFramebufferStatusOES(jit.Regs()[0]);
    });
}

bool checkAsterGles(Host& host) {
    Pbuffer buffer;
    if (!buffer.open()) return false;
    constexpr GLfloat vertices[] = {-1.f, -1.f, 1.f, -1.f, 0.f, 1.f};
    const uint32_t address = host.GuestAlloc(sizeof(vertices));
    if (!address) return false;
    std::memcpy(guestSpan(host, address, sizeof(vertices)), vertices, sizeof(vertices));
    auto call = [&](const char* name, std::vector<uint32_t> args) {
        return host.RunFunction(host.GetThunkManager().ResolveSymbol(name, STT_FUNC), args);
    };
    glViewport(0, 0, 8, 8);
    glClearColor(0.f, 0.f, 0.f, 1.f);
    glClear(GL_COLOR_BUFFER_BIT);
    glColor4f(1.f, 0.f, 0.f, 1.f);
    call("glMatrixMode", {GL_MODELVIEW});
    call("glLoadIdentity", {});
    call("glEnableClientState", {GL_VERTEX_ARRAY});
    call("glVertexPointer", {2, GL_FLOAT, 0, address});
    call("glDrawArrays", {GL_TRIANGLES, 0, 3});
    call("glDisableClientState", {GL_VERTEX_ARRAY});
    GLubyte pixel[4]{};
    glReadPixels(4, 3, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, pixel);
    return !host.HasFailed() && glGetError() == GL_NO_ERROR && pixel[0] > 240 && pixel[1] < 10 && pixel[2] < 10;
}

bool checkAsterGlesShim(Host& host) {
    Pbuffer buffer;
    if (!buffer.open()) return false;
    // Exercise the *guest* compatibility shim and its newly patched engine
    // GOT slot, including the nine-word AAPCS texture-upload call boundary.
    const uint32_t upload = host.MemoryRead32(0x40000000 + 0x1822db8);
    const auto expected = host.FindLibrarySymbol("libRestart.so","glTexImage2D");
    if (!upload || upload != expected) return false;
    const auto data=host.GuestAlloc(8);
    if (!data) return false;
    for (unsigned i=0;i<4;++i) host.MemoryWrite16(data+2*i,0xf00f);
    GLuint texture=0;
    glGenTextures(1,&texture);
    glBindTexture(GL_TEXTURE_2D,texture);
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_NEAREST);
    host.RunFunction(upload,{GL_TEXTURE_2D,0,GL_UNSIGNED_SHORT_4_4_4_4,2,2,0,
        GL_RGBA,GL_UNSIGNED_SHORT_4_4_4_4,data});
    const GLfloat vertices[]={-1.f,-1.f,1.f,-1.f,0.f,1.f};
    const GLfloat coords[]={0.f,0.f,0.f,0.f,0.f,0.f};
    glViewport(0,0,8,8);
    glClearColor(0.f,0.f,0.f,1.f);
    glClear(GL_COLOR_BUFFER_BIT);
    glMatrixMode(GL_PROJECTION);glLoadIdentity();
    glMatrixMode(GL_MODELVIEW);glLoadIdentity();
    glColor4f(1.f,1.f,1.f,1.f);
    glEnable(GL_TEXTURE_2D);
    glEnableClientState(GL_VERTEX_ARRAY);glEnableClientState(GL_TEXTURE_COORD_ARRAY);
    glVertexPointer(2,GL_FLOAT,0,vertices);glTexCoordPointer(2,GL_FLOAT,0,coords);
    glDrawArrays(GL_TRIANGLES,0,3);
    GLubyte pixel[4]{};
    glReadPixels(4,3,1,1,GL_RGBA,GL_UNSIGNED_BYTE,pixel);
    const auto error=glGetError();
    glDisableClientState(GL_TEXTURE_COORD_ARRAY);glDisableClientState(GL_VERTEX_ARRAY);
    glDisable(GL_TEXTURE_2D);glDeleteTextures(1,&texture);
    const bool passed=!host.HasFailed() && !error && pixel[0]>240 && pixel[1]<10 && pixel[2]<10;
    __android_log_print(ANDROID_LOG_INFO,"AsterArm64Probe",
        "Guest RGBA4444 shim upload=%d pixel=%u,%u,%u,%u error=0x%x",passed,pixel[0],pixel[1],pixel[2],pixel[3],error);
    return passed;
}

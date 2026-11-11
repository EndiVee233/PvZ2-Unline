package com.popcap.SexyAppFramework;

import android.content.Context;
import android.graphics.Canvas;
import android.opengl.GLSurfaceView;
import android.util.DisplayMetrics;
import android.util.Log;
import android.view.Display;
import android.view.GestureDetector;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.ScaleGestureDetector;
import android.view.SurfaceHolder;
import android.view.View;
import android.view.WindowManager;
import javax.microedition.khronos.egl.EGL10;
import javax.microedition.khronos.egl.EGLConfig;
import javax.microedition.khronos.egl.EGLContext;
import javax.microedition.khronos.egl.EGLDisplay;
import javax.microedition.khronos.opengles.GL10;

/* JADX INFO: loaded from: K:\反编译PvZ2\raw\classes.dex */
public class AndroidSurfaceView extends GLSurfaceView {
    public static final int DEBUG_CHECK_GL_ERROR = 1;
    public static final int DEBUG_LOG_GL_CALLS = 2;
    private AndroidRenderer mAndroidRenderer;
    private int mGLESVersionSupported;
    private GestureDetector mGestureDetector;
    private int mOrigAppHeight;
    private int mOrigAppWidth;
    private ScaleGestureDetector mScaleGestureDetector;
    private AndroidUIEventManager mUIEventManager;
    private float mViewScaleFactor;
    private WindowManager mWindowManager;
    public boolean mbDrawingFrames;
    public boolean mbFocusState;
    private boolean mbIsInitialized;
    public Object mbNotifyOnDrawEventObject;
    static boolean DEBUG = true;
    static boolean ShowFPS = false;
    static String LogTAG = "SexyEGL";

    /* JADX INFO: Access modifiers changed from: private */
    private native void Native_onDrawFrame();

    /* JADX INFO: Access modifiers changed from: private */
    private native void Native_onSurfaceChanged(int i, int i2);

    /* JADX INFO: Access modifiers changed from: private */
    private native void Native_onSurfaceCreated();

    public AndroidSurfaceView(Context InContext, WindowManager InWindowManager, AndroidUIEventManager InEventManager, int InGLESVersionSupported) {
        super(InContext);
        this.mGLESVersionSupported = 0;
        this.mbDrawingFrames = false;
        this.mbFocusState = false;
        this.mViewScaleFactor = 0.5f;
        this.mWindowManager = InWindowManager;
        this.mUIEventManager = InEventManager;
        this.mGLESVersionSupported = InGLESVersionSupported;
        this.mbIsInitialized = false;
        setFocusable(true);
        setFocusableInTouchMode(true);
        if (android.os.Build.VERSION.SDK_INT >= 26) setDefaultFocusHighlightEnabled(false);
        this.mOrigAppWidth = 0;
        this.mOrigAppHeight = 0;
        this.mGestureDetector = new GestureDetector(InContext, this.mUIEventManager);
        this.mGestureDetector.setIsLongpressEnabled(true);
        this.mScaleGestureDetector = new ScaleGestureDetector(InContext, this.mUIEventManager);
        setOnTouchListener(new View.OnTouchListener() { // from class: com.popcap.SexyAppFramework.AndroidSurfaceView.1
            @Override // android.view.View.OnTouchListener
            public boolean onTouch(View v, MotionEvent event) {
                if (!SexyAppFrameworkActivity.instance().SplashScreenShowing()) {
                    boolean GestureDetected = AndroidSurfaceView.this.mScaleGestureDetector.onTouchEvent(event) | AndroidSurfaceView.this.mGestureDetector.onTouchEvent(event);
                    return AndroidSurfaceView.this.mUIEventManager.HandleTouchEvent(event) | GestureDetected;
                }
                return false;
            }
        });
    }

    public void init(int InRedBits, int InGreenBits, int InBlueBits, int InAlphaBits, int InDepthBits, int InStencilBits) {
        if (InAlphaBits > 0) {
            SurfaceHolder holder = getHolder();
            holder.setFormat(-3);
        }
        setEGLContextFactory(new AndroidEGLContextFactory(this));
        setEGLConfigChooser(new GraphicsConfigChooser(InRedBits, InGreenBits, InBlueBits, InAlphaBits, InDepthBits, InStencilBits, this.mGLESVersionSupported));
        this.mAndroidRenderer = new AndroidRenderer(this);
        setRenderer(this.mAndroidRenderer);
        this.mbIsInitialized = true;
    }

    private int Graphics_GetGLViewSysFBO() {
        return -1;
    }

    public boolean Graphics_IsOpenGLES20() {
        return this.mGLESVersionSupported >= 2;
    }

    public int Graphics_GetOpenGLESVersion() {
        return Graphics_IsOpenGLES20() ? 2 : 1;
    }

    private float Graphics_GetGLViewScaleFactor() {
        return this.mViewScaleFactor;
    }

    private void Graphics_SetGLViewScaleFactor(float InScaleFactor) {
        this.mViewScaleFactor = InScaleFactor;
    }

    private boolean Graphics_CanSetGLViewScaleFactor() {
        return true;
    }

    public void Graphics_GetScreenSizeInPixels(int[] outWidthHeight) {
        synchronized (this) {
            outWidthHeight[0] = this.mOrigAppWidth;
            outWidthHeight[1] = this.mOrigAppHeight;
        }
    }

    public void SetScreenSizeInPixels(int width, int height) {
        this.mOrigAppWidth = width;
        this.mOrigAppHeight = height;
    }

    private void Graphics_GetScreenSizeInPoints(int[] outWidthHeight) {
        synchronized (this) {
            Display disp = this.mWindowManager.getDefaultDisplay();
            DisplayMetrics metrics = new DisplayMetrics();
            disp.getMetrics(metrics);
            float width = getWidth();
            float height = getHeight();
            float f = metrics.density;
            outWidthHeight[0] = Math.round((width * 1.0f) + 0.5f);
            outWidthHeight[1] = Math.round((height * 1.0f) + 0.5f);
        }
    }

    public final boolean IsInitailized() {
        return this.mbIsInitialized;
    }

    @Override // android.view.View, android.view.KeyEvent.Callback
    public boolean onKeyDown(int InKeyCode, KeyEvent InEvent) {
        // Keep game keyboard focus out of the offscreen IME helper. Real text
        // fields and dialogs receive their own key events and retain Tab.
        if (InKeyCode == KeyEvent.KEYCODE_TAB) return true;
        if (DEBUG) {
            Log.i("Surface", "onKeyDown.");
        }
        if (this.mUIEventManager.HandleKeyEvent(InEvent) || InKeyCode == 82) {
            return true;
        }
        return super.onKeyDown(InKeyCode, InEvent);
    }

    @Override // android.view.View, android.view.KeyEvent.Callback
    public boolean onKeyUp(int InKeyCode, KeyEvent InEvent) {
        if (InKeyCode == KeyEvent.KEYCODE_TAB) return true;
        if (DEBUG) {
            Log.i("Surface", "onKeyUp.");
        }
        if (this.mUIEventManager.HandleKeyEvent(InEvent)) {
            return true;
        }
        return super.onKeyUp(InKeyCode, InEvent);
    }

    @Override // android.view.View
    public boolean onTouchEvent(MotionEvent InEvent) {
        if (DEBUG) {
            Log.i("Surface", "onTouchEvent.");
        }
        if (SexyAppFrameworkActivity.instance().SplashScreenShowing()) {
            return false;
        }
        return this.mUIEventManager.HandleTouchEvent(InEvent);
    }

    @Override
    public boolean onHoverEvent(MotionEvent event) {
        if ((event.getSource() & 0x2002) != 0x2002) return super.onHoverEvent(event);
        int action = event.getActionMasked();
        if (action == MotionEvent.ACTION_HOVER_EXIT) return true;
        if (action != MotionEvent.ACTION_HOVER_MOVE && action != MotionEvent.ACTION_HOVER_ENTER)
            return super.onHoverEvent(event);
        if (SexyAppFrameworkActivity.instance().SplashScreenShowing()) return false;
        return this.mUIEventManager.HandleHoverEvent(event);
    }

    @Override // android.view.SurfaceView, android.view.View
    protected void dispatchDraw(Canvas canvas) {
        super.dispatchDraw(canvas);
    }

    @Override // android.opengl.GLSurfaceView, android.view.SurfaceView, android.view.View
    protected void onAttachedToWindow() {
        if (DEBUG) {
            Log.i("Surface", "onAttachedToWindow.");
        }
        super.onAttachedToWindow();
    }

    @Override // android.opengl.GLSurfaceView, android.view.SurfaceView, android.view.View
    protected void onDetachedFromWindow() {
        if (DEBUG) {
            Log.i("Surface", "onDetachedFromWindow.");
        }
        super.onDetachedFromWindow();
    }

    @Override // android.view.SurfaceView, android.view.View
    protected void onMeasure(int widthMeasureSpec, int heightMeasureSpec) {
        if (DEBUG) {
            Log.i("Surface", "onMeasure.");
        }
        super.onMeasure(widthMeasureSpec, heightMeasureSpec);
    }

    @Override // android.view.SurfaceView, android.view.View
    protected void onWindowVisibilityChanged(int visibility) {
        if (DEBUG) {
            Log.i("Surface", "onWindowVisibilityChanged.");
        }
        super.onWindowVisibilityChanged(visibility);
    }

    @Override // android.opengl.GLSurfaceView
    public void onResume() {
        if (DEBUG) {
            Log.i("Surface", "onResume.");
        }
        SexyAppFrameworkActivity.instance().AddSplashScreen();
        AndroidRenderer androidRenderer = this.mAndroidRenderer;
        AndroidRenderer.mFirstDraw = true;
        AndroidRenderer androidRenderer2 = this.mAndroidRenderer;
        AndroidRenderer.mDrawCount = 0;
    }

    @Override // android.opengl.GLSurfaceView
    public void onPause() {
        if (DEBUG) {
            Log.i("Surface", "onPause.");
        }
    }

    public void SetFocusState(boolean inFocusState) {
        this.mbFocusState = inFocusState;
    }

    public boolean HasDrawnFirstFrame() {
        AndroidRenderer androidRenderer = this.mAndroidRenderer;
        return !AndroidRenderer.mFirstDraw;
    }

    private static class FPSCounter {
        int frames;
        long startTime;

        private FPSCounter() {
            this.startTime = System.nanoTime();
            this.frames = 0;
        }

        public void logFrame() {
            this.frames++;
            if (System.nanoTime() - this.startTime >= 1000000000) {
                Log.d("FPSCounter", "fps: " + this.frames);
                this.frames = 0;
                this.startTime = System.nanoTime();
            }
        }
    }

    private static class AndroidEGLContextFactory implements GLSurfaceView.EGLContextFactory {
        private static int EGL_CONTEXT_CLIENT_VERSION = 12440;
        private AndroidSurfaceView mView;

        public AndroidEGLContextFactory(AndroidSurfaceView InView) {
            this.mView = null;
            this.mView = InView;
        }

        @Override // android.opengl.GLSurfaceView.EGLContextFactory
        public EGLContext createContext(EGL10 egl, EGLDisplay display, EGLConfig eglConfig) {
            int GLESVers = this.mView.Graphics_GetOpenGLESVersion();
            int[] attrib_list = null;
            if (GLESVers > 0) {
                attrib_list = new int[]{EGL_CONTEXT_CLIENT_VERSION, GLESVers, 12344};
            }
            checkEglError("Before eglCreateContext", egl);
            EGLContext newContext = egl.eglCreateContext(display, eglConfig, EGL10.EGL_NO_CONTEXT, attrib_list);
            if (newContext == EGL10.EGL_NO_CONTEXT) {
                checkEglError("After eglCreateContext", egl);
            }
            return newContext;
        }

        @Override // android.opengl.GLSurfaceView.EGLContextFactory
        public void destroyContext(EGL10 egl, EGLDisplay display, EGLContext deadContext) {
            if (deadContext != EGL10.EGL_NO_CONTEXT) {
                egl.eglDestroyContext(display, deadContext);
            }
        }

        private static void checkEglError(String prompt, EGL10 egl) {
            while (true) {
                int error = egl.eglGetError();
                if (error != 12288) {
                    Log.e(AndroidSurfaceView.LogTAG, String.format("%s: EGL error: 0x%x", prompt, Integer.valueOf(error)));
                } else {
                    return;
                }
            }
        }
    }

    private static class GraphicsConfigChooser implements GLSurfaceView.EGLConfigChooser {
        private int mAlphaSize;
        private int mBlueSize;
        private int mDepthSize;
        private int mGLESVersion;
        private int mGreenSize;
        private int mRedSize;
        private int mStencilSize;
        private int[] mValue = new int[1];
        private static int EGL_OPENGL_ES_BIT = 1;
        private static int EGL_OPENGL_ES2_BIT = 4;
        private static int[] s_configAttribs2 = {12324, 4, 12323, 4, 12322, 4, 12352, EGL_OPENGL_ES2_BIT, 12344};

        public GraphicsConfigChooser(int InRedSize, int InGreenSize, int InBlueSize, int InAlphaSize, int InDepthSize, int InStencilSize, int InGLESVersion) {
            this.mRedSize = 0;
            this.mGreenSize = 0;
            this.mBlueSize = 0;
            this.mAlphaSize = 0;
            this.mDepthSize = 0;
            this.mStencilSize = 0;
            this.mGLESVersion = 0;
            this.mRedSize = InRedSize;
            this.mGreenSize = InGreenSize;
            this.mBlueSize = InBlueSize;
            this.mAlphaSize = InAlphaSize;
            this.mDepthSize = InDepthSize;
            this.mStencilSize = InStencilSize;
            this.mGLESVersion = InGLESVersion;
        }

        public EGLConfig chooseConfigFromList(EGL10 egl, EGLDisplay display, EGLConfig[] configs) {
            for (EGLConfig config : configs) {
                int d = findConfigAttrib(egl, display, config, 12325, 0);
                int s = findConfigAttrib(egl, display, config, 12326, 0);
                if (d >= this.mDepthSize && s >= this.mStencilSize) {
                    int r = findConfigAttrib(egl, display, config, 12324, 0);
                    int g = findConfigAttrib(egl, display, config, 12323, 0);
                    int b = findConfigAttrib(egl, display, config, 12322, 0);
                    int a = findConfigAttrib(egl, display, config, 12321, 0);
                    if (r == this.mRedSize && g == this.mGreenSize && b == this.mBlueSize && a == this.mAlphaSize) {
                        Log.i("GraphicsConfigChooser", "found the match config.");
                        printConfig(egl, display, config);
                        return config;
                    }
                }
            }
            Log.i("GraphicsConfigChooser", "can't find the match config.");
            return null;
        }

        @Override // android.opengl.GLSurfaceView.EGLConfigChooser
        public EGLConfig chooseConfig(EGL10 egl, EGLDisplay display) {
            switch (this.mGLESVersion) {
                case 1:
                    int RenderableType = EGL_OPENGL_ES_BIT;
                    break;
                case 2:
                    int RenderableType2 = EGL_OPENGL_ES2_BIT;
                    break;
            }
            int[] num_configs = new int[1];
            if (!egl.eglChooseConfig(display, s_configAttribs2, null, 0, num_configs)) {
                Log.i("GraphicsConfigChooser", "eglChooseConfig get config nums failed.");
            }
            int iConfigCount = num_configs[0];
            if (iConfigCount <= 0) {
                throw new IllegalArgumentException("No configs match configSpec");
            }
            EGLConfig[] configs = new EGLConfig[iConfigCount];
            if (!egl.eglChooseConfig(display, s_configAttribs2, configs, iConfigCount, num_configs)) {
                Log.i("GraphicsConfigChooser", "eglChooseConfig get detail configs failed.");
            }
            if (AndroidSurfaceView.DEBUG) {
                printConfigs(egl, display, configs);
            }
            return chooseConfigFromList(egl, display, configs);
        }

        private int findConfigAttrib(EGL10 egl, EGLDisplay display, EGLConfig config, int attribute, int defaultValue) {
            if (egl.eglGetConfigAttrib(display, config, attribute, this.mValue)) {
                int defaultValue2 = this.mValue[0];
                return defaultValue2;
            }
            return defaultValue;
        }

        private void printConfigs(EGL10 egl, EGLDisplay display, EGLConfig[] configs) {
            int numConfigs = configs.length;
            Log.w(AndroidSurfaceView.LogTAG, String.format("%d configurations", Integer.valueOf(numConfigs)));
            for (int i = 0; i < numConfigs; i++) {
                Log.w(AndroidSurfaceView.LogTAG, String.format("Configuration %d:\n", Integer.valueOf(i)));
                printConfig(egl, display, configs[i]);
            }
        }

        private void printConfig(EGL10 egl, EGLDisplay display, EGLConfig config) {
            int[] attributes = {12320, 12321, 12322, 12323, 12324, 12325, 12326, 12327, 12328, 12329, 12330, 12331, 12332, 12333, 12334, 12335, 12336, 12337, 12338, 12339, 12340, 12343, 12342, 12341, 12345, 12346, 12347, 12348, 12349, 12350, 12351, 12352, 12354};
            String[] names = {"EGL_BUFFER_SIZE", "EGL_ALPHA_SIZE", "EGL_BLUE_SIZE", "EGL_GREEN_SIZE", "EGL_RED_SIZE", "EGL_DEPTH_SIZE", "EGL_STENCIL_SIZE", "EGL_CONFIG_CAVEAT", "EGL_CONFIG_ID", "EGL_LEVEL", "EGL_MAX_PBUFFER_HEIGHT", "EGL_MAX_PBUFFER_PIXELS", "EGL_MAX_PBUFFER_WIDTH", "EGL_NATIVE_RENDERABLE", "EGL_NATIVE_VISUAL_ID", "EGL_NATIVE_VISUAL_TYPE", "EGL_PRESERVED_RESOURCES", "EGL_SAMPLES", "EGL_SAMPLE_BUFFERS", "EGL_SURFACE_TYPE", "EGL_TRANSPARENT_TYPE", "EGL_TRANSPARENT_RED_VALUE", "EGL_TRANSPARENT_GREEN_VALUE", "EGL_TRANSPARENT_BLUE_VALUE", "EGL_BIND_TO_TEXTURE_RGB", "EGL_BIND_TO_TEXTURE_RGBA", "EGL_MIN_SWAP_INTERVAL", "EGL_MAX_SWAP_INTERVAL", "EGL_LUMINANCE_SIZE", "EGL_ALPHA_MASK_SIZE", "EGL_COLOR_BUFFER_TYPE", "EGL_RENDERABLE_TYPE", "EGL_CONFORMANT"};
            int[] value = new int[1];
            for (int i = 0; i < attributes.length; i++) {
                int attribute = attributes[i];
                String name = names[i];
                if (egl.eglGetConfigAttrib(display, config, attribute, value)) {
                    Log.w(AndroidSurfaceView.LogTAG, String.format("  %s: %d\n", name, Integer.valueOf(value[0])));
                } else {
                    Log.w(AndroidSurfaceView.LogTAG, String.format("  %s: failed\n", name));
                    while (egl.eglGetError() != 12288) {
                    }
                }
            }
        }
    }

    private static class AndroidRenderer implements GLSurfaceView.Renderer {
        FPSCounter mFPS = null;
        AndroidSurfaceView mGLView;
        static boolean mFirstDraw = true;
        static int mDrawCount = 0;
        static boolean mHaveSurfaceChanged = false;
        static float gColor = 0.0f;

        AndroidRenderer(AndroidSurfaceView InView) {
            this.mGLView = null;
            this.mGLView = InView;
        }

        @Override // android.opengl.GLSurfaceView.Renderer
        public void onDrawFrame(GL10 gl) {
            this.mGLView.mbDrawingFrames = true;
            if (this.mGLView.mbNotifyOnDrawEventObject != null) {
                synchronized (this.mGLView.mbNotifyOnDrawEventObject) {
                    this.mGLView.mbNotifyOnDrawEventObject.notifyAll();
                    this.mGLView.mbNotifyOnDrawEventObject = null;
                }
            } else if (!this.mGLView.mbFocusState) {
                if (AndroidSurfaceView.DEBUG) {
                    Log.i("Surface", "onDrawFrame - Don't Draw, don't update when we're suspended.");
                    return;
                }
                return;
            }
            this.mGLView.Native_onDrawFrame();
            mDrawCount++;
            if (mFirstDraw && mDrawCount > 10) {
                mFirstDraw = false;
                SexyAppFrameworkActivity.instance().RemoveSplashScreen();
            }
            if (AndroidSurfaceView.ShowFPS) {
                if (this.mFPS == null) {
                    this.mFPS = new FPSCounter();
                }
                this.mFPS.logFrame();
            }
        }

        @Override // android.opengl.GLSurfaceView.Renderer
        public void onSurfaceCreated(GL10 gl, EGLConfig config) {
            if (AndroidSurfaceView.DEBUG) {
                Log.i("Surface", "onSurfaceCreated - Native_onSurfaceCreated");
            }
            this.mGLView.Native_onSurfaceCreated();
        }

        @Override // android.opengl.GLSurfaceView.Renderer
        public void onSurfaceChanged(GL10 gl, int width, int height) {
            if (AndroidSurfaceView.DEBUG) {
                Log.i("Surface", String.format("onSurfaceChanged - Native_onSurfaceChanged :: %d %d", Integer.valueOf(width), Integer.valueOf(height)));
            }
            if (!mHaveSurfaceChanged) {
                this.mGLView.Native_onSurfaceChanged(width, height);
                mHaveSurfaceChanged = true;
            }
        }
    }
}

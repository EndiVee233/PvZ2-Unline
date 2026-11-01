package com.popcap.SexyAppFramework;

import android.support.v4.view.accessibility.AccessibilityNodeInfoCompat;
import android.util.Log;
import android.view.GestureDetector;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.ScaleGestureDetector;
import com.talkweb.securitypay.common.SegmentFinder;
import java.nio.BufferOverflowException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.LinkedList;
import java.util.Map;
import java.util.TreeMap;

/* JADX INFO: loaded from: K:\反编译PvZ2\raw\classes.dex */
public class AndroidUIEventManager implements GestureDetector.OnGestureListener, ScaleGestureDetector.OnScaleGestureListener {
    static final /* synthetic */ boolean $assertionsDisabled;
    public static final int EVENT_BACK_BUTTON = 5;
    private static final int EVENT_FLICK = 4;
    private static final int EVENT_KEY = 1;
    private static final int EVENT_LONGPRESS = 2;
    private static final int EVENT_PINCH = 3;
    private static final int EVENT_TOUCH = 0;
    private static final float SCALE_THRESHOLD = 5.0E-4f;
    private static final int TouchPhase_TOUCH_BEGAN = 0;
    private static final int TouchPhase_TOUCH_CANCELLED = 4;
    private static final int TouchPhase_TOUCH_ENDED = 3;
    private static final int TouchPhase_TOUCH_MOVED = 1;
    private static final int TouchPhase_TOUCH_STATIONARY = 2;
    private float endScale;
    private float startScale;
    private float prevScaleMag = 0.0f;
    boolean mbAppHasFocus = false;
    Map<Integer, UITouchTracker> mTouches = new TreeMap();
    LinkedList<UIEvent> mEvents = new LinkedList<>();
    private UITouchTracker mMouseHoverTracker;

    static {
        $assertionsDisabled = !AndroidUIEventManager.class.desiredAssertionStatus();
    }

    class UITouchTracker {
        float X;
        float Y;
        int mPointerId;
        int mTapCount;
        double mTimestampMS;
        int phase;
        float previousX;
        float previousY;

        UITouchTracker() {
        }

        void InitializeFromMotionEvent(MotionEvent event, int inPointerIdx, int inPhase, int actionIdx) {
            this.mPointerId = inPointerIdx;
            float x = event.getX(actionIdx);
            this.X = x;
            this.previousX = x;
            float y = event.getY(actionIdx);
            this.Y = y;
            this.previousY = y;
            this.mTapCount = 1;
            this.mTimestampMS = AndroidUIEventManager.this.GetTimeStamp();
            this.phase = inPhase;
        }

        void UpdateFromMotionEvent(MotionEvent event, int inPhase, int actionIdx) {
            this.previousX = this.X;
            this.previousY = this.Y;
            this.X = event.getX(actionIdx);
            this.Y = event.getY(actionIdx);
            this.mTimestampMS = AndroidUIEventManager.this.GetTimeStamp();
            this.phase = inPhase;
            if (inPhase == 1 && this.X == this.previousX && this.Y == this.previousY) {
                this.phase = 2;
            }
        }

        void MarkAsCancelled() {
            this.previousX = this.X;
            this.previousY = this.Y;
            this.mTimestampMS = AndroidUIEventManager.this.GetTimeStamp();
            this.phase = 4;
        }
    }

    abstract class UIEvent {
        public abstract boolean Serialize(ByteBuffer byteBuffer);

        UIEvent() {
        }
    }

    class UITouchEvent extends UIEvent {
        int X;
        int Y;
        int ident;
        int phase;
        int previousX;
        int previousY;
        int tapCount;
        double timestamp;

        public UITouchEvent(UITouchTracker InTouch) {
            super();
            this.ident = InTouch.mPointerId + 1;
            assert this.ident != 0;
            this.X = (int) InTouch.X;
            this.Y = (int) InTouch.Y;
            this.previousX = (int) InTouch.previousX;
            this.previousY = (int) InTouch.previousY;
            this.timestamp = InTouch.mTimestampMS;
            this.phase = InTouch.phase;
        }

        @Override // com.popcap.SexyAppFramework.AndroidUIEventManager.UIEvent
        public boolean Serialize(ByteBuffer buf) {
            try {
                buf.putInt(0);
                buf.putInt(this.ident);
                buf.putInt(this.X);
                buf.putInt(this.Y);
                buf.putInt(this.previousX);
                buf.putInt(this.previousY);
                buf.putInt(1);
                buf.putDouble(this.timestamp);
                buf.putInt(this.phase);
                buf.putInt(-559038737);
                buf.putInt(-559038737);
                return true;
            } catch (BufferOverflowException e) {
                return false;
            }
        }
    }

    public class UIKeyEvent extends UIEvent {
        int mKeyCode;
        int mKeyEvent;
        int mRepeatCount;
        double mTimestampMS;
        int mUnicodeChar;

        public UIKeyEvent(KeyEvent event) {
            super();
            this.mKeyCode = event.getKeyCode();
            this.mUnicodeChar = event.getUnicodeChar();
            this.mKeyEvent = event.getAction();
            this.mRepeatCount = event.getRepeatCount();
            this.mTimestampMS = AndroidUIEventManager.this.GetTimeStamp();
        }

        @Override // com.popcap.SexyAppFramework.AndroidUIEventManager.UIEvent
        public boolean Serialize(ByteBuffer buf) {
            try {
                buf.putInt(1);
                buf.putInt(this.mKeyCode);
                buf.putInt(this.mUnicodeChar);
                buf.putInt(this.mKeyEvent);
                buf.putDouble(this.mTimestampMS);
                buf.putInt(this.mRepeatCount);
                buf.putInt(-559038737);
                return true;
            } catch (BufferOverflowException e) {
                return false;
            }
        }
    }

    public class UILongPressEvent extends UIEvent {
        int X;
        int Y;

        public UILongPressEvent(MotionEvent event) {
            super();
            int actionIdx = event.getActionIndex();
            event.getPointerId(actionIdx);
            this.X = (int) event.getX(actionIdx);
            this.Y = (int) event.getY(actionIdx);
        }

        @Override // com.popcap.SexyAppFramework.AndroidUIEventManager.UIEvent
        public boolean Serialize(ByteBuffer buf) {
            try {
                buf.putInt(2);
                buf.putInt(this.X);
                buf.putInt(this.Y);
                buf.putInt(-559038737);
                return true;
            } catch (BufferOverflowException e) {
                return false;
            }
        }
    }

    public class UIPinchEvent extends UIEvent {
        int X;
        int Y;
        float scaleDelta;
        float scaleDistSq;

        public UIPinchEvent(int X, int Y, float scaleDistSq, float scaleDelta) {
            super();
            this.X = X;
            this.Y = Y;
            this.scaleDistSq = scaleDistSq;
            this.scaleDelta = scaleDelta;
        }

        @Override // com.popcap.SexyAppFramework.AndroidUIEventManager.UIEvent
        public boolean Serialize(ByteBuffer buf) {
            try {
                buf.putInt(3);
                buf.putInt(this.X);
                buf.putInt(this.Y);
                buf.putFloat(this.scaleDistSq);
                buf.putFloat(this.scaleDelta);
                buf.putInt(-559038737);
                buf.putInt(-559038737);
                buf.putInt(-559038737);
                return true;
            } catch (BufferOverflowException e) {
                return false;
            }
        }
    }

    public class UIFlickEvent extends UIEvent {
        int X;
        int Y;
        double velocityX;
        double velocityY;

        public UIFlickEvent(int X, int Y, float velocityX, float velocityY) {
            super();
            this.X = X;
            this.Y = Y;
            this.velocityX = velocityX;
            this.velocityY = velocityY;
        }

        @Override // com.popcap.SexyAppFramework.AndroidUIEventManager.UIEvent
        public boolean Serialize(ByteBuffer buf) {
            try {
                buf.putInt(4);
                buf.putInt(this.X);
                buf.putInt(this.Y);
                buf.putDouble(this.velocityX);
                buf.putDouble(this.velocityY);
                buf.putInt(-559038737);
                return true;
            } catch (BufferOverflowException e) {
                return false;
            }
        }
    }

    public class UIBackButtonEvent extends UIEvent {
        public UIBackButtonEvent() {
            super();
        }

        @Override // com.popcap.SexyAppFramework.AndroidUIEventManager.UIEvent
        public boolean Serialize(ByteBuffer buf) {
            try {
                buf.putInt(5);
                buf.putInt(-559038737);
                buf.putInt(-559038737);
                buf.putInt(-559038737);
                return true;
            } catch (BufferOverflowException e) {
                return false;
            }
        }
    }

    public void HandleGotFocus() {
        this.mbAppHasFocus = true;
    }

    public void HandleLostFocus() {
        this.mbAppHasFocus = false;
        this.mMouseHoverTracker = null;
        for (UITouchTracker tracker : this.mTouches.values()) {
            tracker.MarkAsCancelled();
            EnqueueEvent(new UITouchEvent(tracker));
        }
        this.mTouches.clear();
    }

    public boolean HandleTouchEvent(MotionEvent event) {
        UITouchTracker touch;
        if (!this.mbAppHasFocus) {
            return false;
        }
        int iPtrCount = event.getPointerCount();
        int action = event.getActionMasked();
        switch (action) {
            case 0:
            case 5:
                int actionIdx = event.getActionIndex();
                int pointerId = event.getPointerId(actionIdx);
                if (this.mTouches.containsKey(Integer.valueOf(pointerId))) {
                    this.mTouches.remove(Integer.valueOf(pointerId));
                    if (!$assertionsDisabled) {
                        throw new AssertionError();
                    }
                }
                UITouchTracker newUITouch = new UITouchTracker();
                newUITouch.InitializeFromMotionEvent(event, pointerId, 0, actionIdx);
                this.mTouches.put(Integer.valueOf(pointerId), newUITouch);
                EnqueueEvent(new UITouchEvent(newUITouch));
                break;
            case 1:
            case 6:
                int actionIdx2 = event.getActionIndex();
                int pointerId2 = event.getPointerId(actionIdx2);
                if (this.mTouches.containsKey(Integer.valueOf(pointerId2))) {
                    UITouchTracker touch2 = this.mTouches.remove(Integer.valueOf(pointerId2));
                    if (touch2 != null) {
                        touch2.UpdateFromMotionEvent(event, 3, actionIdx2);
                        EnqueueEvent(new UITouchEvent(touch2));
                    }
                } else if (!$assertionsDisabled) {
                    throw new AssertionError();
                }
                break;
            case 2:
                for (int actionIdx3 = 0; actionIdx3 < iPtrCount; actionIdx3++) {
                    int pointerId3 = event.getPointerId(actionIdx3);
                    if (this.mTouches.containsKey(Integer.valueOf(pointerId3))) {
                        UITouchTracker touch3 = this.mTouches.get(Integer.valueOf(pointerId3));
                        touch3.UpdateFromMotionEvent(event, 1, actionIdx3);
                        EnqueueEvent(new UITouchEvent(touch3));
                    } else if (!$assertionsDisabled) {
                        throw new AssertionError();
                    }
                }
                break;
            case 3:
                int actionIdx4 = event.getActionIndex();
                int pointerId4 = event.getPointerId(actionIdx4);
                if (this.mTouches.containsKey(Integer.valueOf(pointerId4)) && (touch = this.mTouches.remove(Integer.valueOf(pointerId4))) != null) {
                    touch.UpdateFromMotionEvent(event, 4, actionIdx4);
                    EnqueueEvent(new UITouchEvent(touch));
                }
                break;
        }
        return true;
    }

    /** Desktop pointer movement without inventing a touch-down or holding a button. */
    public boolean HandleHoverEvent(MotionEvent event) {
        if (!this.mbAppHasFocus) return false;
        UITouchTracker hover = this.mMouseHoverTracker;
        // Native phase 5 is the desktop hover extension; it never enters mTouches.
        if (hover == null) {
            hover = new UITouchTracker();
            hover.InitializeFromMotionEvent(event, event.getPointerId(0), 5, 0);
            this.mMouseHoverTracker = hover;
        } else {
            hover.UpdateFromMotionEvent(event, 5, 0);
        }
        hover.mPointerId = event.getPointerId(0);
        EnqueueEvent(new UITouchEvent(hover));
        return true;
    }

    public boolean HandleKeyEvent(KeyEvent InEvent) {
        if (!this.mbAppHasFocus) {
            return false;
        }
        switch (InEvent.getKeyCode()) {
            case 4:
            case 7:
            case 8:
            case 9:
            case 10:
            case 11:
            case 12:
            case 13:
            case 14:
            case 15:
            case 16:
            case 17:
            case 18:
            case 29:
            case SegmentFinder.segment_sum /* 30 */:
            case 31:
            case 32:
            case 33:
            case 34:
            case 35:
            case 36:
            case 37:
            case 38:
            case 39:
            case 40:
            case 41:
            case 42:
            case 43:
            case 44:
            case 45:
            case 46:
            case 47:
            case 48:
            case 49:
            case 50:
            case 51:
            case 52:
            case 53:
            case 54:
            case 55:
            case 56:
            case 62:
            case 66:
            case 67:
            case 69:
            case 71:
            case 72:
            case 73:
            case 74:
            case 75:
            case 76:
            case 81:
                EnqueueEvent(new UIKeyEvent(InEvent));
                return true;
            case 5:
            case 6:
            case 19:
            case 20:
            case 21:
            case 22:
            case 23:
            case 24:
            case 25:
            case 26:
            case 27:
            case 28:
            case 57:
            case 58:
            case 59:
            case 60:
            case 61:
            case 63:
            case AccessibilityNodeInfoCompat.ACTION_ACCESSIBILITY_FOCUS /* 64 */:
            case 65:
            case 68:
            case 70:
            case 77:
            case 78:
            case 79:
            case 80:
            default:
                return false;
        }
    }

    /* JADX INFO: Access modifiers changed from: private */
    private double GetTimeStamp() {
        return System.nanoTime() / 1.0E9d;
    }

    private synchronized void EnqueueEvent(UIEvent event) {
        this.mEvents.addLast(event);
    }

    public boolean ProcessEvents(ByteBuffer outData) {
        int iEventCount = 0;
        if (outData == null) {
            return false;
        }
        outData.order(ByteOrder.LITTLE_ENDIAN);
        outData.rewind();
        outData.position(16);
        boolean bMoreResults = false;
        synchronized (this) {
            while (!this.mEvents.isEmpty()) {
                UIEvent evt = this.mEvents.peek();
                outData.mark();
                if (evt.Serialize(outData)) {
                    this.mEvents.remove();
                    iEventCount++;
                } else {
                    outData.reset();
                    bMoreResults = true;
                    break;
                }
            }
        }
        outData.putInt(0, iEventCount);
        return bMoreResults;
    }

    @Override // android.view.GestureDetector.OnGestureListener
    public boolean onDown(MotionEvent event) {
        return false;
    }

    @Override // android.view.GestureDetector.OnGestureListener
    public boolean onFling(MotionEvent e1, MotionEvent e2, float velocityX, float velocityY) {
        Log.d("AndroidUIEventManager", "Fling! VelX: " + velocityX + " VelY: " + velocityY);
        if (this.mbAppHasFocus) {
            EnqueueEvent(new UIFlickEvent((int) e1.getX(), (int) e1.getY(), velocityX, velocityY));
        }
        return false;
    }

    @Override // android.view.GestureDetector.OnGestureListener
    public void onLongPress(MotionEvent e) {
        Log.d("AndroidUIEventManager", "Long Press!");
        EnqueueEvent(new UILongPressEvent(e));
    }

    @Override // android.view.GestureDetector.OnGestureListener
    public boolean onScroll(MotionEvent e1, MotionEvent e2, float distanceX, float distanceY) {
        return false;
    }

    @Override // android.view.GestureDetector.OnGestureListener
    public void onShowPress(MotionEvent e) {
    }

    @Override // android.view.GestureDetector.OnGestureListener
    public boolean onSingleTapUp(MotionEvent e) {
        return false;
    }

    @Override // android.view.ScaleGestureDetector.OnScaleGestureListener
    public boolean onScale(ScaleGestureDetector detector) {
        if (!this.mbAppHasFocus) {
            return false;
        }
        Log.d("AndroidUIEventManager", "Scale!");
        this.endScale = detector.getScaleFactor();
        Log.d("AndroidUIEventManager", "StartCur: " + this.startScale + " EndPrev: " + this.endScale);
        if (this.startScale >= this.endScale) {
            float mag = this.startScale - this.endScale;
            if (mag < this.prevScaleMag || mag - this.prevScaleMag < SCALE_THRESHOLD) {
                return false;
            }
            Log.d("AndroidUIEventManager", "Pinch Detected!");
            this.prevScaleMag = mag;
            onPinch(detector);
        } else if (this.startScale < this.endScale) {
            float mag2 = this.startScale - this.endScale;
            if (mag2 > this.prevScaleMag || Math.abs(mag2 - this.prevScaleMag) < SCALE_THRESHOLD) {
                return false;
            }
            Log.d("AndroidUIEventManager", "Zoom detected!");
            this.prevScaleMag = mag2;
            onPinch(detector);
        }
        return true;
    }

    @Override // android.view.ScaleGestureDetector.OnScaleGestureListener
    public boolean onScaleBegin(ScaleGestureDetector detector) {
        if (!this.mbAppHasFocus) {
            return false;
        }
        Log.d("AndroidUIEventManager", "ScaleBegin!");
        this.startScale = detector.getScaleFactor();
        return true;
    }

    @Override // android.view.ScaleGestureDetector.OnScaleGestureListener
    public void onScaleEnd(ScaleGestureDetector detector) {
        Log.d("AndroidUIEventManager", "ScaleEnd!");
        this.prevScaleMag = 0.0f;
    }

    public void onZoom() {
    }

    public void onPinch(ScaleGestureDetector detector) {
        Log.d("AndroidUIEventManager", "Pinched!!");
        if (this.mTouches.size() >= 2) {
            float scaleDelta = this.endScale - this.startScale;
            UITouchTracker[] touches = (UITouchTracker[]) this.mTouches.values().toArray(new UITouchTracker[this.mTouches.size()]);
            UITouchTracker touch1 = touches[0];
            UITouchTracker touch2 = touches[1];
            float distX = touch1.X - touch2.X;
            float distY = touch1.Y - touch2.Y;
            float scaleDistSq = (distX * distX) + (distY * distY);
            int X = ((int) (touch1.X + touch2.X)) / 2;
            int Y = ((int) (touch1.Y + touch2.Y)) / 2;
            EnqueueEvent(new UIPinchEvent(X, Y, scaleDistSq, scaleDelta));
            Log.d("AndroidUIEventManager", "OnGesturePinch distX: " + distX + " DistY: " + distY + " centerX: " + X + " centerY: " + Y + " scaleDistSq: " + scaleDistSq + " scaleDelta: " + scaleDelta);
        }
    }

    public void onBackButtonPressed() {
        Log.d("AndroidUIEventManager", "Back Button pressed.");
        EnqueueEvent(new UIBackButtonEvent());
    }
}

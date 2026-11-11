#include <jni.h>
#include <astc-codec/astc-codec.h>

extern "C" JNIEXPORT jboolean JNICALL
Java_com_popcap_pvz2cthd_AsterRgbaPilot_decodeAstc(JNIEnv* env, jclass, jbyteArray input,
                                                 jint width, jint height, jobject output) {
    if (width <= 0 || width > 4096 || width % 4 || height <= 0 || height > 128 || height % 4)
        return JNI_FALSE;
    const auto size = env->GetArrayLength(input);
    auto* rgba = static_cast<uint8_t*>(env->GetDirectBufferAddress(output));
    if (size != width * height || !rgba || env->GetDirectBufferCapacity(output) < width * height * 4)
        return JNI_FALSE;
    auto* compressed = env->GetByteArrayElements(input, nullptr);
    if (!compressed)
        return JNI_FALSE;
    const bool ok = astc_codec::ASTCDecompressToRGBA(
        reinterpret_cast<const uint8_t*>(compressed), size, width, height,
        astc_codec::FootprintType::k4x4, rgba, width * height * 4, width * 4);
    env->ReleaseByteArrayElements(input, compressed, JNI_ABORT);
    return ok ? JNI_TRUE : JNI_FALSE;
}

# OkHttp trae sus propias reglas; esto solo silencia avisos de plataformas que no usa
-dontwarn org.bouncycastle.**
-dontwarn org.conscrypt.**
-dontwarn org.openjsse.**

# libtorrent4j: la parte nativa llama a estas clases por nombre (JNI y SWIG)
-keep class org.libtorrent4j.** { *; }

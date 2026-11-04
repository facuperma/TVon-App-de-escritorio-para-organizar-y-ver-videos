package io.github.facuperma.tvon

import android.content.Context
import android.media.MediaScannerConnection
import android.net.ConnectivityManager
import android.os.Build
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import org.libtorrent4j.Priority
import org.libtorrent4j.SessionManager
import org.libtorrent4j.TorrentFlags
import org.libtorrent4j.TorrentHandle
import org.libtorrent4j.TorrentInfo
import org.libtorrent4j.TorrentStatus
import java.io.File
import java.security.MessageDigest
import java.util.concurrent.TimeUnit
import java.util.zip.ZipInputStream

/**
 * El motor de torrent (libtorrent): la parte Java viene en la app, la nativa (≈ 6 MB) se baja de
 * Maven Central solo si el usuario activa los torrents. Se comprueba su huella SHA-256 antes de usarla.
 */
object MotorTorrent {
    private const val VERSION = "2.1.0-39"

    /** ABI de Android → (paquete de libtorrent4j, SHA-256 del .jar publicado en Maven Central). */
    private val PAQUETES = mapOf(
        "arm64-v8a" to ("libtorrent4j-android-arm64" to "59aa4c32c0dc62c95e24c2e3fdf805624625a1f8214e2442fae492e381ecbbdc"),
        "armeabi-v7a" to ("libtorrent4j-android-arm" to "914157778f514661aabe4d3e72451c1d3004401ce6659407ab7ce94a3f273fbc"),
        "x86_64" to ("libtorrent4j-android-x86_64" to "07ed97a0cbffbd8573a838e42549aa139b04d00ae2769eeef1a6a5402aba0cf3"),
        "x86" to ("libtorrent4j-android-x86" to "f25b3b60f3ad59c20e45adad0d161d3fc36d34dc32df33518b6330b79ac570bb"),
    )

    var cargado = false
        private set

    private fun abi(): String? = Build.SUPPORTED_ABIS.firstOrNull { it in PAQUETES }
    private fun archivo(contexto: Context) = File(contexto.filesDir, "motor/libtorrent4j-$VERSION.so")

    fun disponible(): Boolean = abi() != null
    fun instalado(contexto: Context): Boolean = archivo(contexto).isFile

    /** Tamaño aproximado de lo que se baja (para avisar antes). */
    const val TAMANO_APROX = 6L * 1024 * 1024

    /** Baja la parte nativa para este celular, comprueba la huella y la deja lista. */
    suspend fun instalar(contexto: Context, progreso: (Float) -> Unit) = withContext(Dispatchers.IO) {
        val abi = abi() ?: throw IllegalStateException("Este celular no es compatible con el motor de torrent")
        val (paquete, huella) = PAQUETES.getValue(abi)
        val url = "https://repo1.maven.org/maven2/org/libtorrent4j/$paquete/$VERSION/$paquete-$VERSION.jar"
        val red = OkHttpClient.Builder().readTimeout(60, TimeUnit.SECONDS).build()
        val datos = red.newCall(Request.Builder().url(url).build()).execute().use { r ->
            if (!r.isSuccessful) throw java.io.IOException("No se pudo bajar el motor (HTTP ${r.code})")
            val cuerpo = r.body!!
            val total = cuerpo.contentLength().takeIf { it > 0 } ?: TAMANO_APROX
            val salida = java.io.ByteArrayOutputStream(total.toInt())
            cuerpo.byteStream().use { e ->
                val buf = ByteArray(64 * 1024)
                while (true) {
                    val n = e.read(buf)
                    if (n < 0) break
                    salida.write(buf, 0, n)
                    progreso((salida.size().toFloat() / total).coerceAtMost(1f))
                }
            }
            salida.toByteArray()
        }
        val recibida = MessageDigest.getInstance("SHA-256").digest(datos).joinToString("") { "%02x".format(it) }
        if (recibida != huella) throw SecurityException("El motor que llegó no es el oficial (la huella no coincide): no se instala")
        val destino = archivo(contexto)
        destino.parentFile?.mkdirs()
        val temporal = File(destino.path + ".tmp")
        val so = ZipInputStream(datos.inputStream()).use { zip ->
            generateSequence { zip.nextEntry }.firstOrNull { it.name == "lib/$abi/libtorrent4j.so" }?.let { zip.readBytes() }
        } ?: throw IllegalStateException("El paquete del motor no trae la parte para este celular")
        temporal.writeBytes(so)
        temporal.setReadOnly() // Android 14 pide que el código cargado aparte no se pueda modificar
        if (!temporal.renameTo(destino)) throw java.io.IOException("No se pudo guardar el motor")
    }

    /** Hace que libtorrent4j use la parte nativa bajada. Devuelve false si no está o no carga. */
    fun cargar(contexto: Context): Boolean {
        if (cargado) return true
        val so = archivo(contexto)
        if (!so.isFile) return false
        System.setProperty("libtorrent4j.jni.path", so.path)
        cargado = try {
            org.libtorrent4j.LibTorrent.version()
            true
        } catch (e: Throwable) {
            false
        }
        return cargado
    }

    /** Lo borra (vuelve a ocupar 0 MB). Si ya estaba cargado, se termina de soltar al cerrar la app. */
    fun quitar(contexto: Context) {
        archivo(contexto).let { it.setWritable(true); it.delete() }
    }
}

data class TorrentLocal(
    val hash: String, val nombre: String, val progreso: Float, val bajado: Long, val total: Long,
    val velocidad: Int, val pares: Int, val estado: String, val pausado: Boolean,
)

/**
 * Los torrents del celular. Bajan a una carpeta privada de la app y, al terminar, la película y sus
 * subtítulos pasan a Películas/TorrentVision con un nombre lindo. No se queda compartiendo después.
 */
object Torrents {
    var lista by mutableStateOf<List<TorrentLocal>>(emptyList())
        private set
    var buscando by mutableStateOf(0) // links magnet esperando los datos del torrent
        private set

    private var sesion: SessionManager? = null
    private val pausadosPorUsuario = mutableSetOf<String>()
    private val hashes = mutableMapOf<String, org.libtorrent4j.Sha1Hash>()
    private var esperandoWifi = false

    private fun registros(contexto: Context) = File(contexto.filesDir, "torrents").apply { mkdirs() }
    // En la memoria interna privada (no pasa por el almacenamiento compartido de Android, que con muchas escrituras
    // chicas a la vez se puede caer); al terminar se copia a Películas/TorrentVision
    private fun descargas(contexto: Context) = File(contexto.filesDir, "bajando")

    fun hayAlgo(contexto: Context): Boolean =
        registros(contexto).listFiles { f -> f.extension == "torrent" }.orEmpty().isNotEmpty() || buscando > 0

    /** Arranca la sesión y retoma los torrents que quedaron a medias (libtorrent revisa lo ya bajado). */
    @Synchronized
    fun iniciar(contexto: Context): Boolean {
        sesion?.let { return true }
        if (!MotorTorrent.cargar(contexto)) return false
        val s = SessionManager(false)
        // Lectura y escritura comunes: el modo por defecto (mmap) hace caer el almacenamiento de Android (FUSE)
        s.start(org.libtorrent4j.SessionParams().apply { setPosixDiskIO() })
        sesion = s
        for (t in registros(contexto).listFiles { f -> f.extension == "torrent" }.orEmpty()) {
            try {
                val ti = TorrentInfo(t)
                val datos = JSONObject(File(t.path.removeSuffix(".torrent") + ".json").readText())
                val prioridades = prioridadesDe(ti, datos.optJSONArray("ignorar"))
                hashes[ti.infoHash().toHex()] = ti.infoHash()
                s.download(ti, File(descargas(contexto), ti.infoHash().toHex()), null, prioridades, null, TorrentFlags.AUTO_MANAGED)
            } catch (e: Exception) {
                // Un registro roto no frena a los demás
            }
        }
        return true
    }

    /**
     * Pide los datos del torrent al resto de la red (hasta 90 s), elige qué archivos bajar (sin extras),
     * comprueba el lugar libre y lo pone a bajar. Devuelve el aviso para mostrar.
     */
    suspend fun agregar(contexto: Context, magnet: String, libre: Long): String = withContext(Dispatchers.IO) {
        if (!iniciar(contexto)) return@withContext "El motor de torrent no está activado"
        val s = sesion!!
        buscando++
        val bytes = try {
            s.fetchMagnet(magnet, 90, registros(contexto))
        } finally {
            buscando--
        }
        bytes ?: return@withContext "No se encontró el torrent en la red (nadie lo comparte ahora o el link está mal). Probá más tarde."
        val ti = TorrentInfo.bdecode(bytes)
        val hash = ti.infoHash().toHex()
        if (File(registros(contexto), "$hash.torrent").exists()) return@withContext "Ese torrent ya está bajando"
        val fs = ti.files()
        val ignorar = (0 until fs.numFiles()).filter { i ->
            val ruta = fs.filePath(i)
            val ext = ruta.substringAfterLast('.', "").lowercase()
            fs.padFileAt(i) || when {
                ext in Videoteca.VIDEOS -> esExtra(ruta, fs.fileSize(i))
                ext in Videoteca.SUBTITULOS -> false
                else -> true // .nfo, .txt, imágenes, programas…: no hacen falta
            }
        }
        val prioridades = prioridadesDe(ti, org.json.JSONArray(ignorar))
        val peso = (0 until fs.numFiles()).filter { prioridades[it] != Priority.IGNORE }.sumOf { fs.fileSize(it) }
        if (peso == 0L) return@withContext "Ese torrent no trae ninguna película (solo extras u otros archivos)"
        // Al terminar, el archivo más grande está un rato en los dos lugares (mientras se copia)
        val mayor = (0 until fs.numFiles()).filter { prioridades[it] != Priority.IGNORE }.maxOf { fs.fileSize(it) }
        if (peso + mayor + Videoteca.MARGEN > libre) {
            return@withContext "No hay lugar: «${ti.name()}» necesita ${tamano(peso + mayor)} (${tamano(peso)} y un rato " +
                "más mientras se pasa a Películas) y quedan ${tamano(libre)} libres (TorrentVision deja 1 GB para el celular)."
        }
        File(registros(contexto), "$hash.torrent").writeBytes(bytes)
        File(registros(contexto), "$hash.json").writeText(JSONObject().put("ignorar", org.json.JSONArray(ignorar)).toString())
        hashes[hash] = ti.infoHash()
        s.download(ti, File(descargas(contexto), hash).apply { mkdirs() }, null, prioridades, null, TorrentFlags.AUTO_MANAGED)
        "Bajando «${ti.name()}» (${tamano(peso)})"
    }

    private fun prioridadesDe(ti: TorrentInfo, ignorar: org.json.JSONArray?): Array<Priority> {
        val fuera = (0 until (ignorar?.length() ?: 0)).map { ignorar!!.getInt(it) }.toSet()
        return Array(ti.numFiles()) { if (it in fuera) Priority.IGNORE else Priority.DEFAULT }
    }

    private fun handle(hash: String): TorrentHandle? =
        hashes[hash]?.let { sesion?.find(it) }?.takeIf { it.isValid }

    fun pausar(hash: String) {
        pausadosPorUsuario += hash
        handle(hash)?.let { it.unsetFlags(TorrentFlags.AUTO_MANAGED); it.pause() }
    }

    fun reanudar(hash: String) {
        pausadosPorUsuario -= hash
        handle(hash)?.let { it.setFlags(TorrentFlags.AUTO_MANAGED); it.resume() }
    }

    /** Lo saca y borra lo bajado a medias (nada de Películas/TorrentVision). */
    fun cancelar(contexto: Context, hash: String) {
        handle(hash)?.let { sesion?.remove(it) }
        olvidar(contexto, hash)
        File(descargas(contexto), hash).deleteRecursively()
    }

    private fun olvidar(contexto: Context, hash: String) {
        File(registros(contexto), "$hash.torrent").delete()
        File(registros(contexto), "$hash.json").delete()
        pausadosPorUsuario -= hash
        hashes -= hash
    }

    /**
     * Se llama cada segundo desde el servicio: pausa sin wifi (si así se eligió), pasa a la videoteca
     * los que terminaron y actualiza la lista. Devuelve los nombres de los que terminaron.
     */
    fun actualizar(contexto: Context, soloWifi: Boolean): List<String> {
        val s = sesion ?: return emptyList()
        val medido = contexto.getSystemService(ConnectivityManager::class.java)?.isActiveNetworkMetered ?: false
        val esperar = soloWifi && medido
        if (esperar != esperandoWifi) {
            esperandoWifi = esperar
            if (esperar) s.pause() else s.resume()
        }
        val terminados = mutableListOf<String>()
        val nueva = mutableListOf<TorrentLocal>()
        for (t in registros(contexto).listFiles { f -> f.extension == "torrent" }.orEmpty()) {
            val hash = t.nameWithoutExtension
            val h = handle(hash) ?: continue
            val st = h.status()
            if (st.isFinished && st.hasMetadata()) {
                s.remove(h)
                pasarALaVideoteca(contexto, File(descargas(contexto), hash))
                olvidar(contexto, hash)
                terminados += st.name()
                continue
            }
            val pausado = hash in pausadosPorUsuario
            nueva += TorrentLocal(
                hash, st.name(), st.progress(), st.totalWantedDone(), st.totalWanted(), st.downloadPayloadRate(),
                st.numPeers(),
                when {
                    pausado -> "En pausa"
                    esperandoWifi -> "Esperando wifi"
                    st.state() == TorrentStatus.State.CHECKING_FILES || st.state() == TorrentStatus.State.CHECKING_RESUME_DATA -> "Revisando lo ya bajado"
                    st.numPeers() == 0 -> "Buscando quién lo comparte…"
                    else -> "Bajando · ${tamano(st.downloadPayloadRate().toLong()).ifEmpty { "0 MB" }}/s · ${st.numPeers()} conexiones"
                },
                pausado,
            )
        }
        lista = nueva
        return terminados
    }

    /** Mueve los videos (con nombre lindo) y sus subtítulos a Películas/TorrentVision y borra la carpeta temporal. */
    private fun pasarALaVideoteca(contexto: Context, carpeta: File) {
        val destino = File(android.os.Environment.getExternalStoragePublicDirectory(android.os.Environment.DIRECTORY_MOVIES),
            Videoteca.CARPETA).apply { mkdirs() }
        val archivos = carpeta.walkTopDown().filter { it.isFile }.toList()
        val videos = archivos.filter { it.extension.lowercase() in Videoteca.VIDEOS && !esExtra(it.path, it.length()) }
        val subs = archivos.filter { it.extension.lowercase() in Videoteca.SUBTITULOS }
        val movidos = mutableListOf<String>()
        for (v in videos) {
            val base = libre(destino, nombreLindo(v.nameWithoutExtension), v.extension.lowercase())
            val nuevo = File(destino, "$base.${v.extension.lowercase()}")
            if (mover(v, nuevo)) movidos += nuevo.path
            // Sus subtítulos: los que empiezan con su nombre o, si hay un solo video, todos
            val propios = if (videos.size == 1) subs else subs.filter { it.name.startsWith(v.nameWithoutExtension) }
            propios.forEachIndexed { i, s ->
                val idioma = s.nameWithoutExtension.removePrefix(v.nameWithoutExtension).trim('.', ' ', '_', '-')
                    .takeIf { it.length in 1..12 && !it.contains(' ') }
                val nombre = listOfNotNull(base, idioma ?: if (i > 0) "$i" else null).joinToString(".") + "." + s.extension.lowercase()
                val ds = File(destino, nombre)
                if (!ds.exists() && mover(s, ds)) movidos += ds.path
            }
        }
        if (movidos.isNotEmpty()) MediaScannerConnection.scanFile(contexto, movidos.toTypedArray(), null, null)
        carpeta.deleteRecursively()
    }

    private fun libre(carpeta: File, base: String, ext: String): String {
        var nombre = base
        var n = 2
        while (File(carpeta, "$nombre.$ext").exists()) nombre = "$base ($n)".also { n++ }
        return nombre
    }

    private fun mover(de: File, a: File): Boolean =
        de.renameTo(a) || try {
            de.copyTo(a, overwrite = false)
            de.delete()
            true
        } catch (e: Exception) {
            false
        }

    // --- Nombres (como titulos.py de la PC) -----------------------------------------------------

    private val EXTRA = Regex("""(?i)\b(trailers?|teasers?|samples?|featurettes?|interviews?|entrevistas?|behind the scenes|making of|deleted scenes|extended scenes|escenas eliminadas|bonus|bloopers|gag reel)\b""")
    private val CARPETAS_EXTRA = setOf("extras", "extra", "featurettes", "featurette", "trailers", "trailer", "interviews",
        "entrevistas", "behind the scenes", "deleted scenes", "escenas eliminadas", "shorts", "cortos", "cortometrajes",
        "samples", "sample", "bonus", "bonus features", "special features", "making of")
    private val SUFIJO_EXTRA = Regex("""(?i)-(trailer|teaser|sample|featurette|interview|behindthescenes|deleted|scene|short)$""")
    private const val EXTRA_CHICO = 300L * 1024 * 1024

    /** Tráiler, muestra, entrevista… y no la película. Igual criterio que la PC (sin falsos positivos con títulos). */
    fun esExtra(ruta: String, tamano: Long): Boolean {
        val partes = ruta.replace('\\', '/').split('/')
        if (partes.dropLast(1).takeLast(3).any { it.replace(Regex("[._]+"), " ").trim().lowercase() in CARPETAS_EXTRA }) return true
        val nombre = partes.last().substringBeforeLast('.')
        if (SUFIJO_EXTRA.containsMatchIn(nombre)) return true
        val limpio = nombre.replace(Regex("[._]+"), " ")
        val titulo = nombreLindo(nombre).substringBefore(" (")
        val palabra = EXTRA.find(limpio) ?: return false
        if (palabra.range.first >= titulo.length) return true // la palabra va después del título
        return tamano < EXTRA_CHICO
    }

    private val CORTE = Regex("""(?i)\b((19|20)\d{2}|S\d{1,2}E\d{1,3}|\d{1,2}x\d{2}|2160p|1080p|720p|480p|4k|uhd|bluray|blu-ray|brrip|bdrip|web-?dl|webrip|hdtv|dvdrip|hdrip|x264|x265|h264|h265|hevc|10bit|remux|proper|repack)\b""")

    /** «The.Movie.2020.1080p.WEB-DL.x264-GRP» → «The Movie (2020)»; «Show.S01E02.720p» → «Show S01E02». */
    fun nombreLindo(original: String): String {
        val t = original.replace(Regex("[._]+"), " ").replace(Regex("""\[[^\]]*\]|\{[^}]*\}"""), " ")
        val corte = CORTE.findAll(t).firstOrNull { it.range.first > 0 }
        var titulo = (if (corte != null) t.substring(0, corte.range.first) else t).replace(Regex("""[\s\-–(]+$"""), "").trim()
        if (titulo.isEmpty()) titulo = t.trim()
        val episodio = Regex("""(?i)\bS(\d{1,2})E(\d{1,3})\b""").find(t)
        val anio = Regex("""\b(19|20)\d{2}\b""").findAll(t).firstOrNull { it.range.first > 0 }?.value
        if (titulo == titulo.lowercase() || titulo == titulo.uppercase()) {
            titulo = titulo.lowercase().split(' ').joinToString(" ") { it.replaceFirstChar(Char::uppercase) }
        }
        return Videoteca.nombreLindo(
            when {
                episodio != null -> "$titulo S%02dE%02d".format(episodio.groupValues[1].toInt(), episodio.groupValues[2].toInt())
                else -> titulo
            },
            if (episodio == null) anio else null,
        )
    }
}

package io.github.facuperma.tvon

import android.app.DownloadManager
import android.content.Context
import android.media.MediaScannerConnection
import android.net.Uri
import android.os.Environment
import android.os.StatFs
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.io.File
import java.util.concurrent.TimeUnit
import java.util.zip.ZipInputStream

/**
 * Modo «Usar celular como videoteca»: sin PC, el celular baja las películas a Películas/TorrentVision,
 * las guarda con sus subtítulos y las reproduce. La carpeta es la biblioteca: lo que hay ahí, se ve.
 */
class Videoteca(private val contexto: Context) {
    private val prefs = contexto.getSharedPreferences("videoteca", Context.MODE_PRIVATE)
    private val red = OkHttpClient.Builder().connectTimeout(20, TimeUnit.SECONDS).readTimeout(30, TimeUnit.SECONDS).build()
    private val gestor = contexto.getSystemService(DownloadManager::class.java)

    var activa by mutableStateOf(prefs.getBoolean("activa", false))
        private set
    var soloWifi by mutableStateOf(prefs.getBoolean("solo_wifi", true))
        private set
    var peliculas by mutableStateOf<List<PeliculaLocal>>(emptyList())
        private set
    var descargas by mutableStateOf<List<DescargaLocal>>(emptyList())
        private set
    var libre by mutableStateOf(0L)
        private set
    /** La película que se está viendo (null = la lista). */
    var viendo by mutableStateOf<PeliculaLocal?>(null)

    // Búsqueda en el Internet Archive (dominio público)
    var texto by mutableStateOf("")
    var orden by mutableStateOf("populares")
    var resultados by mutableStateOf<List<PeliculaArchive>>(emptyList())
    var total by mutableStateOf(0)
    var pagina = 1
    var mensaje by mutableStateOf<String?>(null)

    val carpeta: File get() = File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_MOVIES), CARPETA)

    fun activar() {
        carpeta.mkdirs()
        activa = true
        prefs.edit().putBoolean("activa", true).apply()
        refrescar()
    }

    /** Vuelve a la app conectada a la PC. Las películas quedan en la carpeta. */
    fun desactivar() {
        activa = false
        prefs.edit().putBoolean("activa", false).apply()
    }

    fun cambiarSoloWifi(valor: Boolean) {
        soloWifi = valor
        prefs.edit().putBoolean("solo_wifi", valor).apply()
    }

    /** Lugar libre donde se guardan las películas. */
    fun espacioLibre(): Long = try {
        StatFs((if (carpeta.exists()) carpeta else Environment.getExternalStorageDirectory()).path).availableBytes
    } catch (e: Exception) {
        0L
    }

    fun refrescar() {
        libre = espacioLibre()
        val archivos = carpeta.listFiles().orEmpty()
        val bajando = descargasPropias().map { it.archivo }.toSet()
        peliculas = archivos
            .filter { it.isFile && it.extension.lowercase() in VIDEOS && it.name !in bajando }
            .map { video ->
                val base = video.nameWithoutExtension
                val subs = archivos.filter { it.isFile && it.extension.lowercase() in SUBTITULOS && it.name.startsWith(base) }
                PeliculaLocal(video, subs.sortedBy { it.name }, prefs.getLong("pos:${video.name}", 0),
                    prefs.getLong("dur:${video.name}", 0), video.length())
            }
            .sortedByDescending { it.archivo.lastModified() }
        descargas = descargasPropias()
    }

    // --- Internet Archive ---------------------------------------------------------------------

    suspend fun buscar(nueva: Boolean) = withContext(Dispatchers.IO) {
        if (nueva) pagina = 1 else pagina++
        var consulta = CONSULTA_BASE
        val palabras = texto.replace(Regex("""[^\p{L}\p{N}\s]"""), " ").split(Regex("\\s+")).filter { it.isNotBlank() }
        if (palabras.isNotEmpty()) consulta += " AND title:(${palabras.joinToString(" ")})"
        if (orden.startsWith("anio")) consulta += " AND year:[1800 TO 2100]"
        val url = "https://archive.org/advancedsearch.php".toHttpUrl().newBuilder()
            .addQueryParameter("q", consulta)
            .apply { for (c in listOf("identifier", "title", "year", "downloads")) addQueryParameter("fl[]", c) }
            .addQueryParameter("sort[]", ORDENES.getValue(orden).second)
            .addQueryParameter("rows", "50").addQueryParameter("page", pagina.toString())
            .addQueryParameter("output", "json").build()
        try {
            val r = json(url.toString()).getJSONObject("response")
            val docs = r.getJSONArray("docs")
            val nuevas = (0 until docs.length()).map { i ->
                val d = docs.getJSONObject(i)
                PeliculaArchive(d.getString("identifier"), d.optString("title", d.getString("identifier")).trim(),
                    d.opt("year")?.toString()?.takeIf { it.isNotBlank() && it != "null" }, d.optLong("downloads"))
            }
            total = r.optInt("numFound")
            resultados = if (nueva) nuevas else resultados + nuevas
            mensaje = if (total == 0) "No se encontró nada con ese título" else null
        } catch (e: Exception) {
            mensaje = "No se pudo buscar en el Internet Archive: ¿hay internet?"
        }
    }

    /**
     * Pone en cola la película y sus subtítulos. Devuelve el aviso para mostrar.
     * Antes compara el tamaño con el lugar libre (deja 1 GB de margen para el celular).
     */
    suspend fun descargar(p: PeliculaArchive): String = withContext(Dispatchers.IO) {
        val datos = try {
            json("https://archive.org/metadata/" + Uri.encode(p.identificador))
        } catch (e: Exception) {
            return@withContext "No se pudo leer la película del Internet Archive: ¿hay internet?"
        }
        val archivos = datos.optJSONArray("files") ?: return@withContext "Esa película no tiene archivos"
        val todos = (0 until archivos.length()).map { archivos.getJSONObject(it) }
        val video = todos.filter { it.optString("format") in FORMATOS }
            .minWithOrNull(compareBy<JSONObject>({ FORMATOS.indexOf(it.optString("format")) }, { -it.optLong("size") }))
            ?: return@withContext "Esa película no tiene un video que se pueda bajar"
        val peso = video.optLong("size")
        carpeta.mkdirs()
        val libreAhora = espacioLibre()
        if (peso + MARGEN > libreAhora) {
            return@withContext "No hay lugar: la película ocupa ${tamano(peso)} y quedan ${tamano(libreAhora)} libres " +
                "(TorrentVision deja 1 GB para el celular). Borrá alguna película y probá de nuevo."
        }
        val nombre = nombreLindo(p.titulo, p.anio)
        val extension = video.getString("name").substringAfterLast('.', "mp4").lowercase()
        encolar(urlArchive(p.identificador, video.getString("name")), "$nombre.$extension", p.titulo)
        // Subtítulos del ítem: el primero queda con el mismo nombre que el video (así lo encuentra cualquier reproductor)
        todos.map { it.getString("name") }.filter { it.lowercase().endsWith(".srt") }.take(3).forEachIndexed { i, s ->
            encolar(urlArchive(p.identificador, s), if (i == 0) "$nombre.srt" else "$nombre.$i.srt", "Subtítulo de ${p.titulo}")
        }
        refrescar()
        "Bajando «${p.titulo}» (${tamano(peso)})" + if (soloWifi) " por wifi" else ""
    }

    private fun encolar(url: String, archivo: String, titulo: String) {
        val pedido = DownloadManager.Request(Uri.parse(url))
            .setTitle(titulo)
            .setDescription("TorrentVision · Películas/$CARPETA")
            .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
            .setDestinationInExternalPublicDir(Environment.DIRECTORY_MOVIES, "$CARPETA/$archivo")
            .setAllowedOverMetered(!soloWifi)
            .setAllowedOverRoaming(false)
        val id = gestor.enqueue(pedido)
        prefs.edit().putStringSet("descargas", ids() + id.toString()).apply()
    }

    private fun ids(): Set<String> = prefs.getStringSet("descargas", emptySet()).orEmpty()

    /** Las descargas de este modo que siguen en el gestor de Android (las terminadas se olvidan). */
    private fun descargasPropias(): List<DescargaLocal> {
        val ids = ids().mapNotNull { it.toLongOrNull() }
        if (ids.isEmpty()) return emptyList()
        val lista = mutableListOf<DescargaLocal>()
        val quedan = mutableSetOf<String>()
        gestor.query(DownloadManager.Query().setFilterById(*ids.toLongArray()))?.use { c ->
            while (c.moveToNext()) {
                val id = c.getLong(c.getColumnIndexOrThrow(DownloadManager.COLUMN_ID))
                val estado = c.getInt(c.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS))
                val ruta = c.getString(c.getColumnIndexOrThrow(DownloadManager.COLUMN_LOCAL_URI)).orEmpty()
                if (estado == DownloadManager.STATUS_SUCCESSFUL) {
                    Uri.parse(ruta).path?.let { MediaScannerConnection.scanFile(contexto, arrayOf(it), null, null) }
                    continue
                }
                quedan += id.toString()
                val motivo = c.getInt(c.getColumnIndexOrThrow(DownloadManager.COLUMN_REASON))
                lista += DescargaLocal(
                    id = id,
                    titulo = c.getString(c.getColumnIndexOrThrow(DownloadManager.COLUMN_TITLE)).orEmpty(),
                    archivo = Uri.parse(ruta).lastPathSegment?.substringAfterLast('/').orEmpty(),
                    bajado = c.getLong(c.getColumnIndexOrThrow(DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR)),
                    total = c.getLong(c.getColumnIndexOrThrow(DownloadManager.COLUMN_TOTAL_SIZE_BYTES)),
                    estado = when (estado) {
                        DownloadManager.STATUS_RUNNING -> "Bajando"
                        DownloadManager.STATUS_PENDING -> "En cola"
                        DownloadManager.STATUS_PAUSED -> when (motivo) {
                            DownloadManager.PAUSED_QUEUED_FOR_WIFI -> "Esperando wifi"
                            DownloadManager.PAUSED_WAITING_FOR_NETWORK -> "Esperando conexión"
                            else -> "En pausa (se retoma sola)"
                        }
                        else -> "Falló (código $motivo)"
                    },
                    fallo = estado == DownloadManager.STATUS_FAILED,
                )
            }
        }
        if (quedan != ids().toSet()) prefs.edit().putStringSet("descargas", quedan).apply()
        return lista
    }

    fun cancelar(d: DescargaLocal) {
        gestor.remove(d.id)
        refrescar()
    }

    /** Borra la película y sus subtítulos del celular. */
    fun borrar(p: PeliculaLocal) {
        (listOf(p.archivo) + p.subtitulos).forEach { it.delete() }
        prefs.edit().remove("pos:${p.archivo.name}").remove("dur:${p.archivo.name}").apply()
        MediaScannerConnection.scanFile(contexto, arrayOf(p.archivo.path), null, null)
        refrescar()
    }

    /** Un .srt/.vtt (o un .zip con uno adentro) elegido en el celular: queda junto a la película, con su nombre. */
    suspend fun agregarSubtitulo(p: PeliculaLocal, uri: Uri): String = withContext(Dispatchers.IO) {
        val nombreOrigen = uri.lastPathSegment.orEmpty().lowercase()
        val entrada = contexto.contentResolver.openInputStream(uri) ?: return@withContext "No se pudo abrir el archivo"
        val (bytes, extension) = entrada.use { e ->
            val datos = e.readBytes()
            if (datos.size >= 2 && datos[0] == 'P'.code.toByte() && datos[1] == 'K'.code.toByte()) {
                ZipInputStream(datos.inputStream()).use { zip ->
                    generateSequence { zip.nextEntry }.firstOrNull { it.name.substringAfterLast('.').lowercase() in SUBTITULOS }
                        ?.let { zip.readBytes() to it.name.substringAfterLast('.').lowercase() }
                } ?: return@withContext "El .zip no tiene ningún subtítulo (.srt o .vtt)"
            } else {
                datos to (if (nombreOrigen.endsWith(".vtt")) "vtt" else "srt")
            }
        }
        if (bytes.size > 5_000_000) return@withContext "Eso no parece un subtítulo (es muy grande)"
        val base = p.archivo.nameWithoutExtension
        var destino = File(carpeta, "$base.$extension")
        var n = 1
        while (destino.exists()) destino = File(carpeta, "$base.${n++}.$extension")
        destino.writeBytes(bytes)
        refrescar()
        "Subtítulo agregado a «${p.titulo}»"
    }

    // --- Dónde quedaste -----------------------------------------------------------------------

    fun guardarProgreso(p: PeliculaLocal, posicion: Long, duracion: Long) {
        prefs.edit().putLong("pos:${p.archivo.name}", posicion).putLong("dur:${p.archivo.name}", duracion).apply()
    }

    fun marcarVista(p: PeliculaLocal, vista: Boolean) {
        val dur = p.duracion.takeIf { it > 0 } ?: 1
        guardarProgreso(p, if (vista) dur else 0, dur)
        refrescar()
    }

    private fun json(url: String): JSONObject =
        red.newCall(Request.Builder().url(url).build()).execute().use { r ->
            if (!r.isSuccessful) throw java.io.IOException("HTTP ${r.code}")
            JSONObject(r.body!!.string())
        }

    companion object {
        const val CARPETA = "TorrentVision"
        const val MARGEN = 1L shl 30
        val VIDEOS = setOf("mp4", "m4v", "mkv", "webm", "avi", "mov", "ogv", "mpg", "mpeg", "ts")
        val SUBTITULOS = setOf("srt", "vtt")
        const val CONSULTA_BASE = "collection:feature_films AND mediatype:movies AND item_size:[100000000 TO 9999999999999]"
        // Como en la PC (archive.py): de mejor a peor
        val FORMATOS = listOf("h.264", "h.264 HD", "MPEG4", "512Kb MPEG4", "Matroska", "Ogg Video", "MPEG2")
        val ORDENES = linkedMapOf(
            "populares" to ("Más populares" to "downloads desc"),
            "titulo" to ("Título (A → Z)" to "titleSorter asc"),
            "anio_desc" to ("Año (más nuevas)" to "year desc"),
            "anio" to ("Año (más viejas)" to "year asc"),
        )

        fun urlArchive(identificador: String, nombre: String) =
            "https://archive.org/download/${Uri.encode(identificador)}/" + nombre.split('/').joinToString("/") { Uri.encode(it) }

        /** «Título (Año)» sin caracteres que el sistema de archivos no acepta. */
        fun nombreLindo(titulo: String, anio: String?): String {
            val limpio = titulo.replace(Regex("""[\\/:*?"<>|\p{Cntrl}]"""), " ").replace(Regex("\\s+"), " ").trim().take(90)
            return if (anio != null && anio !in limpio) "$limpio ($anio)" else limpio.ifEmpty { "Película" }
        }
    }
}

data class PeliculaArchive(val identificador: String, val titulo: String, val anio: String?, val descargas: Long)

data class PeliculaLocal(
    val archivo: File, val subtitulos: List<File>, val posicion: Long, val duracion: Long, val tamano: Long,
) {
    val titulo: String get() = archivo.nameWithoutExtension
    val vista: Boolean get() = duracion > 0 && posicion >= duracion * 0.92
    val empezada: Boolean get() = posicion > 60_000 && !vista
}

data class DescargaLocal(
    val id: Long, val titulo: String, val archivo: String, val bajado: Long, val total: Long, val estado: String,
    val fallo: Boolean,
)

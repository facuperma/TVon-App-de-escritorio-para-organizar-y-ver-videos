package io.github.facuperma.tvon

import android.net.Uri
import android.os.Build
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.Call
import okhttp3.ConnectionSpec
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.net.InetAddress
import java.security.MessageDigest
import java.security.cert.CertificateException
import java.security.cert.X509Certificate
import java.util.concurrent.TimeUnit
import javax.net.ssl.SSLContext
import javax.net.ssl.SSLHandshakeException
import javax.net.ssl.X509TrustManager

class ErrorApi(mensaje: String, val codigo: Int) : Exception(mensaje)

const val SIN_CONEXION = "No hay conexión con la PC. ¿TorrentVision está abierto y con ON encendido? " +
    "(Con «Arrancar TorrentVision con Windows» en la ventana ON, siempre queda listo)"
const val OTRO_CERTIFICADO = "La PC no presentó el certificado de TorrentVision que conoce este celular. " +
    "Si cambiaste de PC o reinstalaste TorrentVision, escaneá el código QR de nuevo. Si no, alguien podría " +
    "estar haciéndose pasar por tu PC: no sigas."
private const val CODIGO_CERTIFICADO = -1

/** El link del QR de TVon: https://IP:puerto/?c=código&h=huella del certificado. */
data class Enlace(val base: String, val codigo: String, val huella: String?) {
    companion object {
        fun leer(texto: String): Enlace? {
            val uri = try { Uri.parse(texto.trim()) } catch (e: Exception) { return null }
            if (uri.scheme != "https" || uri.port <= 0) return null
            val host = uri.host?.removePrefix("[")?.removeSuffix("]") ?: return null
            // Como en la PC: solo una IP (un nombre de dominio puede ser una página haciéndose pasar por TVon)
            if (host != "localhost" && !esIp(host)) return null
            // Y solo de la red de casa o de Tailscale: un link de internet no puede llevar la app a otro lado
            if (host != "localhost" && !esPrivada(host)) return null
            val codigo = uri.getQueryParameter("c")?.takeIf { it.isNotBlank() } ?: return null
            val huella = uri.getQueryParameter("h")?.uppercase()?.takeIf { it.matches(Regex("[0-9A-F]{64}")) }
            return Enlace("https://${uri.encodedAuthority}", codigo, huella)
        }

        /** 10.x, 172.16-31.x, 192.168.x, 100.64-127.x (Tailscale), fd.. (IPv6 local) o localhost. */
        fun esPrivada(host: String): Boolean = try {
            val ip = InetAddress.getByName(host)
            val b = ip.address.map { it.toInt() and 0xFF }
            ip.isLoopbackAddress || ip.isSiteLocalAddress || ip.isLinkLocalAddress ||
                (b.size == 4 && b[0] == 100 && b[1] in 64..127) ||
                (b.size == 16 && (b[0] and 0xFE) == 0xFC)
        } catch (e: Exception) {
            false
        }

        private fun esIp(host: String): Boolean {
            val ipv4 = Regex("""\d{1,3}(\.\d{1,3}){3}""")
            if (!ipv4.matches(host) && !host.contains(':')) return false
            // Con un literal, getByName no consulta DNS
            return try { InetAddress.getByName(host); true } catch (e: Exception) { false }
        }
    }
}

fun huellaLinda(hex: String) = hex.chunked(2).joinToString(":")

/** Los 6 números que tienen que coincidir con los del cartel de la PC (salen de su certificado y del pedido). */
fun codigoVinculo(huella: String, id: String): String {
    val hex = MessageDigest.getInstance("SHA-256").digest((huella.replace(":", "").uppercase() + id).toByteArray())
        .joinToString("") { "%02x".format(it) }
    val n = hex.substring(0, 8).toLong(16) % 1_000_000
    return "%03d %03d".format(n / 1000, n % 1000)
}

private fun sha256(datos: ByteArray): String =
    MessageDigest.getInstance("SHA-256").digest(datos).joinToString("") { "%02X".format(it) }

/** Acepta solo el certificado cuya huella SHA-256 conocemos (la que vino en el QR). */
private class CertificadoFijo(private val huella: String) : X509TrustManager {
    override fun checkServerTrusted(cadena: Array<out X509Certificate>, tipo: String) {
        val recibida = sha256(cadena.firstOrNull()?.encoded ?: throw CertificateException("Sin certificado"))
        if (!MessageDigest.isEqual(recibida.toByteArray(), huella.toByteArray())) {
            throw CertificateException("Certificado desconocido")
        }
    }

    override fun checkClientTrusted(cadena: Array<out X509Certificate>, tipo: String) =
        throw CertificateException("No se usa")

    override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()
}

/** Solo anota el certificado que presenta la PC y corta el saludo: no se manda ningún dato. */
private class SoloMirar : X509TrustManager {
    var huella: String? = null
    override fun checkServerTrusted(cadena: Array<out X509Certificate>, tipo: String) {
        huella = cadena.firstOrNull()?.encoded?.let(::sha256)
        throw CertificateException("Solo mirar")
    }

    override fun checkClientTrusted(cadena: Array<out X509Certificate>, tipo: String) =
        throw CertificateException("No se usa")

    override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()
}

private fun cliente(confianza: X509TrustManager, lectura: Long = 20): OkHttpClient {
    val tls = SSLContext.getInstance("TLS").apply { init(null, arrayOf(confianza), null) }
    return OkHttpClient.Builder()
        .sslSocketFactory(tls.socketFactory, confianza)
        // La identidad de la PC la prueba la huella fija, no el nombre: la IP de la casa puede cambiar
        .hostnameVerifier { _, _ -> true }
        .connectionSpecs(listOf(ConnectionSpec.MODERN_TLS))
        .followRedirects(false)
        .followSslRedirects(false)
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(lectura, TimeUnit.SECONDS)
        .build()
}

// La PC arma el nombre del celular con esto: «Android · SM-A546E»
val AGENTE = "TVonON/${BuildConfig.VERSION_NAME} (Linux; Android ${Build.VERSION.RELEASE}; ${Build.MODEL})"

/** La huella del certificado que presenta la PC en esa dirección (para un QR viejo, sin huella). */
suspend fun mirarHuella(base: String): String = withContext(Dispatchers.IO) {
    val mirar = SoloMirar()
    try {
        cliente(mirar).newCall(Request.Builder().url("$base/").head().build()).execute().close()
    } catch (e: IOException) {
        // esperado: el saludo se corta a propósito
    }
    mirar.huella ?: throw ErrorApi(SIN_CONEXION, 0)
}

/** Habla con el servidor de ON de una PC, con su certificado fijo y la sesión de este celular. */
class Pc(val base: String, val huella: String, @Volatile var token: String?) {
    private val http = cliente(CertificadoFijo(huella))
    /** Para la transmisión de la pantalla: cada cuadro llega en menos de un segundo. */
    val httpLargo: OkHttpClient = http.newBuilder().readTimeout(15, TimeUnit.SECONDS).build()

    /** Para el reproductor: el mismo certificado fijo, con más paciencia (el video se pide por partes). */
    val httpVideo: OkHttpClient = http.newBuilder().readTimeout(60, TimeUnit.SECONDS).build()

    /** Lo que el reproductor manda en cada pedido: la sesión de este celular. */
    fun cabeceras(): Map<String, String> =
        mapOf("User-Agent" to AGENTE) + (token?.let { mapOf("Cookie" to "tvon_sesion=$it") } ?: emptyMap())

    fun url(ruta: String) = base + ruta

    private fun pedido(ruta: String) = Request.Builder().url(base + ruta)
        .header("User-Agent", AGENTE)
        .header("Cache-Control", "no-store")
        .apply { token?.let { header("Cookie", "tvon_sesion=$it") } }

    private fun enviar(cliente: OkHttpClient, req: Request): Response = ejecutar(cliente.newCall(req))

    /** Una transmisión larga (la pantalla): se corta con `cancel()` desde otro hilo. */
    fun llamada(ruta: String): Call = httpLargo.newCall(pedido(ruta).build())

    fun ejecutar(llamada: Call): Response {
        val r = try {
            llamada.execute()
        } catch (e: SSLHandshakeException) {
            throw if (e.causas().any { it is CertificateException }) ErrorApi(OTRO_CERTIFICADO, CODIGO_CERTIFICADO)
            else ErrorApi(SIN_CONEXION, 0)
        } catch (e: IOException) {
            throw ErrorApi(SIN_CONEXION, 0)
        }
        if (r.isSuccessful) return r
        val texto = r.use { it.body?.string().orEmpty() }
        val mensaje = try { JSONObject(texto).optString("error") } catch (e: Exception) { "" }
        throw ErrorApi(mensaje.ifBlank { "Error ${r.code}" }, r.code)
    }

    suspend fun get(ruta: String): Any? = withContext(Dispatchers.IO) {
        enviar(http, pedido(ruta).build()).use { leerJson(it) }
    }

    suspend fun obj(ruta: String): JSONObject = get(ruta) as? JSONObject ?: JSONObject()
    suspend fun lista(ruta: String): JSONArray = get(ruta) as? JSONArray ?: JSONArray()

    suspend fun post(ruta: String, cuerpo: JSONObject): JSONObject? = withContext(Dispatchers.IO) {
        val req = pedido(ruta)
            // Cabecera propia: la PC la exige en toda orden (protección contra CSRF)
            .header("X-TVon", "1")
            .post(cuerpo.toString().toRequestBody(JSON))
            .build()
        enviar(http, req).use { leerJson(it) as? JSONObject }
    }

    /** Una imagen (cuadro del video, miniatura); null si no hay. */
    suspend fun bytes(ruta: String): ByteArray? = withContext(Dispatchers.IO) {
        enviar(http, pedido(ruta).build()).use { r ->
            try { if (r.code == 204) null else r.body?.bytes() } catch (e: IOException) { throw ErrorApi(SIN_CONEXION, 0) }
        }
    }

    /** Vincular sin QR: le pide permiso a la PC (aparece un cartel allá). Devuelve el id del pedido. */
    suspend fun solicitar(nombre: String): String = withContext(Dispatchers.IO) {
        val req = pedido("/api/solicitar")
            .header("X-TVon", "1")
            .post(JSONObject().put("nombre", nombre).toString().toRequestBody(JSON))
            .build()
        enviar(http, req).use { r ->
            (leerJson(r) as? JSONObject)?.optString("id")?.takeIf { it.isNotEmpty() }
                ?: throw ErrorApi("La PC no aceptó el pedido", r.code)
        }
    }

    /** («pendiente» | «aprobada» | «rechazada» | «vencida», sesión si se aprobó). */
    suspend fun estadoSolicitud(id: String): Pair<String, String?> = withContext(Dispatchers.IO) {
        enviar(http, pedido("/api/solicitud?id=" + Uri.encode(id)).build()).use { r ->
            val token = r.headers("Set-Cookie").firstNotNullOfOrNull { Regex("""tvon_sesion=([^;]+)""").find(it)?.groupValues?.get(1) }
            ((leerJson(r) as? JSONObject)?.optString("estado") ?: "vencida") to token
        }
    }

    /** Canjea el código del QR por una sesión propia de este celular. */
    suspend fun emparejar(codigo: String): String = withContext(Dispatchers.IO) {
        val req = pedido("/api/emparejar")
            .header("X-TVon", "1")
            .post(JSONObject().put("codigo", codigo).toString().toRequestBody(JSON))
            .build()
        enviar(http, req).use { r ->
            r.headers("Set-Cookie").firstNotNullOfOrNull { Regex("""tvon_sesion=([^;]+)""").find(it)?.groupValues?.get(1) }
                ?: throw ErrorApi("La PC no devolvió una sesión", 500)
        }
    }

    private fun leerJson(r: Response): Any? {
        if (r.code == 204) return null
        val texto = try { r.body?.string().orEmpty().trim() } catch (e: IOException) { throw ErrorApi(SIN_CONEXION, 0) }
        if (texto.isEmpty()) return null
        return try {
            if (texto.startsWith("[")) JSONArray(texto) else JSONObject(texto)
        } catch (e: org.json.JSONException) {
            throw ErrorApi("La PC mandó una respuesta que no se entiende", 502)
        }
    }

    private fun Throwable.causas(): Sequence<Throwable> = generateSequence(this) { it.cause }

    companion object {
        val JSON = "application/json".toMediaType()
        fun esCertificado(e: Throwable) = e is ErrorApi && e.codigo == CODIGO_CERTIFICADO
    }
}

/**
 * Si la IP de la PC cambió (el router le dio otra), se la busca en la wifi: se pregunta «TVON?» por
 * difusión UDP y cada TVon con ON encendido contesta su puerto y la huella de su certificado.
 * Devuelve las direcciones (https://ip:puerto) que contestaron con una de las huellas conocidas.
 * Contestar no prueba nada: después la conexión igual exige ese mismo certificado.
 */
suspend fun descubrirPcs(huellas: Set<String>, puerto: Int = 8765, esperaMs: Int = 1500): Map<String, String> =
    withContext(Dispatchers.IO) {
        val encontradas = mutableMapOf<String, String>()
        try {
            java.net.DatagramSocket().use { s ->
                s.broadcast = true
                s.soTimeout = 300
                val pregunta = "TVON?".toByteArray()
                s.send(java.net.DatagramPacket(pregunta, pregunta.size, InetAddress.getByName("255.255.255.255"), puerto))
                val buffer = ByteArray(512)
                val fin = System.currentTimeMillis() + esperaMs
                while (System.currentTimeMillis() < fin) {
                    val paquete = java.net.DatagramPacket(buffer, buffer.size)
                    try {
                        s.receive(paquete)
                    } catch (e: java.net.SocketTimeoutException) {
                        continue
                    }
                    try {
                        val o = JSONObject(String(paquete.data, 0, paquete.length))
                        val huella = o.getString("huella").uppercase()
                        val p = o.getInt("puerto")
                        val ip = paquete.address.hostAddress ?: continue
                        // Sin huellas conocidas (vincular sin QR) vale cualquiera: después se compara el código
                        if ((huellas.isEmpty() || huella in huellas) && p in 1..65535 && !ip.contains(':')) {
                            encontradas["https://$ip:$p"] = huella
                        }
                    } catch (e: Exception) {
                        // una respuesta que no es de TVon
                    }
                }
            }
        } catch (e: IOException) {
            // sin wifi: no hay a quién preguntar
        }
        encontradas
    }

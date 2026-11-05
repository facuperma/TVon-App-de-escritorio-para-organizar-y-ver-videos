package io.github.facuperma.tvon

import android.app.Application
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.provider.OpenableColumns
import android.util.Base64
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.Call
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException

/** Las pestañas de abajo. Pantalla no tiene botón propio: se entra desde Mouse. */
enum class Pestana(val icono: String, val texto: String, val enBarra: Boolean = true) {
    INICIO("🏠", "Inicio"), REPRODUCTOR("▶", "Control"), BIBLIOTECA("📚", "Biblioteca"), PELICULAS("➕", "Agregar"),
    MOUSE("🖱", "Mouse"), PANTALLA("🖥", "Pantalla", enBarra = false), MAS("⋯", "Más"),
}

sealed interface Fase {
    data object Cargando : Fase
    /** Sin nada vinculado: escanear el QR de la PC o entrar a la app (videoteca del celular). */
    data object Bienvenida : Fase
    data class Emparejar(val mensaje: String? = null) : Fase
    data class SinConexion(val mensaje: String) : Fase
    data object Lista : Fase
    /** Sin PC: el celular baja, guarda y reproduce las películas. */
    data object Videoteca : Fase
}

/** Una opción de la hoja de acciones (abajo). */
data class Opcion(
    val texto: String, val marca: String = "", val peligro: Boolean = false, val confirmar: String? = null,
    val hacer: suspend () -> Unit,
)

data class Hoja(val titulo: String, val opciones: List<Opcion>)
data class Confirmar(val texto: String, val si: String = "Sí", val hacer: suspend () -> Unit)
data class PedirTexto(val titulo: String, val inicial: String = "", val hacer: suspend (String) -> Unit)
data class Aviso(val texto: String, val malo: Boolean, val id: Long = System.nanoTime())
data class HuellaPorConfirmar(val enlace: Enlace, val huella: String)

data class Calidad(val texto: String, val ancho: Int, val calidad: Int, val fps: Int)

val CALIDADES = listOf(
    Calidad("Fluida (25 fps)", 960, 50, 25),
    Calidad("Normal (15 fps)", 1280, 60, 15),
    Calidad("Nítida (10 fps)", 1920, 75, 10),
)

/** Arma el JSON de una orden; las listas pasan a arreglos. */
private const val SUBTITULO_MAX = 3L * 1024 * 1024

fun json(vararg pares: Pair<String, Any?>): JSONObject = JSONObject().apply {
    for ((k, v) in pares) put(k, if (v is Collection<*>) JSONArray(v) else v ?: JSONObject.NULL)
}

class Modelo(app: Application) : AndroidViewModel(app) {
    val almacen = Almacen(app)
    val videoteca = Videoteca(app)
    private val prefsApariencia = app.getSharedPreferences("apariencia", android.content.Context.MODE_PRIVATE)
    /** ⚙ Apariencia abierta (la galería de temas). */
    var apariencia by mutableStateOf(false)
    private var pc: Pc? = null

    var fase by mutableStateOf<Fase>(Fase.Cargando)
    var pestana by mutableStateOf(Pestana.INICIO)
        private set
    var conectado by mutableStateOf(true)
    var enPrimerPlano = true
    val base get() = pc?.base.orEmpty()
    val huella get() = pc?.huella.orEmpty()

    // Ventanitas
    var hoja by mutableStateOf<Hoja?>(null)
    var confirmar by mutableStateOf<Confirmar?>(null)
    var pedirTexto by mutableStateOf<PedirTexto?>(null)
    var aviso by mutableStateOf<Aviso?>(null)
    var huellaPorConfirmar by mutableStateOf<HuellaPorConfirmar?>(null)
    var emparejando by mutableStateOf(false)
    /** Vincular sin QR en curso: el código que tiene que coincidir con el de la PC y qué está pasando. */
    var vinculo by mutableStateOf<Vinculo?>(null)
    private var trabajoVinculo: kotlinx.coroutines.Job? = null

    // Reproductor
    var estado by mutableStateOf<Estado?>(null)
    /** Sube cada vez que un clic deja el foco en un campo de texto de la PC: abre el teclado del celular. */
    var pedirTeclado by mutableIntStateOf(0)

    // Biblioteca
    var biblioteca by mutableStateOf<Biblioteca?>(null)
    var archivos by mutableStateOf<List<ArchivoBib>>(emptyList())
    var filtro by mutableStateOf("todos")
    var categoria by mutableStateOf<Int?>(null)
    var busqueda by mutableStateOf("")
    var seleccion by mutableStateOf<Set<Int>>(emptySet())
    var eligiendo by mutableStateOf(false)
    var favAbiertos by mutableStateOf<Set<Int>>(emptySet())
    var mostrar by mutableStateOf(almacen.mostrar)
        private set

    /** Los archivos de la lista según «Mostrar»: sin ver (también los que quedaron a medias), vistos o todos. */
    val archivosVisibles: List<ArchivoBib>
        get() = when (mostrar) {
            "sin_ver" -> archivos.filter { it.visto != "✓" }
            "vistos" -> archivos.filter { it.visto == "✓" }
            else -> archivos
        }

    fun elegirMostrar(m: String) {
        mostrar = m
        almacen.mostrar = m
        seleccion = seleccion.intersect(archivosVisibles.map { it.id }.toSet())
    }

    // Películas
    var peliculas by mutableStateOf<List<Pelicula>>(emptyList())
    var peliculasTotal by mutableStateOf(0)
    var peliculasTexto by mutableStateOf("")
    var peliculasMensaje by mutableStateOf<String?>(null)
    var orden by mutableStateOf("populares")
    var ordenes by mutableStateOf<List<Pair<String, String>>>(emptyList())
    private var paginaPeliculas = 1
    private var qPeliculas = ""
    var descargas by mutableStateOf<Descargas?>(null)
    var torrents by mutableStateOf<List<Torrent>>(emptyList())
    var enlaceTorrent by mutableStateOf("")

    // Inicio: ver las películas y series de la PC (como Jellyfin)
    var inicio by mutableStateOf<Inicio?>(null)
    /** Por qué no se pudo cargar el inicio (se reintenta solo). */
    var inicioError by mutableStateOf<String?>(null)
    var catalogo by mutableStateOf<List<Cartel>>(emptyList())
    var catalogoTipo by mutableStateOf("pelicula")
    var catalogoGenero by mutableStateOf("")
    var catalogoOrden by mutableStateOf("recientes")
    var catalogoTexto by mutableStateOf("")
    /** Lo que se abrió encima de la pestaña: la serie, después el capítulo… (atrás vuelve de a uno). */
    var detalles by mutableStateOf<List<Detalle>>(emptyList())
    var viendoAca by mutableStateOf<VerEnCelular?>(null)
        private set

    // Mouse y pantalla
    var monitores by mutableStateOf<Monitores?>(null)
    var errorControl by mutableStateOf<String?>(null)
    var monitor by mutableStateOf(0)
    var viendo by mutableStateOf(false)
    var pantallaPC by mutableStateOf<ImageBitmap?>(null)
    var errorPantalla by mutableStateOf<String?>(null)
    var pantallaCompleta by mutableStateOf(false)
    var mantenido by mutableStateOf(false)

    init {
        io.github.facuperma.tvon.ui.C.tema = io.github.facuperma.tvon.ui.temaPorId(prefsApariencia.getString("tema", null))
        io.github.facuperma.tvon.ui.C.animada = prefsApariencia.getBoolean("animada", true)
        correr { conectar() }
        viewModelScope.launch { latido() }
    }

    // --- Conexión ---------------------------------------------------------------------------------

    /** Prueba las conexiones guardadas (la de casa, la de Tailscale…), la última que anduvo primero. */
    private var conectando = false

    suspend fun conectar() {
        // Probar varias direcciones tarda: si ya se está probando, no se encima otro intento
        if (conectando) return
        conectando = true
        try {
            probarConexiones()
        } finally {
            conectando = false
        }
    }

    private suspend fun probarConexiones() {
        if (videoteca.activa) {
            fase = Fase.Videoteca
            return
        }
        val guardadas = almacen.conexiones()
        if (guardadas.isEmpty()) {
            // Si ya está en Emparejar (p. ej. volvió del lector de QR) se queda ahí
            if (fase !is Fase.Emparejar) fase = Fase.Bienvenida
            return
        }
        var mensaje = SIN_CONEXION
        for (c in guardadas) {
            val prueba = Pc(c.base, c.huella, c.token)
            try {
                val e = Estado.de(prueba.obj("/api/estado"))
                pc = prueba
                almacen.preferir(c)
                estado = e
                conectado = true
                if (fase != Fase.Lista) {
                    fase = Fase.Lista
                    alCambiarDePestana()
                }
                return
            } catch (e: ErrorApi) {
                when {
                    e.codigo == 401 -> almacen.quitar(c.base) // la PC la desconectó
                    Pc.esCertificado(e) -> mensaje = OTRO_CERTIFICADO
                }
            }
        }
        if (mensaje != OTRO_CERTIFICADO && reencontrar()) return
        if (almacen.conexiones().isEmpty()) {
            fase = Fase.Emparejar("Este celular ya no está conectado a TorrentVision: escaneá el código QR de nuevo (botón 📱 ON en la PC).")
        } else if (fase != Fase.Lista || mensaje == OTRO_CERTIFICADO) {
            fase = Fase.SinConexion(mensaje)
        } else {
            conectado = false
        }
    }

    /**
     * La PC vinculada no contesta en su dirección de siempre: quizá el router le dio otra IP o TVon
     * abrió otro puerto. Se la busca en la wifi y, si aparece con el mismo certificado, se sigue con
     * la misma sesión en la dirección nueva (sin volver a escanear el QR).
     */
    private suspend fun reencontrar(): Boolean {
        val guardadas = almacen.conexiones()
        if (guardadas.isEmpty()) return false
        for ((base, huella) in descubrirPcs(guardadas.map { it.huella }.toSet())) {
            if (guardadas.any { it.base == base }) continue // esa ya se probó
            for (c in guardadas.filter { it.huella == huella }) {
                val prueba = Pc(base, huella, c.token)
                try {
                    val e = Estado.de(prueba.obj("/api/estado"))
                    almacen.quitar(c.base)
                    almacen.guardar(Conexion(base, huella, c.token))
                    pc = prueba
                    estado = e
                    conectado = true
                    if (fase != Fase.Lista) {
                        fase = Fase.Lista
                        alCambiarDePestana()
                    }
                    return true
                } catch (e: ErrorApi) {
                    // esa sesión es de otra dirección (la de Tailscale, por ejemplo): se prueba la siguiente
                }
            }
        }
        return false
    }

    private var fallos = 0

    /** Errores de la API: sin sesión vuelve a emparejar; sin red se marca la conexión caída. */
    private fun manejar(e: ErrorApi, avisar: Boolean) {
        when {
            e.codigo == 401 -> {
                pc?.let { almacen.quitar(it.base) }
                viewModelScope.launch { conectar() }
            }
            Pc.esCertificado(e) -> fase = Fase.SinConexion(OTRO_CERTIFICADO)
            e.codigo == 0 -> {
                conectado = false
                // Fuera de casa la IP de la wifi no responde: se prueba la otra conexión (Tailscale)
                if (++fallos >= 3) {
                    fallos = 0
                    viewModelScope.launch { conectar() }
                }
                if (avisar) mostrarAviso(e.message.orEmpty(), true)
            }
            avisar -> mostrarAviso(e.message.orEmpty(), true)
        }
    }

    private suspend fun latido() {
        var tic = 0
        while (viewModelScope.isActive) {
            delay(1000)
            tic++
            if (!enPrimerPlano) continue
            when (fase) {
                is Fase.SinConexion -> if (tic % 3 == 0) correr { conectar() }
                Fase.Videoteca -> if (tic % 2 == 0) videoteca.refrescar()
                Fase.Lista -> {
                    val e = estado
                    if (pestana == Pestana.REPRODUCTOR || e?.apagadoSegundos != null || e?.siguiente != null || tic % 3 == 0) {
                        correr { refrescarEstado() }
                    }
                    if (pestana == Pestana.PELICULAS && tic % 2 == 0) {
                        correr { cargarDescargas() }
                        correr { cargarTorrents() }
                    }
                    // Si el primer pedido falló (wifi que se cortó, TVon ocupado…), el inicio se vuelve a pedir
                    if (pestana == Pestana.INICIO && inicio == null && tic % 3 == 0) {
                        correr {
                            cargarInicio()
                            cargarCatalogo()
                        }
                    }
                }
                else -> {}
            }
        }
    }

    fun irA(p: Pestana) {
        if (pestana == Pestana.PANTALLA && p != Pestana.PANTALLA) dejarDeVer()
        if (p != Pestana.MOUSE) mantenerClic(false)
        pestana = p
        alCambiarDePestana()
    }

    private fun alCambiarDePestana() {
        when (pestana) {
            Pestana.INICIO -> correr {
                cargarInicio()
                cargarCatalogo()
            }
            Pestana.BIBLIOTECA -> correr { cargarBiblioteca() }
            Pestana.PELICULAS -> correr {
                if (peliculas.isEmpty()) buscarPeliculas(1)
                cargarDescargas()
                cargarTorrents()
            }
            Pestana.MOUSE, Pestana.PANTALLA -> correr { cargarMonitores() }
            else -> {}
        }
        correr { refrescarEstado() }
    }

    fun elegirTema(t: io.github.facuperma.tvon.ui.TemaCel) {
        io.github.facuperma.tvon.ui.C.tema = t
        prefsApariencia.edit().putString("tema", t.id).apply()
    }

    fun elegirAnimadas(si: Boolean) {
        io.github.facuperma.tvon.ui.C.animada = si
        prefsApariencia.edit().putBoolean("animada", si).apply()
    }

    /** El botón rojo: el celular pasa a ser la videoteca (sin PC). */
    fun usarVideoteca() {
        dejarDeVer()
        viendoAca?.jugador?.pause()
        videoteca.activar()
        fase = Fase.Videoteca
    }

    /** Un link magnet para bajar en el celular (modo videoteca). */
    fun bajarTorrentAca(magnet: String) {
        val app = getApplication<Application>()
        ServicioTorrents.iniciar(app)
        correr {
            val aviso = Torrents.agregar(app, magnet, videoteca.espacioLibre())
            mostrarAviso(aviso, !aviso.startsWith("Bajando"))
        }
    }

    /** Volver a manejar la PC: las películas del celular quedan en su carpeta. */
    fun irAEmparejar() {
        fase = Fase.Emparejar()
    }

    /** Atrás desde Emparejar: a la bienvenida si no hay PC guardada; si hay, se intenta conectar. */
    fun volverABienvenida() {
        if (almacen.conexiones().isEmpty()) {
            fase = Fase.Bienvenida
        } else {
            fase = Fase.Cargando
            correr { conectar() }
        }
    }

    fun dejarVideoteca() {
        videoteca.desactivar()
        fase = if (almacen.conexiones().isEmpty()) Fase.Emparejar() else Fase.Cargando
        correr { conectar() }
    }

    fun alVolver() {
        enPrimerPlano = true
        correr { if (fase == Fase.Lista) refrescarEstado() else conectar() }
    }

    fun alIrse() {
        enPrimerPlano = false
        dejarDeVer()
        mantenerClic(false)
        // El video del celular se pausa (y la PC guarda por dónde iba)
        viendoAca?.jugador?.pause()
    }

    // --- Emparejar ----------------------------------------------------------------------------------

    fun usarEnlace(texto: String) {
        val enlace = Enlace.leer(texto)
        if (enlace == null) {
            mostrarAviso("Ese no es un código de TorrentVision. En la PC tocá 📱 ON y escaneá el QR que aparece.", true)
            return
        }
        if (enlace.huella != null) return emparejarCon(enlace, enlace.huella)
        // QR de un TVon más viejo, sin la huella: se muestra para compararla con la de la PC
        viewModelScope.launch {
            emparejando = true
            try {
                huellaPorConfirmar = HuellaPorConfirmar(enlace, mirarHuella(enlace.base))
            } catch (e: ErrorApi) {
                mostrarAviso(e.message.orEmpty(), true)
            } finally {
                emparejando = false
            }
        }
    }

    fun emparejarCon(enlace: Enlace, huella: String) {
        huellaPorConfirmar = null
        viewModelScope.launch {
            emparejando = true
            try {
                val nueva = Pc(enlace.base, huella, null)
                val token = nueva.emparejar(enlace.codigo)
                almacen.guardar(Conexion(enlace.base, huella, token))
                while (conectando) delay(100) // un reintento viejo no tiene la conexión nueva
                conectar()
                if (fase == Fase.Lista) mostrarAviso("¡Conectado a TorrentVision!", false)
            } catch (e: ErrorApi) {
                if (fase == Fase.Lista) mostrarAviso(e.message.orEmpty(), true) else fase = Fase.Emparejar(e.message)
            } finally {
                emparejando = false
            }
        }
    }

    /** Vincular sin QR: busca la PC en la wifi, le pide permiso y espera a que en la PC toquen Permitir. */
    fun vincularSinQr() {
        trabajoVinculo?.cancel()
        trabajoVinculo = viewModelScope.launch {
            vinculo = Vinculo(null, "Buscando TorrentVision en la wifi…")
            try {
                val pcs = descubrirPcs(emptySet(), esperaMs = 2500)
                if (pcs.isEmpty()) {
                    vinculo = Vinculo(null, "No encontré TorrentVision en esta wifi. En la PC tiene que estar encendido 📱 ON, " +
                        "y los dos en la misma red.", fallo = true)
                    return@launch
                }
                val (base, huella) = pcs.entries.first()
                val pc = Pc(base, huella, null)
                val nombre = "${android.os.Build.MANUFACTURER} ${android.os.Build.MODEL}".trim()
                val id = pc.solicitar(nombre)
                val codigo = codigoVinculo(huella, id)
                vinculo = Vinculo(codigo, "Mirá la PC: tocá Permitir si muestra este mismo código.")
                val fin = System.currentTimeMillis() + 115_000
                while (System.currentTimeMillis() < fin) {
                    delay(1500)
                    val (estado, token) = pc.estadoSolicitud(id)
                    when (estado) {
                        "aprobada" -> if (token != null) {
                            almacen.guardar(Conexion(base, huella, token))
                            vinculo = null
                            while (conectando) delay(100)
                            conectar()
                            mostrarAviso("¡Vinculado! Desde ahora se conecta solo.", false)
                            return@launch
                        }
                        "rechazada" -> { vinculo = Vinculo(null, "En la PC tocaron Rechazar.", fallo = true); return@launch }
                        "vencida" -> break
                    }
                }
                vinculo = Vinculo(null, "Pasó el tiempo y nadie lo aprobó en la PC. Probá de nuevo.", fallo = true)
            } catch (e: ErrorApi) {
                vinculo = Vinculo(null, e.message.orEmpty(), fallo = true)
            }
        }
    }

    fun cancelarVinculo() {
        trabajoVinculo?.cancel()
        vinculo = null
    }

    fun desconectar() = correr {
        for (c in almacen.conexiones()) {
            try { Pc(c.base, c.huella, c.token).post("/api/salir", JSONObject()) } catch (e: ErrorApi) { /* ya no importa */ }
        }
        almacen.quitarTodas()
        pc = null
        estado = null
        dejarDeVer()
        fase = Fase.Emparejar("Celular desconectado.")
    }

    // --- Utilidades -----------------------------------------------------------------------------------

    fun mostrarAviso(texto: String, malo: Boolean) {
        aviso = Aviso(texto, malo)
    }

    /** Corre algo que puede fallar: los errores de la API ya se avisaron donde hacía falta. */
    fun correr(bloque: suspend () -> Unit): Job = viewModelScope.launch {
        try {
            bloque()
        } catch (e: ErrorApi) {
            // ya se avisó
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            mostrarAviso("Algo salió mal: ${e.message}", true)
        }
    }

    private fun conPc(): Pc = pc ?: throw ErrorApi(SIN_CONEXION, 0)

    /** Una orden a TVon (POST /api/accion). Avisa del error y lo vuelve a lanzar. */
    suspend fun accion(nombre: String, vararg datos: Pair<String, Any?>): JSONObject? {
        try {
            val r = conPc().post("/api/accion", json("accion" to nombre, *datos))
            conectado = true
            r?.optString("aviso")?.takeIf { it.isNotBlank() }?.let { mostrarAviso(it, false) }
            correr { refrescarEstado() }
            return r
        } catch (e: ErrorApi) {
            manejar(e, avisar = true)
            throw e
        }
    }

    /** Lo mismo, sin esperar el resultado. */
    fun hacer(nombre: String, vararg datos: Pair<String, Any?>) = correr { accion(nombre, *datos) }

    private suspend fun <T> leer(avisar: Boolean = false, pedido: suspend (Pc) -> T): T {
        try {
            val r = pedido(conPc())
            conectado = true
            fallos = 0
            return r
        } catch (e: ErrorApi) {
            manejar(e, avisar)
            throw e
        }
    }

    // --- Reproductor ----------------------------------------------------------------------------------

    private var pidiendoEstado = false

    suspend fun refrescarEstado() {
        if (pidiendoEstado || pc == null) return
        pidiendoEstado = true
        try {
            estado = Estado.de(leer { it.obj("/api/estado") })
        } finally {
            pidiendoEstado = false
        }
    }

    private suspend fun decodificar(datos: ByteArray): ImageBitmap? = withContext(Dispatchers.Default) {
        try {
            BitmapFactory.decodeByteArray(datos, 0, datos.size)?.asImageBitmap()
        } catch (e: OutOfMemoryError) {
            null
        }
    }

    private var relojVolumen: Job? = null

    /** El volumen se manda un ratito después de soltar el dedo (no una orden por cada paso). */
    fun volumen(valor: Int) {
        relojVolumen?.cancel()
        relojVolumen = correr {
            delay(150)
            accion("volumen", "valor" to valor)
        }
    }

    /** Botones de volumen del celular → volumen de TVon, mientras se ve el reproductor. */
    fun teclaVolumen(arriba: Boolean, soloMirar: Boolean = false): Boolean {
        val rep = estado?.reproduccion
        if (fase != Fase.Lista || pestana != Pestana.REPRODUCTOR || rep == null || !almacen.teclasVolumen ||
            viendoAca != null || detalles.isNotEmpty()) return false
        if (soloMirar) return true
        val nuevo = (rep.volumen + if (arriba) 5 else -5).coerceIn(0, 100)
        estado = estado?.copy(reproduccion = rep.copy(volumen = nuevo))
        volumen(nuevo)
        return true
    }

    // --- Biblioteca ------------------------------------------------------------------------------------

    suspend fun cargarBiblioteca() {
        biblioteca = Biblioteca.de(leer { it.obj("/api/biblioteca") })
        cargarArchivos()
    }

    suspend fun cargarArchivos() {
        val ruta = Uri.Builder().path("/api/archivos").appendQueryParameter("filtro", filtro)
            .appendQueryParameter("q", busqueda)
            .apply { categoria?.let { appendQueryParameter("categoria", it.toString()) } }
            .build().toString()
        val lista = leer { it.lista(ruta) }.objetos(ArchivoBib::de)
        archivos = lista
        val visibles = lista.map { it.id }.toSet()
        seleccion = seleccion.intersect(visibles)
    }

    private val miniaturas = android.util.LruCache<Int, ImageBitmap>(120)

    suspend fun miniatura(id: Int): ImageBitmap? {
        miniaturas.get(id)?.let { return it }
        val datos = try { conPc().bytes("/api/miniatura?id=$id") } catch (e: ErrorApi) { null } ?: return null
        return decodificar(datos)?.also { miniaturas.put(id, it) }
    }

    fun elegirFiltro(f: String, c: Int?) {
        filtro = f
        categoria = c
        correr { cargarArchivos() }
    }

    private var relojBusqueda: Job? = null

    fun buscar(texto: String) {
        busqueda = texto
        relojBusqueda?.cancel()
        relojBusqueda = correr {
            delay(300)
            cargarArchivos()
        }
    }

    fun alternarSeleccion(id: Int) {
        seleccion = if (id in seleccion) seleccion - id else seleccion + id
        if (seleccion.isEmpty()) eligiendo = false
    }

    fun terminarSeleccion() {
        eligiendo = false
        seleccion = emptySet()
    }

    // --- Inicio: ver en el celular ------------------------------------------------------------------------

    suspend fun cargarInicio() {
        try {
            inicio = Inicio.de(leer { it.obj("/api/inicio") })
            inicioError = null
        } catch (e: ErrorApi) {
            inicioError = e.message
            throw e
        }
    }

    private var relojCatalogo: Job? = null

    suspend fun cargarCatalogo() {
        val ruta = Uri.Builder().path("/api/catalogo")
            .appendQueryParameter("tipo", if (catalogoTexto.isNotBlank()) "todo" else catalogoTipo)
            .appendQueryParameter("genero", catalogoGenero).appendQueryParameter("q", catalogoTexto)
            .appendQueryParameter("orden", catalogoOrden).build().toString()
        catalogo = leer { it.lista(ruta) }.objetos(Cartel::de)
    }

    fun buscarCatalogo(texto: String) {
        catalogoTexto = texto
        relojCatalogo?.cancel()
        relojCatalogo = correr {
            delay(300)
            cargarCatalogo()
        }
    }

    fun filtrarCatalogo(tipo: String = catalogoTipo, genero: String = catalogoGenero, orden: String = catalogoOrden) {
        catalogoTipo = tipo
        catalogoGenero = genero
        catalogoOrden = orden
        correr { cargarCatalogo() }
    }

    private val posters = android.util.LruCache<String, ImageBitmap>(60)

    suspend fun poster(clave: String): ImageBitmap? {
        posters.get(clave)?.let { return it }
        val datos = try {
            conPc().bytes("/api/poster?c=" + Uri.encode(clave))
        } catch (e: ErrorApi) {
            null
        } ?: return null
        return decodificar(datos)?.also { posters.put(clave, it) }
    }

    /** Tocar un póster: la serie (con sus temporadas) o la ficha de la película o el capítulo. */
    fun abrir(c: Cartel) = correr {
        if (c.tipo == "serie") abrirSerie(c.clave) else c.id?.let { abrirFicha(it) }
    }

    suspend fun abrirSerie(clave: String) {
        val serie = SerieDet.de(leer(avisar = true) { it.obj("/api/serie?c=" + Uri.encode(clave)) })
        detalles = detalles.filterNot { it is Detalle.DeSerie && it.serie.clave == clave } + Detalle.DeSerie(serie)
    }

    suspend fun abrirFicha(id: Int) {
        detalles = detalles + Detalle.DeVideo(ficha(id))
    }

    private suspend fun ficha(id: Int) = FichaVideo.de(leer(avisar = true) { it.obj("/api/ficha?id=$id") })

    /** Después de marcar visto, favoritos o corregir la ficha: lo abierto se vuelve a pedir. */
    suspend fun refrescarDetalles() {
        detalles = detalles.map { d ->
            when (d) {
                is Detalle.DeSerie -> Detalle.DeSerie(SerieDet.de(leer { it.obj("/api/serie?c=" + Uri.encode(d.serie.clave)) }))
                is Detalle.DeVideo -> Detalle.DeVideo(ficha(d.ficha.id))
            }
        }
        correr { cargarInicio() }
    }

    fun cerrarDetalle() {
        detalles = detalles.dropLast(1)
        if (detalles.isEmpty() && pestana == Pestana.INICIO) correr { cargarInicio() }
    }

    /** Ver el video en este celular, desde donde quedó (en la PC o acá) o desde el principio. */
    fun verAca(f: FichaVideo, desdeElPrincipio: Boolean = false) {
        val pc = pc ?: return
        if (!f.existe) return mostrarAviso("El archivo ya no está en la PC", true)
        val actual = viendoAca ?: VerEnCelular(getApplication(), pc, viewModelScope, ::mostrarAviso) { siguienteId ->
            correr {
                val siguiente = ficha(siguienteId)
                mostrarAviso("Sigue: ${siguiente.nombreLindo}", false)
                viendoAca?.abrir(siguiente, siguiente.posicion)
            }
        }
        viendoAca = actual
        actual.abrir(f, if (desdeElPrincipio) 0 else f.posicion)
    }

    fun verAcaId(id: Int) = correr { verAca(ficha(id)) }

    fun dejarDeVerAca() {
        viendoAca?.cerrar()
        viendoAca = null
        correr { refrescarDetalles() }
    }

    // --- Películas ---------------------------------------------------------------------------------------

    suspend fun buscarPeliculas(pagina: Int) {
        if (pagina == 1) qPeliculas = peliculasTexto.trim()
        peliculasMensaje = "Buscando…"
        try {
            val ruta = Uri.Builder().path("/api/dp/buscar").appendQueryParameter("q", qPeliculas)
                .appendQueryParameter("orden", orden).appendQueryParameter("pagina", pagina.toString()).build().toString()
            val r = leer { it.obj(ruta) }
            val nuevas = r.optJSONArray("peliculas").objetos(Pelicula::de)
            paginaPeliculas = pagina
            peliculasTotal = r.optInt("total")
            peliculas = if (pagina == 1) nuevas else peliculas + nuevas
            r.optJSONObject("ordenes")?.let { o -> ordenes = o.keys().asSequence().map { it to o.optString(it) }.toList() }
            peliculasMensaje = null
        } catch (e: ErrorApi) {
            peliculasMensaje = e.message
        }
    }

    fun masPeliculas() = correr { buscarPeliculas(paginaPeliculas + 1) }

    private var pidiendoDescargas = false

    suspend fun cargarDescargas() {
        if (pidiendoDescargas) return
        pidiendoDescargas = true
        try {
            descargas = Descargas.de(leer { it.obj("/api/dp/cola") })
        } finally {
            pidiendoDescargas = false
        }
    }

    private var pidiendoTorrents = false

    suspend fun cargarTorrents() {
        if (pidiendoTorrents) return
        pidiendoTorrents = true
        try {
            torrents = leer { it.lista("/api/torrents") }.objetos(Torrent::de)
        } finally {
            pidiendoTorrents = false
        }
    }

    fun bajarTorrent() {
        val enlace = enlaceTorrent.trim()
        if (enlace.isEmpty()) return mostrarAviso("Pegá el link magnet (mantené apretado el recuadro → Pegar)", true)
        correr {
            accion("torrent_agregar", "enlace" to enlace)
            enlaceTorrent = ""
            delay(1500)
            cargarTorrents()
        }
    }

    // --- Subtítulos para la PC: un link (lo baja la PC) o un archivo del celular -------------------------

    var enlaceSubtitulo by mutableStateOf("")

    fun mandarSubtitulo() {
        val enlace = enlaceSubtitulo.trim()
        if (enlace.isEmpty()) return mostrarAviso("Pegá el link del subtítulo o elegí el archivo", true)
        correr { if (subirSubtitulo(json("enlace" to enlace))) enlaceSubtitulo = "" }
    }

    fun mandarArchivoSubtitulo(uri: Uri) = correr {
        val resolver = getApplication<Application>().contentResolver
        var nombre = "subtitulo"
        var tamano = 0L
        resolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE), null, null, null)?.use { c ->
            if (c.moveToFirst()) {
                nombre = c.getString(0) ?: nombre
                tamano = c.getLong(1)
            }
        }
        // Un subtítulo pesa unos KB: así no se lee entero un video elegido por error
        if (tamano > SUBTITULO_MAX) return@correr mostrarAviso("Es demasiado grande para ser un subtítulo", true)
        val bytes = withContext(Dispatchers.IO) { resolver.openInputStream(uri)?.use { it.readBytes() } }
            ?: return@correr mostrarAviso("No se pudo leer el archivo", true)
        subirSubtitulo(json("nombre" to nombre, "contenido" to Base64.encodeToString(bytes, Base64.NO_WRAP)))
    }

    private suspend fun subirSubtitulo(cuerpo: JSONObject): Boolean = try {
        val r = conPc().post("/api/subtitulo", cuerpo)
        conectado = true
        r?.optString("aviso")?.takeIf { it.isNotBlank() }?.let { mostrarAviso(it, false) }
        true
    } catch (e: ErrorApi) {
        manejar(e, avisar = true)
        false
    }

    /** Un link magnet que llegó de otra app (compartir o «abrir con»). */
    fun recibirMagnet(enlace: String) {
        if (fase == Fase.Videoteca) {
            // Sin PC: va a la tarjeta de torrents del celular
            videoteca.enlaceTorrent = enlace
            videoteca.pestana = 1
            return
        }
        enlaceTorrent = enlace
        if (fase == Fase.Lista) irA(Pestana.PELICULAS) else pestana = Pestana.PELICULAS
    }

    // --- Mouse, teclado y pantalla -----------------------------------------------------------------------

    suspend fun cargarMonitores() {
        errorControl = null
        try {
            val m = Monitores.de(leer { it.obj("/api/pantalla/monitores") })
            monitores = m
            if (!viendo) monitor = m.tvon.coerceIn(0, (m.lista.size - 1).coerceAtLeast(0))
            if (!m.control) errorControl = "Manejar el mouse y el teclado está desactivado en TorrentVision (📱 ON → Opciones)."
        } catch (e: ErrorApi) {
            errorControl = e.message
        }
    }

    // Las entradas van de a una y en orden (mandadas juntas podrían llegar cambiadas). Los movimientos
    // del touchpad se suman mientras se espera la respuesta anterior. Todo corre en el hilo principal.
    private val pendientes = ArrayDeque<JSONObject>()
    private var dx = 0f
    private var dy = 0f
    private var enviando = false

    private fun sacarMovimiento(): JSONObject? {
        val x = Math.round(dx)
        val y = Math.round(dy)
        if (x == 0 && y == 0) return null
        dx -= x
        dy -= y
        return json("tipo" to "desplazar", "dx" to x, "dy" to y)
    }

    fun entrada(vararg datos: Pair<String, Any?>) {
        sacarMovimiento()?.let(pendientes::addLast) // lo que se movió antes va antes
        pendientes.addLast(json("monitor" to monitor, *datos))
        enviarCola()
        // Después de un clic izquierdo se pregunta si quedó un campo de texto enfocado en la PC
        val d = datos.toMap()
        val izquierdo = (d["boton"] ?: "izquierdo") == "izquierdo"
        if (izquierdo && (d["tipo"] == "clic_aqui" || d["tipo"] == "clic" || (d["tipo"] == "boton" && d["apretado"] == false))) {
            revisarEscritura()
        }
    }

    private var consultaEscritura: Job? = null

    private fun revisarEscritura() {
        consultaEscritura?.cancel()
        consultaEscritura = viewModelScope.launch {
            while (enviando) delay(30) // que el clic llegue antes que la pregunta
            val r = try {
                conPc().obj("/api/pantalla/escribiendo")
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                return@launch // una PC más vieja no lo sabe responder: no pasa nada
            }
            if (r.optBoolean("escribiendo")) pedirTeclado++
        }
    }

    fun moverPuntero(x: Float, y: Float) {
        dx += x
        dy += y
        enviarCola()
    }

    private fun enviarCola() {
        if (enviando) return
        enviando = true
        viewModelScope.launch {
            try {
                while (true) {
                    val datos = pendientes.removeFirstOrNull() ?: sacarMovimiento() ?: break
                    try {
                        conPc().post("/api/pantalla/entrada", datos)
                    } catch (e: CancellationException) {
                        throw e
                    } catch (e: Exception) {
                        pendientes.clear()
                        dx = 0f
                        dy = 0f
                        if (e is ErrorApi) manejar(e, avisar = true) else mostrarAviso("Algo salió mal: ${e.message}", true)
                    }
                }
            } finally {
                enviando = false
            }
        }
    }

    fun mantenerClic(activo: Boolean) {
        if (mantenido == activo) return
        mantenido = activo
        if (pc != null) entrada("tipo" to "boton", "boton" to "izquierdo", "apretado" to activo)
    }

    private var transmision: Job? = null
    private var llamada: Call? = null

    /**
     * La pantalla de la PC llega como MJPEG. Se lee en un hilo y solo se decodifica el último cuadro
     * completo: si el celular va atrasado, los viejos se saltean y no se acumula demora.
     */
    fun verPantalla(calidad: Calidad) {
        val pc = pc ?: return
        dejarDeVer()
        viendo = true
        errorPantalla = null
        val ruta = Uri.Builder().path("/api/pantalla.mjpg")
            .appendQueryParameter("monitor", monitor.toString())
            .appendQueryParameter("ancho", calidad.ancho.toString())
            .appendQueryParameter("calidad", calidad.calidad.toString())
            .appendQueryParameter("fps", calidad.fps.toString())
            .build().toString()
        val esta = pc.llamada(ruta)
        llamada = esta
        transmision = viewModelScope.launch {
            val cuadros = Channel<ByteArray>(Channel.CONFLATED)
            val dibujar = launch(Dispatchers.Default) {
                // Tres mapas de bits que se reusan por turno: sin basura por cada cuadro
                val mapas = arrayOfNulls<Bitmap>(3)
                var turno = 0
                for (datos in cuadros) {
                    val opciones = BitmapFactory.Options().apply {
                        inMutable = true
                        inBitmap = mapas[turno]
                    }
                    val mapa = try {
                        BitmapFactory.decodeByteArray(datos, 0, datos.size, opciones)
                    } catch (e: IllegalArgumentException) {
                        // cambió el tamaño: un mapa nuevo
                        try { BitmapFactory.decodeByteArray(datos, 0, datos.size) } catch (e: Exception) { null }
                    } catch (e: OutOfMemoryError) {
                        null // se saltea el cuadro
                    } ?: continue
                    mapas[turno] = mapa
                    turno = (turno + 1) % mapas.size
                    val imagen = mapa.asImageBitmap()
                    withContext(Dispatchers.Main) { if (llamada === esta) pantallaPC = imagen }
                }
            }
            try {
                withContext(Dispatchers.IO) {
                    pc.ejecutar(esta).use { r ->
                        val fuente = r.body?.source() ?: throw IOException("sin datos")
                        var largo = -1
                        while (true) {
                            val linea = fuente.readUtf8LineStrict(1024)
                            when {
                                linea.isEmpty() && largo >= 0 -> {
                                    cuadros.trySend(fuente.readByteArray(largo.toLong()))
                                    largo = -1
                                }
                                linea.startsWith("Content-Length:", ignoreCase = true) ->
                                    largo = linea.substringAfter(':').trim().toIntOrNull()?.takeIf { it in 1..(20 shl 20) } ?: -1
                            }
                        }
                    }
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                if (llamada === esta) {
                    errorPantalla = if (e is ErrorApi && e.codigo > 0) e.message
                    else "Se cortó la transmisión (¿la PC dejó de compartir o se apagó ON?)."
                }
            } finally {
                cuadros.close()
                dibujar.cancel()
                if (llamada === esta) {
                    llamada = null
                    viendo = false
                    pantallaPC = null
                    pantallaCompleta = false
                }
            }
        }
    }

    /** Cortar la conexión: así la PC deja de capturar y saca el aviso. */
    fun dejarDeVer() {
        val actual = llamada ?: return
        llamada = null
        actual.cancel()
        transmision?.cancel()
        viendo = false
        pantallaPC = null
        pantallaCompleta = false
    }

    override fun onCleared() {
        llamada?.cancel()
        viendoAca?.cerrar()
    }
}

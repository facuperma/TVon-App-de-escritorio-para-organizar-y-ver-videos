package io.github.facuperma.tvon.ui

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import androidx.media3.common.MediaItem
import androidx.media3.common.MimeTypes
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import io.github.facuperma.tvon.Hoja
import io.github.facuperma.tvon.Modelo
import io.github.facuperma.tvon.Opcion
import io.github.facuperma.tvon.PeliculaLocal
import io.github.facuperma.tvon.Videoteca
import io.github.facuperma.tvon.miles
import io.github.facuperma.tvon.tamano
import io.github.facuperma.tvon.Confirmar
import kotlinx.coroutines.delay

/** El botón rojo: sin PC, el celular pasa a ser la videoteca. Pregunta antes y pide el permiso si hace falta. */
@Composable
fun BotonVideoteca(vm: Modelo, modifier: Modifier = Modifier) {
    val contexto = LocalContext.current
    var preguntar by remember { mutableStateOf(false) }
    // Android 8 y 9 piden permiso para escribir en Películas; desde el 10 no hace falta
    val permiso = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        if (ok) vm.usarVideoteca() else vm.mostrarAviso("Sin ese permiso no se pueden guardar películas en el celular", true)
    }
    Boton("📱 Usar celular como videoteca", modifier.fillMaxWidth(), Estilo.PELIGRO) { preguntar = true }
    if (preguntar) {
        val libre = remember { vm.videoteca.espacioLibre() }
        AlertDialog(
            onDismissRequest = { preguntar = false },
            containerColor = C.panel,
            title = { Text("¿Usar el celular sin PC?") },
            text = {
                Text("El celular baja las películas y sus subtítulos, las guarda en Películas/${Videoteca.CARPETA} " +
                    "y las reproduce, sin TorrentVision en la PC.\n\n" +
                    "Lugar libre: ${tamano(libre)} (siempre se deja 1 GB para el celular).\n" +
                    "Se baja solo con wifi (lo podés cambiar en ⚙).\n\n" +
                    "Para volver a manejar la PC: ⚙ → Usar con una PC. Las películas quedan en la carpeta.")
            },
            confirmButton = {
                TextButton(onClick = {
                    preguntar = false
                    val falta = Build.VERSION.SDK_INT < Build.VERSION_CODES.Q && ContextCompat.checkSelfPermission(
                        contexto, Manifest.permission.WRITE_EXTERNAL_STORAGE) != PackageManager.PERMISSION_GRANTED
                    if (falta) permiso.launch(Manifest.permission.WRITE_EXTERNAL_STORAGE) else vm.usarVideoteca()
                }) { Text("Usar el celular") }
            },
            dismissButton = { TextButton(onClick = { preguntar = false }) { Text("Cancelar") } },
        )
    }
}

private enum class PestanaVideoteca(val icono: String, val texto: String) {
    BIBLIOTECA("📚", "Películas"), AGREGAR("➕", "Agregar"), AJUSTES("⚙", "Ajustes"),
}

@Composable
fun PantallaVideoteca(vm: Modelo) {
    val v = vm.videoteca
    LaunchedEffect(Unit) { v.refrescar() }
    v.viendo?.let { ReproductorLocal(v, it); return }
    var pestana by remember { mutableStateOf(PestanaVideoteca.BIBLIOTECA) }
    BackHandler(enabled = pestana != PestanaVideoteca.BIBLIOTECA) { pestana = PestanaVideoteca.BIBLIOTECA }
    Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding()) {
        Row(
            Modifier.fillMaxWidth().background(C.panel).padding(horizontal = 16.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Logo(28)
            Column(Modifier.weight(1f)) {
                Text("TorrentVision", fontWeight = FontWeight.Bold, color = Color.White)
                Text("📱 Videoteca del celular · ${tamano(v.libre)} libres", color = C.tenue, fontSize = 12.sp)
            }
        }
        Box(Modifier.weight(1f).imePadding()) {
            when (pestana) {
                PestanaVideoteca.BIBLIOTECA -> Biblioteca(vm) { pestana = PestanaVideoteca.AGREGAR }
                PestanaVideoteca.AGREGAR -> Agregar(vm)
                PestanaVideoteca.AJUSTES -> Ajustes(vm)
            }
        }
        NavigationBar(containerColor = C.panel, windowInsets = WindowInsets(0, 0, 0, 0)) {
            for (p in PestanaVideoteca.entries) {
                NavigationBarItem(
                    selected = pestana == p, onClick = { pestana = p },
                    icon = { Text(p.icono, fontSize = 18.sp) },
                    label = { Text(p.texto, fontSize = 10.sp, maxLines = 1) },
                    colors = NavigationBarItemDefaults.colors(
                        selectedTextColor = Color.White, unselectedTextColor = C.tenue, indicatorColor = C.chipActivo,
                    ),
                )
            }
        }
    }
}

@Composable
private fun Biblioteca(vm: Modelo, irAAgregar: () -> Unit) {
    val v = vm.videoteca
    var paraSubtitulo by remember { mutableStateOf<PeliculaLocal?>(null) }
    val elegir = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        val p = paraSubtitulo
        if (uri != null && p != null) vm.correr { vm.mostrarAviso(v.agregarSubtitulo(p, uri), false) }
    }
    LazyColumn(contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp), modifier = Modifier.fillMaxSize()) {
        if (v.descargas.isNotEmpty()) {
            item { Pista("⬇ Bajando ${v.descargas.size} · mirá el avance en ➕ Agregar", Modifier.padding(vertical = 4.dp)) }
        }
        if (v.peliculas.isEmpty()) {
            item {
                Tarjeta {
                    TituloTarjeta("Todavía no hay películas")
                    Pista("Buscá películas de dominio público en ➕ Agregar: se bajan a Películas/${Videoteca.CARPETA}. " +
                        "También aparece acá cualquier video que copies a esa carpeta.")
                    Boton("➕ Agregar películas", Modifier.fillMaxWidth(), Estilo.PRIMARIO) { irAAgregar() }
                }
            }
        }
        items(v.peliculas, key = { it.archivo.path }) { p ->
            val estado = when {
                p.vista -> "✓ vista"
                p.empezada -> "${(p.posicion * 100 / p.duracion.coerceAtLeast(1))} %"
                else -> null
            }
            Item(
                p.titulo,
                listOfNotNull(tamano(p.tamano), estado, if (p.subtitulos.isNotEmpty()) "💬 ${p.subtitulos.size}" else null)
                    .joinToString(" · "),
                { IconoTexto("🎞") },
                colorNombre = when { p.vista -> C.vista; p.empezada -> C.pendiente; else -> C.texto },
                alTocar = { v.viendo = p },
                alMantener = {
                    vm.hoja = Hoja(p.titulo, listOf(
                        Opcion("▶ Ver") { v.viendo = p },
                        Opcion("⏮ Ver desde el principio") { v.guardarProgreso(p, 0, p.duracion); v.refrescar(); v.viendo = v.peliculas.firstOrNull { it.archivo == p.archivo } },
                        Opcion("💬 Agregar subtítulo (.srt o .zip)") { paraSubtitulo = p; elegir.launch("*/*") },
                        Opcion(if (p.vista) "Marcar como no vista" else "✓ Marcar como vista") { v.marcarVista(p, !p.vista) },
                        Opcion("🗑 Borrar del celular", peligro = true, confirmar = "¿Borrar «${p.titulo}» y sus subtítulos del celular?") {
                            v.borrar(p)
                            vm.mostrarAviso("Borrada: ${p.titulo}", false)
                        },
                    ))
                },
            )
        }
        if (v.peliculas.isNotEmpty()) item { Pista("Mantené apretada una película para más opciones.", Modifier.padding(vertical = 6.dp)) }
    }
}

@Composable
private fun Agregar(vm: Modelo) {
    val v = vm.videoteca
    val foco = LocalFocusManager.current
    val contexto = LocalContext.current
    val buscar = { foco.clearFocus(); vm.correr { v.buscar(nueva = true) }; Unit }
    LaunchedEffect(Unit) { if (v.resultados.isEmpty()) v.buscar(nueva = true) }
    LazyColumn(contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp), modifier = Modifier.fillMaxSize()) {
        if (v.descargas.isNotEmpty()) {
            item {
                Tarjeta {
                    TituloTarjeta("⬇ Bajando al celular")
                    for (d in v.descargas) {
                        Item(d.titulo, d.estado + if (d.total > 0) " · ${tamano(d.bajado)} de ${tamano(d.total)}" else "",
                            { IconoTexto(if (d.fallo) "⚠" else "⬇") },
                            abajo = { if (d.total > 0) Progreso(d.bajado.toFloat() / d.total) }) {
                            Boton("✕", chico = true) { v.cancelar(d) }
                        }
                    }
                    if (v.soloWifi) Pista("Solo con wifi: con datos móviles quedan esperando (se cambia en ⚙).")
                }
            }
        }
        item {
            Tarjeta {
                TituloTarjeta("🎞 Películas de dominio público")
                Pista("De la colección del Internet Archive: libres y gratis. Se bajan con sus subtítulos, si tienen.")
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        v.texto, { v.texto = it }, Modifier.weight(1f), singleLine = true,
                        colors = campoColores(), placeholder = { Text("Título (vacío = las más populares)") },
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                        keyboardActions = KeyboardActions(onSearch = { buscar() }),
                    )
                    Boton("Buscar", estilo = Estilo.PRIMARIO) { buscar() }
                }
                Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    for ((clave, o) in Videoteca.ORDENES) Chip(o.first, v.orden == clave) { v.orden = clave; buscar() }
                }
            }
        }
        item {
            Pista(v.mensaje ?: "${v.resultados.size} de ${miles(v.total.toLong())} películas", Modifier.padding(vertical = 6.dp))
        }
        items(v.resultados, key = { "a" + it.identificador }) { p ->
            val ya = v.peliculas.any { it.titulo == Videoteca.nombreLindo(p.titulo, p.anio) } ||
                v.descargas.any { it.titulo == p.titulo }
            Item(p.titulo, listOfNotNull(p.anio, "${miles(p.descargas)} descargas").joinToString(" · "), { IconoTexto("🎞") }) {
                if (ya) Pista("✓ en el celular", color = C.acentoClaro)
                else Boton("⬇", chico = true) { vm.correr { vm.mostrarAviso(v.descargar(p), false) } }
            }
        }
        if (v.resultados.size < v.total) {
            item { Boton("Cargar más", Modifier.fillMaxWidth().padding(vertical = 6.dp)) { vm.correr { v.buscar(nueva = false) } } }
        }
        item {
            Tarjeta {
                TituloTarjeta("💬 Subtítulos")
                Pista("Bajá el .srt o .zip en el navegador y después, en 📚 Películas, mantené apretada la película → " +
                    "Agregar subtítulo. Queda junto a la película con su nombre.")
                Boton("🌐 Buscar subtítulos", Modifier.fillMaxWidth()) {
                    try {
                        contexto.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://subdivx.com/")))
                    } catch (e: Exception) {
                        vm.mostrarAviso("No hay un navegador para abrir el link", true)
                    }
                }
            }
        }
        item {
            Tarjeta {
                TituloTarjeta("🧲 Torrents (links magnet)")
                Pista("Próximamente: para bajar torrents en el celular, TorrentVision va a descargar aparte el motor de " +
                    "torrent (≈ 12 MB), solo si lo activás. Así la app sigue siendo liviana para quien no lo usa.")
            }
        }
    }
}

@Composable
private fun Ajustes(vm: Modelo) {
    val v = vm.videoteca
    val ocupado = v.peliculas.sumOf { it.tamano }
    LazyColumn(contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp), modifier = Modifier.fillMaxSize()) {
        item {
            Tarjeta {
                TituloTarjeta("📂 Dónde se guardan")
                Text("Películas/${Videoteca.CARPETA}", color = Color.White)
                Pista(v.carpeta.path)
                Pista(listOfNotNull("${v.peliculas.size} películas", tamano(ocupado).ifEmpty { null },
                    "quedan ${tamano(v.libre)} libres").joinToString(" · "))
                Pista("La carpeta se ve en la galería y en Archivos, y no se borra si desinstalás la app.")
            }
        }
        item {
            Tarjeta {
                TituloTarjeta("⬇ Descargas")
                Interruptor("Bajar solo con wifi", v.soloWifi) { v.cambiarSoloWifi(it) }
                Pista(if (v.soloWifi) "Con datos móviles, las descargas esperan a que haya wifi."
                    else "Ojo: una película puede gastar varios GB del plan de datos.")
            }
        }
        item {
            Tarjeta {
                TituloTarjeta("🖥 ¿Tenés TorrentVision en una PC?")
                Pista("La app vuelve a manejar la PC (escaneando su QR). Las películas del celular quedan en su carpeta " +
                    "y las ves de nuevo con el botón rojo.")
                Boton("🖥 Usar con una PC", Modifier.fillMaxWidth()) {
                    vm.confirmar = Confirmar("¿Volver a usar la app con la PC?", "Usar con la PC") { vm.dejarVideoteca() }
                }
            }
        }
    }
}

/** Reproduce una película del celular, con sus subtítulos, desde donde quedó. */
@Composable
private fun ReproductorLocal(v: Videoteca, p: PeliculaLocal) {
    val contexto = LocalContext.current
    val jugador = remember(p.archivo) {
        ExoPlayer.Builder(contexto).build().apply {
            val subs = p.subtitulos.mapIndexed { i, s ->
                MediaItem.SubtitleConfiguration.Builder(Uri.fromFile(s))
                    .setMimeType(if (s.extension.equals("vtt", true)) MimeTypes.TEXT_VTT else MimeTypes.APPLICATION_SUBRIP)
                    .setLabel(s.name.removePrefix(p.archivo.nameWithoutExtension).trim('.', ' ').ifEmpty { "Subtítulo" })
                    .setId("sub$i")
                    .setSelectionFlags(if (i == 0) androidx.media3.common.C.SELECTION_FLAG_DEFAULT else 0)
                    .build()
            }
            setMediaItem(MediaItem.Builder().setUri(Uri.fromFile(p.archivo)).setSubtitleConfigurations(subs).build(),
                if (p.vista) 0L else p.posicion)
            prepare()
            playWhenReady = true
        }
    }
    val guardar = {
        if (jugador.duration > 0) v.guardarProgreso(p, jugador.currentPosition, jugador.duration)
    }
    DisposableEffect(jugador) {
        onDispose {
            guardar()
            jugador.release()
            v.refrescar()
        }
    }
    LaunchedEffect(jugador) {
        // Cada 10 segundos, por si se apaga el celular
        while (true) {
            delay(10_000)
            if (jugador.isPlaying) guardar()
        }
    }
    LifecycleEventEffect(Lifecycle.Event.ON_STOP) {
        jugador.pause()
        guardar()
    }
    BackHandler { v.viendo = null }
    Box(Modifier.fillMaxSize().background(Color.Black)) {
        AndroidView(
            factory = { c ->
                PlayerView(c).apply {
                    player = jugador
                    keepScreenOn = true
                    setShowSubtitleButton(true)
                    setShowNextButton(false)
                    setShowPreviousButton(false)
                }
            },
            modifier = Modifier.fillMaxSize(),
        )
        Row(Modifier.fillMaxWidth().padding(8.dp), verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            Chip("✕") { v.viendo = null }
            Text(p.titulo, color = Color.White, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
        }
    }
}

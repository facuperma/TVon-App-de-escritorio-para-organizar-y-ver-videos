package io.github.facuperma.tvon.ui

import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import io.github.facuperma.tvon.Cast
import io.github.facuperma.tvon.Modelo
import io.github.facuperma.tvon.Subtitulos
import io.github.facuperma.tvon.textoSincronia
import io.github.facuperma.tvon.tiempo
import kotlinx.coroutines.delay

private val ESTADOS = mapOf(
    "reproduciendo" to "▶ Reproduciendo", "pausa" to "⏸ En pausa", "detenido" to "⏹ Detenido",
    "vista_previa" to "Vista previa: tocá ▶ para empezar",
)

@Composable
fun deslizador() = SliderDefaults.colors(thumbColor = Color.White, activeTrackColor = C.acento, inactiveTrackColor = C.fondoHondo)

@Composable
fun PestanaReproductor(vm: Modelo) {
    val e = vm.estado
    val rep = e?.reproduccion
    val hay = rep != null
    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp, vertical = 6.dp)
    ) {
        Tarjeta {
            Text(e?.archivo?.nombre ?: "Nada en reproducción", color = C.titulo, fontWeight = FontWeight.SemiBold)
            Pista(rep?.let { ESTADOS[it.estado].orEmpty() } ?: if (e?.archivo != null) "🖼 Imagen" else "Elegí algo en la Biblioteca")
        }

        Tarjeta {
            // Barra de tiempo: mientras se arrastra no la pisa el estado que llega de la PC
            var arrastre by remember { mutableStateOf<Float?>(null) }
            val duracion = (rep?.duracion ?: 0L).coerceAtLeast(1L).toFloat()
            val posicion = arrastre ?: (rep?.posicion ?: 0L).toFloat()
            Slider(
                value = posicion.coerceIn(0f, duracion), valueRange = 0f..duracion, enabled = hay, colors = deslizador(),
                onValueChange = { arrastre = it },
                onValueChangeFinished = {
                    arrastre?.let { ms -> vm.correr { try { vm.accion("ir_a", "ms" to ms.toLong()) } finally { arrastre = null } } }
                },
            )
            Row(Modifier.fillMaxWidth()) {
                Pista(tiempo(posicion.toLong()), Modifier.weight(1f))
                Pista(tiempo(rep?.duracion ?: 0L))
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly, verticalAlignment = Alignment.CenterVertically) {
                Redondo("⏮") { vm.hacer("lista", "paso" to -1) }
                Redondo("↺15", habilitado = hay) { vm.hacer("adelantar", "ms" to -15000) }
                Redondo(if (rep?.estado == "reproduciendo") "⏸" else "▶", grande = true, habilitado = hay) { vm.hacer("play_pausa") }
                Redondo("15↻", habilitado = hay) { vm.hacer("adelantar", "ms" to 15000) }
                Redondo("⏭", habilitado = hay) { vm.hacer("siguiente") }
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Boton("−5 s", Modifier.weight(1f), habilitado = hay, chico = true) { vm.hacer("adelantar", "ms" to -5000) }
                Boton("⏹", Modifier.weight(1f), habilitado = hay, chico = true) { vm.hacer("detener") }
                Boton("+5 s", Modifier.weight(1f), habilitado = hay, chico = true) { vm.hacer("adelantar", "ms" to 5000) }
                Boton("Lista ▶", Modifier.weight(1f), chico = true) { vm.hacer("lista", "paso" to 1) }
            }
            Volumen(vm, rep?.volumen ?: 50, rep?.silencio ?: false, hay)
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Boton("⛶ Pantalla completa", chico = true) { vm.hacer("pantalla_completa") }
                Box(Modifier.weight(1f).padding(start = 12.dp)) {
                    Interruptor("🔌 Apagar la PC al terminar", e?.apagarAlTerminar ?: false) { vm.hacer("apagar_al_terminar", "activo" to it) }
                }
            }
        }

        e?.subtitulos?.let { TarjetaSubtitulos(vm, it, e.opensubtitles) }

        // El touchpad en el medio: se maneja el mouse de la PC sin cambiar de pestaña
        // Al hacer clic en un campo de texto de la PC, el teclado del celular se abre solo acá
        vm.errorControl?.let { Text(it, color = C.error) }
        if (vm.monitores?.control != false) {
            Teclado(vm, compacto = true)
            Tarjeta {
                TituloTarjeta("🖱 Mouse")
                Touchpad(vm, Modifier.height(240.dp))
                BotonesMouse(vm)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Pista("Velocidad")
                    var velocidad by remember { mutableFloatStateOf(vm.almacen.velocidad) }
                    Slider(
                        velocidad, { velocidad = it; vm.almacen.velocidad = it },
                        Modifier.weight(1f).padding(start = 12.dp), valueRange = 0.5f..4f, colors = deslizador(),
                    )
                }
            }
        }

        e?.cast?.let { TarjetaTele(vm, it, hay) }

        Tarjeta {
            val cola = e?.cola.orEmpty()
            TituloTarjeta("☰ Cola" + if (cola.isNotEmpty()) " (${cola.size})" else "") {
                if (cola.isNotEmpty()) Boton("Vaciar", chico = true) { vm.hacer("cola_vaciar") }
            }
            if (cola.isEmpty()) Pista("Vacía. Agregá videos desde la Biblioteca.")
            cola.forEachIndexed { i, v ->
                Item("${i + 1}. ${v.nombre}", icono = { IconoTexto("🎬") }) {
                    Boton("▶", chico = true) { vm.hacer("cola_reproducir", "ruta" to v.ruta) }
                    Boton("✕", chico = true) { vm.hacer("cola_quitar", "ruta" to v.ruta) }
                }
            }
        }
    }
}

/** Mandar el video a la tele (Chromecast): lo hace la PC; el celular elige la tele y la maneja. */
@Composable
private fun TarjetaTele(vm: Modelo, c: Cast, hayVideo: Boolean) {
    Tarjeta {
        TituloTarjeta("📺 Tele") {
            Boton(if (c.buscando) "Buscando…" else "🔄 Buscar", chico = true, habilitado = !c.buscando) { vm.hacer("cast_buscar") }
        }
        val t = c.transmision
        when {
            !c.disponible -> Pista("Este TorrentVision de la PC no tiene Chromecast: actualizalo.")
            t != null -> {
                Text("En ${t.dispositivo}: ${t.titulo}", color = C.titulo, fontWeight = FontWeight.SemiBold)
                Pista(tiempo(t.posicion) + " / " + tiempo(t.duracion) +
                    when (t.estado) { "pausa" -> " · en pausa"; "cargando" -> " · cargando…"; else -> "" })
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly, verticalAlignment = Alignment.CenterVertically) {
                    Redondo("↺15") { vm.hacer("cast_adelantar", "ms" to -15000) }
                    Redondo(if (t.estado == "pausa") "▶" else "⏸", grande = true) { vm.hacer("cast_play_pausa") }
                    Redondo("15↻") { vm.hacer("cast_adelantar", "ms" to 15000) }
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Boton("🔉 −", Modifier.weight(1f), chico = true) { vm.hacer("cast_volumen", "valor" to (t.volumen - 10).coerceAtLeast(0)) }
                    Boton("🔊 +", Modifier.weight(1f), chico = true) { vm.hacer("cast_volumen", "valor" to (t.volumen + 10).coerceAtMost(100)) }
                    Boton("⏹ Dejar de transmitir", Modifier.weight(2f), chico = true) { vm.hacer("cast_detener") }
                }
            }
            c.teles.isEmpty() -> Pista(if (c.buscando) "Buscando Chromecast en la red de la PC…"
                else "Tocá 🔄 Buscar. El Chromecast tiene que estar prendido y en la misma red que la PC.")
            else -> {
                if (!hayVideo) Pista("Abrí un video (Biblioteca o Inicio) y elegí la tele.")
                for (tele in c.teles) {
                    Item(tele.nombre, tele.modelo, { IconoTexto("📺") }) {
                        Boton("Mandar", chico = true, estilo = Estilo.PRIMARIO, habilitado = hayVideo) {
                            vm.hacer("cast_iniciar", "dispositivo" to tele.id)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun Volumen(vm: Modelo, volumen: Int, silencio: Boolean, hay: Boolean) {
    // Mientras se toca la barra (y un ratito después) manda lo que muestra el celular
    var tocado by remember { mutableStateOf<Float?>(null) }
    var soltado by remember { mutableIntStateOf(0) }
    LaunchedEffect(soltado) {
        if (soltado > 0) {
            delay(800)
            tocado = null
        }
    }
    val valor = tocado ?: volumen.toFloat()
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Redondo(if (silencio) "🔇" else "🔊", habilitado = hay) { vm.hacer("silencio") }
        Slider(
            value = valor, valueRange = 0f..100f, enabled = hay, colors = deslizador(),
            modifier = Modifier.weight(1f).padding(horizontal = 8.dp),
            onValueChange = {
                tocado = it
                vm.volumen(it.toInt())
            },
            onValueChangeFinished = { soltado++ },
        )
        Pista("${valor.toInt()} %", Modifier.width(44.dp))
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun TarjetaSubtitulos(vm: Modelo, s: Subtitulos, conClave: Boolean) {
    var abierta by rememberSaveable { mutableStateOf(false) }
    val activo = s.archivos.firstOrNull { it.activo }?.texto ?: s.pistas.firstOrNull { it.activa }?.texto
    Tarjeta {
        Row(
            Modifier
                .fillMaxWidth()
                .clickable { abierta = !abierta },
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("CC Subtítulos", color = C.titulo, fontWeight = FontWeight.SemiBold)
            Pista(" · " + (activo ?: "desactivados"), Modifier.weight(1f).padding(start = 4.dp))
            Text(if (abierta) "▾" else "▸", color = C.tenue)
        }
        if (!abierta) return@Tarjeta
        OpcionSub("Desactivados", !s.activos) { vm.hacer("subtitulos") }
        for (a in s.archivos) OpcionSub(a.texto, a.activo) { vm.hacer("subtitulos", "archivo" to a.ruta) }
        s.pistas.forEachIndexed { i, p -> OpcionSub("${p.texto} (incluida en el video)", p.activa) { vm.hacer("subtitulos", "pista" to i) } }

        val conArchivo = s.archivos.any { it.activo }
        Pista("Sincronía: ${textoSincronia(s.retraso)}")
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            for ((texto, ms) in listOf("◀◀" to -500, "◀ Antes" to -100, "Después ▶" to 100, "▶▶" to 500)) {
                Boton(texto, Modifier.weight(1f), habilitado = conArchivo, chico = true) { vm.hacer("retraso", "ms" to ms) }
            }
        }
        // El número exacto, escrito a mano (también con signo: -2500 = salen 2,5 s antes)
        var ms by rememberSaveable { mutableStateOf("") }
        val aplicar = {
            ms.trim().toIntOrNull()?.let { vm.hacer("retraso", "valor" to it.coerceIn(-600_000, 600_000)); ms = "" }
                ?: vm.mostrarAviso("Escribí un número de milisegundos, por ejemplo -2500 o 1200", true)
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(
                ms, { ms = it.filter { c -> c.isDigit() || c == '-' }.take(7) }, Modifier.weight(1f), singleLine = true,
                enabled = conArchivo, colors = campoColores(), placeholder = { Text("${s.retraso} ms") },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number, imeAction = ImeAction.Done),
                keyboardActions = androidx.compose.foundation.text.KeyboardActions(onDone = { aplicar() }),
            )
            Boton("Aplicar ms", habilitado = conArchivo, chico = true) { aplicar() }
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            Boton("🪄 Automática", Modifier.weight(1f), habilitado = conArchivo, chico = true) { vm.hacer("sincronizar_auto") }
            Boton("🎯 Ahora habla", Modifier.weight(1f), habilitado = conArchivo, chico = true) { vm.hacer("sincronizar_ahora") }
        }
        Boton("↺ Sin ajuste", Modifier.fillMaxWidth(), habilitado = conArchivo, chico = true) { vm.hacer("retraso", "valor" to 0) }
        FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            for (t in s.tamanos) Chip(t.texto, t.escala == s.escala) { vm.hacer("tamano_subtitulos", "escala" to t.escala) }
        }
        Boton("🌐 Buscar en internet (OpenSubtitles)", Modifier.fillMaxWidth()) {
            if (conClave) vm.hacer("buscar_subtitulos")
            else vm.mostrarAviso("Falta la clave de OpenSubtitles: cargala en Configuración → Preferencias, en la PC", true)
        }
    }
}

@Composable
private fun OpcionSub(texto: String, activa: Boolean, alTocar: () -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(8.dp))
            .background(if (activa) C.chipActivo else Color.Transparent)
            .clickable(onClick = alTocar)
            .padding(horizontal = 10.dp, vertical = 9.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(if (activa) "●" else "○", color = if (activa) C.acentoClaro else C.tenue, modifier = Modifier.width(24.dp))
        Text(texto, color = if (activa) C.titulo else C.texto)
    }
}

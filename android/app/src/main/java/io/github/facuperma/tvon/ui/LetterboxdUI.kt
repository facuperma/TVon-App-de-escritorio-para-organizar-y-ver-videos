package io.github.facuperma.tvon.ui

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.net.Uri
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import io.github.facuperma.tvon.Hoja
import io.github.facuperma.tvon.Modelo
import io.github.facuperma.tvon.Opcion
import io.github.facuperma.tvon.PeliLb

/** El interruptor de arriba de la pestaña: la biblioteca de la PC o la lista de Letterboxd. */
@Composable
fun SelectorBiblioteca(vm: Modelo) {
    Row(Modifier.padding(bottom = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Chip("📚 Biblioteca", vm.bibVista == "biblioteca") { vm.bibVista = "biblioteca" }
        Chip("🎬 Letterboxd", vm.bibVista == "letterboxd") { vm.bibVista = "letterboxd" }
    }
}

@Composable
fun PestanaLetterboxd(vm: Modelo) {
    val foco = LocalFocusManager.current
    val contexto = LocalContext.current
    LaunchedEffect(Unit) { if (vm.lbPelis.isEmpty() && !vm.lbCargando) vm.cargarLetterboxd() }
    val visibles = if (vm.lbOcultar) vm.lbPelis.filter { !it.tengo } else vm.lbPelis
    val tengo = vm.lbPelis.count { it.tengo }
    LazyColumn(contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp), modifier = Modifier.fillMaxSize()) {
        item { SelectorBiblioteca(vm) }
        item {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    vm.lbUsuario, { vm.lbUsuario = it }, Modifier.weight(1f), singleLine = true, colors = campoColores(),
                    placeholder = { Text("Tu usuario o link de Letterboxd") },
                    keyboardOptions = KeyboardOptions(autoCorrectEnabled = false, keyboardType = KeyboardType.Uri, imeAction = ImeAction.Go),
                    keyboardActions = KeyboardActions(onGo = { foco.clearFocus(); vm.cargarLetterboxd("watchlist", true) }),
                )
                Boton("Cargar", estilo = Estilo.PRIMARIO) { foco.clearFocus(); vm.cargarLetterboxd("watchlist", true) }
            }
        }
        item {
            Row(Modifier.padding(vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Chip("📋 Mi watchlist", vm.lbVista == "watchlist") { vm.cargarLetterboxd("watchlist", true) }
                Chip("🏆 Las 500 mejores", vm.lbVista == "mejores") { vm.cargarLetterboxd("mejores") }
            }
        }
        item { Interruptor("Ocultar las que ya tengo", vm.lbOcultar) { vm.lbOcultar = it } }
        item {
            Pista(
                when {
                    vm.lbCargando -> "Leyendo Letterboxd… (la primera vez tarda unos segundos)"
                    vm.lbMensaje != null -> vm.lbMensaje!!
                    else -> "${vm.lbPelis.size} películas · $tengo ya en tu biblioteca · ${vm.lbPelis.size - tengo} para bajar"
                },
                Modifier.padding(vertical = 6.dp), color = if (vm.lbMensaje != null) C.error else C.tenue,
            )
        }
        items(visibles, key = { it.url }) { p ->
            Item(
                p.titulo, p.anio + if (p.tengo) " · ✓ Ya la tenés" else "",
                { IconoTexto(if (p.tengo) "✔" else "🎬") },
                colorNombre = if (p.tengo) C.vista else C.texto,
                alTocar = { vm.hoja = opcionesLetterboxd(vm, contexto, p) },
            )
        }
    }
}

private fun copiar(contexto: Context, texto: String) {
    (contexto.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager)
        .setPrimaryClip(ClipData.newPlainText("TorrentVision", texto))
}

private fun opcionesLetterboxd(vm: Modelo, contexto: Context, p: PeliLb) = Hoja(
    "${p.titulo} (${p.anio})",
    listOf(
        Opcion("⬇ Bajarla") {
            val r = vm.lbBajar(p)
            if (r?.optBoolean("libre") == true) {
                vm.mostrarAviso(r.optString("aviso"), false)
                vm.cargarDescargas()
            } else if (r != null) {
                // No es de dominio público: se abre la búsqueda del torrent en el celular y se copia el título
                copiar(contexto, r.optString("texto"))
                abrirEnNavegador(contexto, r.optString("url"))
                vm.mostrarAviso("Tocá el link magnet y abrilo con TorrentVision: la PC lo baja sola", false)
            }
        },
        Opcion("💬 Buscar subtítulos") {
            val texto = "${p.titulo} ${p.anio}".trim()
            copiar(contexto, texto)
            abrirEnNavegador(contexto, "https://www.opensubtitles.org/es/search2/sublanguageid-spa/moviename-" + Uri.encode(texto))
        },
        Opcion("Ver en Letterboxd") { abrirEnNavegador(contexto, p.url) },
    ),
)

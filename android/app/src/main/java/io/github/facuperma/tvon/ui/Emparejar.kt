package io.github.facuperma.tvon.ui

import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.codescanner.GmsBarcodeScannerOptions
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning
import io.github.facuperma.tvon.Modelo

/** Abre el lector de QR de Google (no hace falta permiso de cámara) y usa lo que lea. */
fun escanear(contexto: Context, vm: Modelo) {
    val opciones = GmsBarcodeScannerOptions.Builder()
        .setBarcodeFormats(Barcode.FORMAT_QR_CODE)
        .enableAutoZoom()
        .build()
    GmsBarcodeScanning.getClient(contexto, opciones).startScan()
        .addOnSuccessListener { codigo -> codigo.rawValue?.let(vm::usarEnlace) }
        .addOnFailureListener { e ->
            vm.mostrarAviso("No se pudo abrir el lector de QR (${e.message}). Pegá el enlace a mano.", true)
        }
}

@Composable
fun PantallaEmparejar(vm: Modelo, mensaje: String?) {
    val contexto = LocalContext.current
    var enlace by rememberSaveable { mutableStateOf("") }
    // Atrás vuelve a la bienvenida (si no hay ninguna PC guardada)
    BackHandler(enabled = !vm.emparejando && vm.vinculo == null) { vm.volverABienvenida() }
    Column(
        Modifier
            .fillMaxSize()
            .systemBarsPadding()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 24.dp, vertical = 40.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Logo(96)
        TituloTVon(28)
        Text(mensaje ?: "Manejá TorrentVision desde el celular.", textAlign = TextAlign.Center,
            color = if (mensaje != null) C.error else C.texto)
        Tarjeta {
            Text("1. En la PC, abrí TorrentVision y tocá 📱 ON.", color = C.texto)
            Text("2. Encendelo y escaneá el código QR con este botón.", color = C.texto)
            Pista("El celular y la PC tienen que estar en la misma red wifi (o los dos en Tailscale).")
        }
        if (vm.emparejando) {
            CircularProgressIndicator(color = C.acento)
        } else {
            Boton("📷 Escanear el código QR", Modifier.fillMaxWidth(), Estilo.PRIMARIO) { escanear(contexto, vm) }
        }
        // Sin QR: se pide permiso a la PC y se aprueba allá, comparando un código
        val v = vm.vinculo
        if (v == null) {
            Boton("📡 Vincular sin QR (lo aprobás en la PC)", Modifier.fillMaxWidth()) { vm.vincularSinQr() }
        } else {
            Tarjeta {
                TituloTarjeta("📡 Vincular sin QR")
                if (v.codigo != null) {
                    Text(v.codigo, color = C.titulo, fontSize = 34.sp, fontWeight = FontWeight.Bold,
                        modifier = Modifier.align(Alignment.CenterHorizontally))
                }
                Text(v.mensaje, color = if (v.fallo) C.error else C.texto)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (v.fallo) Boton("Probar de nuevo", Modifier.weight(1f), Estilo.PRIMARIO) { vm.vincularSinQr() }
                    Boton(if (v.fallo) "Cerrar" else "Cancelar", Modifier.weight(1f)) { vm.cancelarVinculo() }
                }
            }
        }
        Pista("¿No anda la cámara? Pegá el enlace que aparece debajo del QR:")
        OutlinedTextField(
            enlace, { enlace = it }, Modifier.fillMaxWidth(), singleLine = true, colors = campoColores(),
            placeholder = { Text("https://192.168.…:8765/?c=…") },
        )
        Boton("Conectar", Modifier.fillMaxWidth(), habilitado = enlace.isNotBlank() && !vm.emparejando) {
            vm.usarEnlace(enlace)
        }
        Pista("🔒 Conexión cifrada: solo habla con tu PC.", Modifier.padding(top = 12.dp))
        Tarjeta(Modifier.padding(top = 12.dp)) {
            TituloTarjeta("¿No tenés una PC?")
            Pista("El celular puede bajar las películas, guardarlas con sus subtítulos y reproducirlas solo.")
            BotonVideoteca(vm, texto = "▶ Entrar a la app sin PC", preguntarAntes = false)
        }
    }
}

/** Primera pantalla sin nada vinculado: vincular la PC o entrar directo a la app (videoteca del celular). */
@Composable
fun PantallaBienvenida(vm: Modelo) {
    val contexto = LocalContext.current
    Column(
        Modifier
            .fillMaxSize()
            .systemBarsPadding()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 24.dp, vertical = 40.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Logo(110)
        TituloTVon(30)
        Text("Torrent para todos", color = C.texto, textAlign = TextAlign.Center)
        Tarjeta(Modifier.padding(top = 12.dp)) {
            TituloTarjeta("🖥 Tengo TorrentVision en la PC")
            Pista("En la PC tocá 📱 ON y escaneá el código: manejás todo desde el celular.")
            if (vm.emparejando) {
                CircularProgressIndicator(color = C.acento, modifier = Modifier.align(Alignment.CenterHorizontally))
            } else {
                Boton("📷 Escanear el código QR", Modifier.fillMaxWidth(), Estilo.PRIMARIO) { escanear(contexto, vm) }
            }
            Boton("Otras formas de vincular (sin QR)", Modifier.fillMaxWidth()) { vm.irAEmparejar() }
        }
        Tarjeta {
            TituloTarjeta("📱 Usar solo el celular")
            Pista("Bajá y mirá películas sin PC. Después podés vincular una.")
            BotonVideoteca(vm, texto = "▶ Entrar a la app", preguntarAntes = false)
        }
    }
}

@Composable
fun PantallaSinConexion(vm: Modelo, mensaje: String) {
    val contexto = LocalContext.current
    Column(
        Modifier
            .fillMaxSize()
            .systemBarsPadding()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 24.dp, vertical = 40.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Logo(96)
        TituloTVon(28)
        Text(mensaje, textAlign = TextAlign.Center, color = C.error)
        CircularProgressIndicator(color = C.acento)
        Pista("Se reintenta solo cada unos segundos.", Modifier.padding(bottom = 12.dp))
        Boton("Reintentar ahora", Modifier.fillMaxWidth()) { vm.correr { vm.conectar() } }
        Boton("📷 Escanear el código QR de nuevo", Modifier.fillMaxWidth(), Estilo.PRIMARIO) { escanear(contexto, vm) }
    }
}

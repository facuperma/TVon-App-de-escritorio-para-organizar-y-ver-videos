package io.github.facuperma.tvon.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.draw.alpha
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** Los colores de la app: salen del tema elegido (⚙ Apariencia), los mismos que en la PC. */
object C {
    var tema by mutableStateOf(TEMAS[0])
    var animada by mutableStateOf(true)

    val fondo get() = col(tema.fondo)
    val fondoHondo get() = col(tema.fondoHondo)
    val panel get() = col(tema.panel)
    val panelClaro get() = col(tema.panelClaro)
    val borde get() = col(tema.borde)
    val texto get() = col(tema.texto)
    val tenue get() = col(tema.tenue) // en el celular se lee a la luz del día: un poco más claro que en la PC
    val acento get() = col(tema.acento)
    val sobreAcento get() = col(tema.sobreAcento)
    val acentoClaro get() = if (tema.claro) lerpColor(acento, Color.Black, 0.25f) else lerpColor(acento, Color.White, 0.45f)
    /** Textos destacados (títulos): casi blanco en los temas oscuros, oscuro en los claros. */
    val titulo get() = if (tema.claro) col(tema.titulo) else lerpColor(col(tema.titulo), Color.White, 0.35f)
    val verde get() = if (tema.claro) Color(0xFF16803C) else Color(0xFF4ADE80)
    val vista get() = if (tema.claro) Color(0xFF16803C) else Color(0xFF86EFAC)
    val pendiente get() = if (tema.claro) Color(0xFFA15C00) else Color(0xFFFACC15)
    val peligro = Color(0xFFEF4444)
    val peligroFondo get() = if (tema.claro) Color(0xFFFDE2E2) else Color(0xFF5B1D1D)
    val peligroBorde get() = if (tema.claro) Color(0xFFD14343) else Color(0xFF8F2A2A)
    val peligroTexto get() = if (tema.claro) Color(0xFF8B1111) else Color(0xFFFFD4D4)
    val error get() = if (tema.claro) Color(0xFFC0262D) else Color(0xFFFF8080)
    val chipActivo get() = col(tema.seleccion)
    val esquina get() = tema.radio.dp
    val letra get() = tema.letra
}

@Composable
fun TemaTVon(contenido: @Composable () -> Unit) {
    val base = if (C.tema.claro) lightColorScheme() else darkColorScheme()
    val f = C.letra
    val letra = Typography().let { b ->
        Typography(
            bodyLarge = b.bodyLarge.copy(fontFamily = f), bodyMedium = b.bodyMedium.copy(fontFamily = f),
            bodySmall = b.bodySmall.copy(fontFamily = f), labelLarge = b.labelLarge.copy(fontFamily = f),
            labelMedium = b.labelMedium.copy(fontFamily = f), labelSmall = b.labelSmall.copy(fontFamily = f),
            titleLarge = b.titleLarge.copy(fontFamily = f), titleMedium = b.titleMedium.copy(fontFamily = f),
            titleSmall = b.titleSmall.copy(fontFamily = f), headlineSmall = b.headlineSmall.copy(fontFamily = f),
        )
    }
    MaterialTheme(
        colorScheme = base.copy(
            primary = C.acento, onPrimary = C.sobreAcento, background = C.fondo, onBackground = C.texto,
            surface = C.panel, onSurface = C.texto, surfaceVariant = C.panelClaro, onSurfaceVariant = C.tenue,
            surfaceContainerHigh = C.panel, surfaceContainerLow = C.panel, surfaceContainer = C.panel,
            outline = C.borde, error = C.peligro, secondaryContainer = C.chipActivo,
            onSecondaryContainer = C.titulo, surfaceContainerHighest = C.panelClaro,
        ),
        typography = letra,
    ) {
        // Sin esto, el texto que no está dentro de un Surface sale negro sobre el fondo azul marino
        CompositionLocalProvider(LocalContentColor provides C.texto, content = contenido)
    }
}

@Composable
fun Tarjeta(modifier: Modifier = Modifier, contenido: @Composable ColumnScope.() -> Unit) {
    Column(
        modifier
            .fillMaxWidth()
            .padding(vertical = 6.dp)
            .clip(RoundedCornerShape(C.esquina + 2.dp))
            .background(C.panel)
            .border(1.dp, C.borde, RoundedCornerShape(C.esquina + 2.dp))
            .padding(14.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
        content = contenido,
    )
}

@Composable
fun TituloTarjeta(texto: String, modifier: Modifier = Modifier, extra: @Composable RowScope.() -> Unit = {}) {
    Row(modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text(texto, color = C.titulo, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
        extra()
    }
}

@Composable
fun Pista(texto: String, modifier: Modifier = Modifier, color: Color = C.tenue) =
    Text(texto, color = color, fontSize = 13.sp, modifier = modifier)

enum class Estilo { NORMAL, PRIMARIO, PELIGRO }

@Composable
fun Boton(
    texto: String, modifier: Modifier = Modifier, estilo: Estilo = Estilo.NORMAL, habilitado: Boolean = true,
    chico: Boolean = false, alTocar: () -> Unit,
) {
    val t = C.tema
    val (fondo, borde, color) = when (estilo) {
        Estilo.PRIMARIO -> Triple(C.acento, C.acento, C.sobreAcento)
        Estilo.PELIGRO -> Triple(C.peligroFondo, C.peligroBorde, C.peligroTexto)
        Estilo.NORMAL -> Triple(C.panelClaro, col(t.botonBorde), col(t.botonTexto))
    }
    // Los botones comunes llevan el degradé del tema (gel, cromo, metal…); el primario, el acento con brillo
    val pincel = when {
        estilo == Estilo.NORMAL -> degrade(t.boton, t.brillo)
        estilo == Estilo.PRIMARIO && t.brillo -> brilloDe(C.acento)
        else -> null
    }
    val forma = RoundedCornerShape(C.esquina)
    Button(
        onClick = alTocar, enabled = habilitado,
        modifier = if (pincel != null) modifier.alpha(if (habilitado) 1f else .5f).background(pincel, forma) else modifier,
        shape = forma,
        border = BorderStroke(if (t.id == "noventa") 2.dp else 1.dp, borde),
        colors = ButtonDefaults.buttonColors(
            containerColor = if (pincel != null) Color.Transparent else fondo, contentColor = color,
            disabledContainerColor = if (pincel != null) Color.Transparent else fondo.copy(alpha = .4f),
            disabledContentColor = color.copy(alpha = .6f),
        ),
        contentPadding = if (chico) PaddingValues(horizontal = 10.dp, vertical = 4.dp) else PaddingValues(horizontal = 14.dp, vertical = 10.dp),
    ) {
        Text(texto, fontSize = if (chico) 13.sp else 15.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
}

@Composable
fun Redondo(
    texto: String, modifier: Modifier = Modifier, grande: Boolean = false, habilitado: Boolean = true, alTocar: () -> Unit,
) {
    val lado = if (grande) 72.dp else 52.dp
    Button(
        onClick = alTocar, enabled = habilitado, modifier = modifier.size(lado), shape = CircleShape,
        contentPadding = PaddingValues(0.dp),
        border = BorderStroke(1.dp, if (grande) C.acento else C.borde),
        colors = ButtonDefaults.buttonColors(
            containerColor = if (grande) C.acento else C.panelClaro, contentColor = if (grande) C.sobreAcento else C.texto,
            disabledContainerColor = C.panelClaro.copy(alpha = .4f), disabledContentColor = C.tenue,
        ),
    ) { Text(texto, fontSize = if (grande) 28.sp else 16.sp, maxLines = 1) }
}

@Composable
fun Interruptor(texto: String, activo: Boolean, modifier: Modifier = Modifier, alCambiar: (Boolean) -> Unit) {
    Row(modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text(texto, modifier = Modifier.weight(1f))
        Switch(
            checked = activo, onCheckedChange = alCambiar,
            colors = SwitchDefaults.colors(checkedTrackColor = C.verde, checkedThumbColor = Color.White),
        )
    }
}

@Composable
fun Chip(texto: String, activo: Boolean = false, modifier: Modifier = Modifier, alTocar: () -> Unit) {
    Box(
        modifier
            .clip(RoundedCornerShape(20.dp))
            .background(if (activo) C.chipActivo else C.panel)
            .border(1.dp, if (activo) C.acento else C.borde, RoundedCornerShape(20.dp))
            .clickable(onClick = alTocar)
            .padding(horizontal = 12.dp, vertical = 7.dp),
    ) { Text(texto, color = if (activo) C.titulo else C.texto, fontSize = 14.sp, maxLines = 1) }
}

/** Una fila de lista: ícono, nombre, renglón chico y lo que vaya a la derecha. */
@OptIn(ExperimentalFoundationApi::class)
@Composable
fun Item(
    nombre: String,
    sub: String = "",
    icono: @Composable () -> Unit = {},
    colorNombre: Color = C.texto,
    elegido: Boolean = false,
    tenue: Boolean = false,
    alTocar: (() -> Unit)? = null,
    alMantener: (() -> Unit)? = null,
    abajo: @Composable ColumnScope.() -> Unit = {},
    derecha: @Composable RowScope.() -> Unit = {},
) {
    val vibrar = LocalHapticFeedback.current
    Row(
        Modifier
            .fillMaxWidth()
            .padding(vertical = 3.dp)
            .clip(RoundedCornerShape(C.esquina))
            .background(if (elegido) C.chipActivo else C.panel)
            .border(1.dp, if (elegido) C.acento else C.borde, RoundedCornerShape(C.esquina))
            .then(
                if (alTocar != null || alMantener != null) Modifier.combinedClickable(
                    onClick = { alTocar?.invoke() },
                    onLongClick = alMantener?.let { { vibrar.performHapticFeedback(HapticFeedbackType.LongPress); it() } },
                ) else Modifier
            )
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Box(Modifier.width(36.dp), contentAlignment = Alignment.Center) { icono() }
        Column(Modifier.weight(1f)) {
            Text(nombre, color = if (tenue) C.tenue else colorNombre, maxLines = 2, overflow = TextOverflow.Ellipsis)
            if (sub.isNotEmpty()) Text(sub, color = C.tenue, fontSize = 12.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
            abajo()
        }
        derecha()
    }
}

@Composable
fun IconoTexto(texto: String) = Text(texto, fontSize = 22.sp)

@Composable
fun Progreso(fraccion: Float) {
    Box(
        Modifier
            .padding(top = 6.dp)
            .fillMaxWidth()
            .height(5.dp)
            .clip(RoundedCornerShape(3.dp))
            .background(C.fondoHondo)
    ) {
        Box(
            Modifier
                .fillMaxWidth(fraccion.coerceIn(0f, 1f))
                .height(5.dp)
                .background(C.acento)
        )
    }
}

@Composable
fun campoColores() = OutlinedTextFieldDefaults.colors(
    focusedBorderColor = C.acento, unfocusedBorderColor = C.borde,
    focusedContainerColor = C.fondoHondo, unfocusedContainerColor = C.fondoHondo,
)

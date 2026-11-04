package io.github.facuperma.tvon.ui

import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily

/**
 * Los mismos temas que la app de escritorio (temas.py): el azul de siempre y once estilos retro de los 2000.
 * Inspirados en esa época, con diseños propios.
 */
data class TemaCel(
    val id: String,
    val nombre: String,
    val epoca: String,
    val descripcion: String,
    val animacion: String,
    val fondo: Long, val fondoHondo: Long, val panel: Long, val panelClaro: Long, val borde: Long,
    val texto: Long, val tenue: Long, val acento: Long, val sobreAcento: Long, val seleccion: Long, val titulo: Long,
    val barra: List<Long>,          // degradé de la barra de arriba
    val boton: List<Long>,          // degradé de los botones (dos colores = brillo de gel)
    val botonBorde: Long, val botonTexto: Long,
    val lcdFondo: Long, val lcdTexto: Long,
    val radio: Int = 10,
    val letra: FontFamily = FontFamily.SansSerif,
    val claro: Boolean = false,
    val brillo: Boolean = false,    // botones con la mitad de arriba más clara
)

fun col(v: Long) = Color(v)

/** Degradé vertical; con brillo, corte duro a la mitad como los botones de gel. */
fun degrade(colores: List<Long>, brillo: Boolean = false): Brush =
    if (colores.size == 1) Brush.verticalGradient(listOf(col(colores[0]), col(colores[0])))
    else if (brillo && colores.size == 2) Brush.verticalGradient(
        0f to col(colores[0]), 0.49f to lerpColor(col(colores[0]), col(colores[1]), 0.35f),
        0.5f to col(colores[1]), 1f to lerpColor(col(colores[1]), Color.Black, 0.15f),
    )
    else Brush.verticalGradient(colores.map { col(it) })

/** El brillo de gel sobre un solo color: arriba más claro, corte a la mitad, abajo el color. */
fun brilloDe(c: Color): Brush = Brush.verticalGradient(
    0f to lerpColor(c, Color.White, 0.55f), 0.49f to lerpColor(c, Color.White, 0.25f), 0.5f to c, 1f to lerpColor(c, Color.Black, 0.2f),
)

fun lerpColor(a: Color, b: Color, f: Float) =
    Color(a.red + (b.red - a.red) * f, a.green + (b.green - a.green) * f, a.blue + (b.blue - a.blue) * f, 1f)

val TEMAS = listOf(
    TemaCel("marino", "Azul noche", "TorrentVision", "El de siempre: azul marino, prolijo y tranquilo.", "ninguna",
        0xFF0F1729, 0xFF0A1020, 0xFF131D33, 0xFF1F2D4D, 0xFF24334F, 0xFFDBE2EF, 0xFF97A3B8, 0xFF3D7BFD, 0xFFFFFFFF,
        0xFF1F3566, 0xFFFFFFFF, listOf(0xFF131D33), listOf(0xFF1F2D4D), 0xFF24334F, 0xFFDBE2EF, 0xFF0A1020, 0xFF9FC2FF),
    TemaCel("galaxia", "Galaxia P2P", "Programas para compartir de 2004",
        "Azul profundo con estrellas que pasan, botones de cristal celeste y la marquesina con lo que estás viendo.",
        "estrellas", 0xFF070D1F, 0xFF030714, 0xFF0D1833, 0xFF15284F, 0xFF1F3B70, 0xFFD6E6FF, 0xFF8AA2CC, 0xFF2FB4FF,
        0xFF001022, 0xFF1D5FB0, 0xFF8FD8FF, listOf(0xFF1B3A78, 0xFF0B1838, 0xFF050B1E), listOf(0xFF3D74C9, 0xFF173A7A),
        0xFF4B86E0, 0xFFFFFFFF, 0xFF020611, 0xFF4FD2FF, radio = 12, brillo = true),
    TemaCel("llama", "Lámpara de llama", "Reproductores con skins de 1999",
        "Gris metálico, pantallita LCD verde con el título corriendo y un ecualizador que salta.", "ecualizador",
        0xFF23232B, 0xFF14141A, 0xFF2D2D38, 0xFF3C3C4A, 0xFF55556A, 0xFFD8D8E0, 0xFF9A9AB0, 0xFF3CD63C, 0xFF000000,
        0xFF24456E, 0xFF00E000, listOf(0xFF4A4A5C, 0xFF2A2A36, 0xFF1C1C24), listOf(0xFF5A5A6E, 0xFF383846),
        0xFF76768E, 0xFFE6E6EE, 0xFF000000, 0xFF00E000, radio = 3, letra = FontFamily.Monospace),
    TemaCel("luna", "Luna", "El escritorio de 2001",
        "Ventanas beige, barra azul brillante y botones redondeados. Arriba, el cielo con nubes y la loma verde.",
        "nubes", 0xFFECE9D8, 0xFFFFFFFF, 0xFFF6F4EA, 0xFFFFFFFF, 0xFF7F9DB9, 0xFF000000, 0xFF5A5A5A, 0xFF316AC5,
        0xFFFFFFFF, 0xFFC1D2EE, 0xFF0A246A, listOf(0xFF3D95FF, 0xFF0A5FD8, 0xFF0050C8), listOf(0xFFFFFFFF, 0xFFD6D0C5),
        0xFF003C74, 0xFF000000, 0xFF0A5FD8, 0xFFFFFFFF, radio = 6, claro = true),
    TemaCel("gel", "Gel azul", "Las computadoras transparentes de 2000",
        "Gris perla con botones de gel azul que brillan como caramelo y gotas que respiran.", "gotas",
        0xFFE9EAEE, 0xFFF7F7F9, 0xFFF2F2F5, 0xFFFFFFFF, 0xFFA9AEBB, 0xFF111111, 0xFF5F6470, 0xFF1F7AE0, 0xFFFFFFFF,
        0xFFD7E6FA, 0xFF0B3F8C, listOf(0xFFFBFBFC, 0xFFDCDEE4, 0xFFC9CCD4), listOf(0xFFCFE6FF, 0xFF2B84EE),
        0xFF1D5FB8, 0xFF06224D, 0xFFDFE9F5, 0xFF0B3F8C, radio = 16, claro = true, brillo = true),
    TemaCel("cristal", "Cristal negro", "El reproductor de vidrio de 2006",
        "Negro brillante como un piano, reflejos de vidrio y una aurora azul que ondula.", "aurora",
        0xFF0B0B0D, 0xFF000000, 0xFF141418, 0xFF202027, 0xFF2E2E38, 0xFFE8ECF2, 0xFF9AA1AE, 0xFF3FA9F5, 0xFF00121F,
        0xFF1B4F7A, 0xFFBFE3FF, listOf(0xFF3A3A44, 0xFF1C1C22, 0xFF08080A), listOf(0xFF4A4A56, 0xFF0E0E12),
        0xFF50505E, 0xFFF0F4FA, 0xFF000000, 0xFF7CC8FF, radio = 12, brillo = true),
    TemaCel("plata", "Plata cepillada", "La jukebox de metal de 2003",
        "Aluminio cepillado con una pantallita verde agua, como los reproductores de música de esa época.", "brillo",
        0xFFD9D9D9, 0xFFF2F2F2, 0xFFE4E4E4, 0xFFF7F7F7, 0xFF8C8C8C, 0xFF1A1A1A, 0xFF5C5C5C, 0xFF5D7FA8, 0xFFFFFFFF,
        0xFFCFD6DF, 0xFF202020, listOf(0xFFF0F0F0, 0xFFC8C8C8, 0xFFB2B2B2), listOf(0xFFFAFAFA, 0xFFBDBDBD),
        0xFF7A7A7A, 0xFF111111, 0xFFD4E2C4, 0xFF1D2B14, radio = 9, claro = true),
    TemaCel("mula", "Mula verde", "Las redes de intercambio de 2003",
        "Blanco y verde, amigable, con flechitas que suben y bajan como en las transferencias de antes.", "flechas",
        0xFFF3F8F1, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0xFF9CC59A, 0xFF13301A, 0xFF557A5C, 0xFF2E9E4F, 0xFFFFFFFF,
        0xFFDCEFDC, 0xFF1F6B35, listOf(0xFFE9F6E6, 0xFFC4E3BF, 0xFFA8D4A1), listOf(0xFFFFFFFF, 0xFFCFE9CA),
        0xFF5AA65F, 0xFF133A1C, 0xFF103B1D, 0xFFA8FF9E, radio = 8, claro = true, brillo = true),
    TemaCel("fosforo", "Fósforo", "Los monitores de tubo",
        "Negro absoluto y letras verde fósforo, líneas de barrido y una lluvia de letras.", "lluvia",
        0xFF030A04, 0xFF000000, 0xFF06110A, 0xFF0B1D10, 0xFF145A26, 0xFF39FF6A, 0xFF22B04C, 0xFF39FF6A, 0xFF001A06,
        0xFF0F4D20, 0xFF9CFFB5, listOf(0xFF020703), listOf(0xFF04140A), 0xFF1FA748, 0xFF5CFF86, 0xFF000000, 0xFF39FF6A,
        radio = 0, letra = FontFamily.Monospace),
    TemaCel("neon", "Neón Y2K", "El cambio de milenio",
        "Violeta, fucsia y cian con cromo, y la grilla infinita hacia un sol de atardecer.", "grilla",
        0xFF14062B, 0xFF0A0218, 0xFF1E0A3D, 0xFF2C1257, 0xFF5B2A9E, 0xFFF3E6FF, 0xFFB79BE0, 0xFFFF2FD6, 0xFF1A0024,
        0xFF7A1FA8, 0xFF22E4FF, listOf(0xFF3A0D6E, 0xFF1A0640), listOf(0xFFF4F4FF, 0xFF7D7DA8),
        0xFF22E4FF, 0xFF1A0033, 0xFF0A0218, 0xFF22E4FF, radio = 18, brillo = true),
    TemaCel("aero", "Burbujas Aero", "El optimismo de 2007",
        "Cielo celeste, verde agua y vidrio con brillo; burbujas que suben.", "burbujas",
        0xFFE6F4FB, 0xFFFFFFFF, 0xFFF4FBFF, 0xFFFFFFFF, 0xFF8FC7E3, 0xFF0B3247, 0xFF4F7A8F, 0xFF1BA3D6, 0xFFFFFFFF,
        0xFFD2EEF9, 0xFF0A6C8F, listOf(0xFFBFE8FB, 0xFF7FCFF2, 0xFF55C2A8), listOf(0xFFFFFFFF, 0xFF9FDCF2),
        0xFF3AA7CF, 0xFF063246, 0xFF0D6F93, 0xFFE9FBFF, radio = 20, claro = true, brillo = true),
    TemaCel("noventa", "Escritorio 98", "Las ventanas grises de 1998",
        "Gris clásico con botones en relieve, barra azul marino y el protector de pantalla de estrellas.", "warp",
        0xFFC0C0C0, 0xFFFFFFFF, 0xFFC0C0C0, 0xFFFFFFFF, 0xFF808080, 0xFF000000, 0xFF404040, 0xFF000080, 0xFFFFFFFF,
        0xFFB4C8F0, 0xFF000080, listOf(0xFF000080, 0xFF1084D0), listOf(0xFFC0C0C0), 0xFF404040, 0xFF000000,
        0xFF000000, 0xFFFFFFFF, radio = 0, claro = true),
)

fun temaPorId(id: String?) = TEMAS.firstOrNull { it.id == id } ?: TEMAS[0]

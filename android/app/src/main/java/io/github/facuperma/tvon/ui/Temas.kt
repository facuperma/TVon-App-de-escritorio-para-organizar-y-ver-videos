package io.github.facuperma.tvon.ui

import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
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
    // Segunda tanda (las mismas de la PC)
    TemaCel("casete", "Casete 85", "Los walkman y los casetes de los 80",
        "Beige, naranja y marrón de cinta, con un casete girando arriba.", "casete",
        0xFFEFE3C8, 0xFFFBF4E4, 0xFFF6EAD2, 0xFFFFFAF0, 0xFFB98C55, 0xFF3B2414, 0xFF7A5A3C, 0xFFE0661F, 0xFFFFFFFF,
        0xFFF1D9B5, 0xFF8A3A10, listOf(0xFF3B2414, 0xFF6B3D1E), listOf(0xFFFFF7E6, 0xFFE8CFA6), 0xFF9B6A3A, 0xFF3B2414,
        0xFF2A1A10, 0xFFFFB347, radio = 14, claro = true),
    TemaCel("vinilo", "Disquería", "Los tocadiscos y la madera",
        "Madera oscura, dorado y un vinilo que gira con la púa encima.", "vinilo",
        0xFF1C120C, 0xFF0F0905, 0xFF2A1B12, 0xFF3A2618, 0xFF6B4A2A, 0xFFF1E2C8, 0xFFC4A580, 0xFFD4A24C, 0xFF1C120C,
        0xFF7A5222, 0xFFF3C771, listOf(0xFF5A3820, 0xFF24160C), listOf(0xFF4A3220, 0xFF24160C), 0xFFD4A24C, 0xFFF3E3C2,
        0xFF0F0905, 0xFFF3C771, radio = 24, letra = FontFamily.Serif, brillo = true),
    TemaCel("arcade", "Arcade 8 bits", "Los fichines de los 80",
        "Negro de sala de juegos, colores chillones y marcianitos marchando.", "pixeles",
        0xFF0A0A14, 0xFF000000, 0xFF11112A, 0xFF1C1C40, 0xFFFF2E88, 0xFFF2F2FF, 0xFF9F9FD8, 0xFFFFE14D, 0xFF14002A,
        0xFFFF2E88, 0xFF3CF2FF, listOf(0xFF000000), listOf(0xFF14143A), 0xFF3CF2FF, 0xFFFFE14D, 0xFF000000, 0xFFFFE14D,
        radio = 0, letra = FontFamily.Monospace),
    TemaCel("osciloscopio", "Osciloscopio", "Los aparatos de laboratorio",
        "Gris verdoso de instrumento y la onda verde que se dibuja en la pantalla.", "osciloscopio",
        0xFF1D2420, 0xFF111613, 0xFF252E29, 0xFF303B35, 0xFF4D5D53, 0xFFD6E6DC, 0xFF9FB7AA, 0xFF7CFF9A, 0xFF06210F,
        0xFF2F5A3D, 0xFFA6FFBB, listOf(0xFF3A4640, 0xFF1A201C), listOf(0xFF46534C, 0xFF2E3833), 0xFF7A8C82, 0xFFE2F0E7,
        0xFF06140B, 0xFF7CFF9A, radio = 3),
    TemaCel("oceano", "Océano", "Los protectores de pantalla de peces",
        "Azul profundo, turquesa y olas que van y vienen con burbujas.", "olas",
        0xFF06243A, 0xFF031624, 0xFF0A3150, 0xFF114268, 0xFF1F6F96, 0xFFD8F3FF, 0xFF8FC3DC, 0xFF2FE0D0, 0xFF022A26,
        0xFF147A9C, 0xFF9CF1FF, listOf(0xFF0E5A86, 0xFF04243A), listOf(0xFF3AA3D0, 0xFF0D4F75), 0xFF5FD6E8, 0xFFFFFFFF,
        0xFF031624, 0xFF9CF1FF, radio = 22, brillo = true),
    TemaCel("fuego", "Fuego", "Las visualizaciones de música de 2000",
        "Negro con brasas: llamas que crecen con lo que suena.", "fuego",
        0xFF140604, 0xFF080201, 0xFF200A06, 0xFF33100A, 0xFF7A2310, 0xFFFFE6D6, 0xFFE09A7A, 0xFFFF6A1A, 0xFF1A0500,
        0xFFA8320F, 0xFFFFC04D, listOf(0xFF3A0A04, 0xFF7A1A08), listOf(0xFFFF9A4D, 0xFFA8320F), 0xFFFFC04D, 0xFF1A0500,
        0xFF080201, 0xFFFFC04D, radio = 16, brillo = true),
    TemaCel("caramelo", "Caramelo", "Las computadoras de colores de 1999",
        "Rosa chicle y blanco, todo redondo como un caramelo, con corazones flotando.", "corazones",
        0xFFFFE8F3, 0xFFFFF6FB, 0xFFFFF0F7, 0xFFFFFFFF, 0xFFF29AC4, 0xFF4A0F2C, 0xFFA3567B, 0xFFFF3D8B, 0xFFFFFFFF,
        0xFFFFD6EA, 0xFFC2185B, listOf(0xFFFFD1E6, 0xFFFF6FA8), listOf(0xFFFFFFFF, 0xFFFF9EC9), 0xFFFF3D8B, 0xFF4A0F2C,
        0xFFFF3D8B, 0xFFFFFFFF, radio = 26, claro = true, brillo = true),
    TemaCel("teletexto", "Teletexto", "Las páginas de texto de la tele",
        "Negro y los siete colores puros de la tele, en bloques, con el número de página.", "teletexto",
        0xFF000000, 0xFF000000, 0xFF000000, 0xFF0A0A0A, 0xFF0000FF, 0xFFFFFFFF, 0xFF00FFFF, 0xFFFFFF00, 0xFF000000,
        0xFF0000FF, 0xFFFFFF00, listOf(0xFF0000FF), listOf(0xFF000000), 0xFF00FF00, 0xFF00FFFF, 0xFF000000, 0xFFFFFF00,
        radio = 0, letra = FontFamily.Monospace),
    TemaCel("radio", "Radio a válvulas", "Las radios de madera con dial",
        "Nogal, bronce y un dial ámbar con la aguja buscando emisoras.", "dial",
        0xFF2B1A10, 0xFF1A0F08, 0xFF3A2416, 0xFF4A301D, 0xFF8A6038, 0xFFF5E3C4, 0xFFD4B08A, 0xFFFFB84D, 0xFF2B1A10,
        0xFF8A5A28, 0xFFFFCF7A, listOf(0xFF6A4224, 0xFF2B1A10), listOf(0xFFC8A06A, 0xFF7A5430), 0xFFFFCF7A, 0xFF2B1A10,
        0xFF3A2008, 0xFFFFCF7A, radio = 20, letra = FontFamily.Serif, brillo = true),
    TemaCel("vhs", "Videoclub", "Los casetes de video y el «PLAY»",
        "Azul de pantalla de video, letras blancas y franjas de tracking.", "vhs",
        0xFF0B1A8A, 0xFF06106A, 0xFF0F22A0, 0xFF1630B8, 0xFF5A74FF, 0xFFFFFFFF, 0xFFC6D0FF, 0xFFFFFFFF, 0xFF0B1A8A,
        0xFF3F5CFF, 0xFFFFFFFF, listOf(0xFF06106A, 0xFF0B1A8A), listOf(0xFF0B1A8A), 0xFFFFFFFF, 0xFFFFFFFF,
        0xFF06106A, 0xFFFFFFFF, radio = 2, letra = FontFamily.Monospace),
)

fun temaPorId(id: String?) = TEMAS.firstOrNull { it.id == id } ?: TEMAS[0]

private val estadosCalculados = mutableMapOf<String, Pair<Color, Color>>()

/** (a medias, vista) del tema: el primer tono que no se confunda con el texto, con contraste 4.5:1 sobre el fondo. */
fun estados(t: TemaCel): Pair<Color, Color> = estadosCalculados.getOrPut(t.id) {
    val pendiente = colorEstado(t, listOf(48f, 32f, 320f), null)
    pendiente to colorEstado(t, listOf(140f, 190f, 215f), pendiente)
}

private fun colorEstado(t: TemaCel, tonos: List<Float>, evitar: Color?): Color {
    val hsv = FloatArray(3)
    android.graphics.Color.colorToHSV(t.texto.toInt(), hsv)
    val textoTono = hsv[0]
    val textoVivo = hsv[1] * hsv[2]
    val evitarTono = evitar?.let { e -> FloatArray(3).also { android.graphics.Color.colorToHSV(e.toArgb(), it) }[0] }
    fun lejos(a: Float, b: Float): Boolean { val d = kotlin.math.abs(a - b) % 360; return minOf(d, 360 - d) >= 40 }
    val elegido = tonos.firstOrNull { (textoVivo < 0.4f || lejos(it, textoTono)) && (evitarTono == null || lejos(it, evitarTono)) }
        ?: tonos.last()
    val fondos = listOf(t.panel.toInt(), t.fondo.toInt())
    val oscuro = androidx.core.graphics.ColorUtils.calculateLuminance(t.panel.toInt()) < 0.2
    for (i in 0 until 12) {
        val luz = (if (oscuro) 0.62f + i * 0.03f else 0.42f - i * 0.03f).coerceIn(0.05f, 0.95f)
        val c = androidx.core.graphics.ColorUtils.HSLToColor(floatArrayOf(elegido, 0.9f, luz))
        if (fondos.all { androidx.core.graphics.ColorUtils.calculateContrast(c, it or 0xFF000000.toInt()) >= 4.5 }) return Color(c)
    }
    return Color(androidx.core.graphics.ColorUtils.HSLToColor(floatArrayOf(elegido, 0.9f, if (oscuro) 0.9f else 0.15f)))
}

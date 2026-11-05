package io.github.facuperma.tvon.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.basicMarquee
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.clipRect
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.facuperma.tvon.Modelo
import kotlin.math.abs
import kotlin.math.sin

/**
 * La banda de los temas retro: una pantallita con el título que corre (marquesina) y la animación del tema
 * (estrellas, ecualizador, nubes, aurora, lluvia, grilla de neón…), igual que en la PC.
 */
@OptIn(ExperimentalFoundationApi::class)
@Composable
fun BandaRetro(titulo: String, sonando: Boolean, modifier: Modifier = Modifier) {
    val t = C.tema
    if (t.animacion == "ninguna") return
    var tiempo by remember { mutableFloatStateOf(0f) }
    if (C.animada) {
        LaunchedEffect(t.id) {
            val inicio = withFrameNanos { it }
            while (true) withFrameNanos { tiempo = (it - inicio) / 1e9f }
        }
    }
    val lcd = col(t.lcdTexto)
    Box(modifier.fillMaxWidth().height(32.dp).background(col(t.lcdFondo))) {
        Canvas(Modifier.matchParentSize()) { dibujar(t.animacion, tiempo, sonando) }
        Box(
            Modifier.padding(4.dp).fillMaxHeight().fillMaxWidth(0.56f)
                .clip(RoundedCornerShape(minOf(t.radio, 6).dp))
                .background(col(t.lcdFondo).copy(alpha = .86f))
                .border(1.dp, lcd.copy(alpha = .5f), RoundedCornerShape(minOf(t.radio, 6).dp)),
            contentAlignment = Alignment.CenterStart,
        ) {
            Text(
                (if (sonando) "▶ " else "❚❚ ") + titulo.ifEmpty { "TorrentVision · Torrent para todos" },
                color = lcd, fontSize = 12.sp, fontWeight = FontWeight.Bold, maxLines = 1, softWrap = false,
                fontFamily = C.letra,
                modifier = Modifier.padding(horizontal = 8.dp).let { if (C.animada) it.basicMarquee(iterations = Int.MAX_VALUE) else it },
                overflow = if (C.animada) TextOverflow.Clip else TextOverflow.Ellipsis,
            )
        }
    }
}

/** Número «al azar» pero fijo para cada índice (así las estrellas no saltan de un cuadro a otro). */
private fun azar(i: Int): Float {
    val x = sin(i * 12.9898f + 78.233f) * 43758.547f
    return x - kotlin.math.floor(x)
}

private fun DrawScope.dibujar(animacion: String, t: Float, sonando: Boolean) {
    val w = size.width
    val h = size.height
    when (animacion) {
        "estrellas" -> {
            drawRect(Brush.verticalGradient(listOf(Color(0xFF0B1F4A), Color(0xFF020611))))
            for (i in 0 until 70) {
                val capa = i % 3
                val vel = 12f + capa * 22f
                val x = ((azar(i) * w - t * vel) % w + w) % w
                val y = azar(i + 300) * h
                val brillo = 0.45f + 0.55f * abs(sin(t * 2.5f + i))
                drawCircle(Color(0xFFC8E6FF).copy(alpha = brillo * (0.4f + capa * 0.3f)), 1f + capa * 0.9f, Offset(x, y))
            }
            val fase = (t % 6f) / 6f
            if (fase < 0.12f) {
                val x = w * (1 - fase / 0.12f)
                drawLine(Color(0xCC8FD8FF), Offset(x, 4 + fase * 60), Offset(x + 50, fase * 60), 2f)
            }
        }
        "warp" -> {
            drawRect(Color.Black)
            val cx = w * 0.78f
            val cy = h / 2
            for (i in 0 until 90) {
                val z = 1f - ((t * 0.35f + azar(i)) % 1f)
                val x = cx + (azar(i + 500) * 2 - 1) / z.coerceAtLeast(.05f) * w * 0.06f
                val y = cy + (azar(i + 900) * 2 - 1) / z.coerceAtLeast(.05f) * h * 0.5f
                if (x in 0f..w && y in 0f..h) {
                    val g = (1 - z).coerceIn(0f, 1f)
                    drawCircle(Color.White.copy(alpha = g), 0.6f + g * 2f, Offset(x, y))
                }
            }
        }
        "ecualizador" -> {
            val n = 22
            val x0 = w * 0.6f
            val ancho = (w - x0 - 8) / n
            for (i in 0 until n) {
                val alto = if (sonando) abs(sin(t * (1.3f + i * 0.17f) + i)) * (1 - i / (n * 1.6f)) *
                    (0.6f + 0.4f * abs(sin(t * 7 + i * 3))) else 0.06f
                val bloques = (alto * 8).toInt()
                for (b in 0 until bloques) {
                    val color = when {
                        b < 4 -> Color(0xFF00E000)
                        b < 6 -> Color(0xFFE0E000)
                        else -> Color(0xFFFF3B1F)
                    }
                    drawRect(color, Offset(x0 + i * ancho, h - 4 - (b + 1) * (h - 6) / 8f), Size(ancho - 2, (h - 6) / 8f - 1))
                }
            }
        }
        "nubes" -> {
            drawRect(Brush.verticalGradient(listOf(Color(0xFF3A8CE8), Color(0xFF9FD0FF))))
            for (i in 0 until 6) {
                val r = 14f + azar(i) * 18f
                val x = ((azar(i + 40) * w + t * (8 + i * 3)) % (w + 4 * r)) - 2 * r
                val y = 4 + azar(i + 80) * h * 0.4f + r * 0.3f
                for ((dx, dy, f) in listOf(Triple(0f, 0f, 1f), Triple(r * .7f, 2f, .8f), Triple(-r * .6f, 3f, .7f))) {
                    drawOval(Color.White.copy(alpha = .85f), Offset(x + dx - r * .5f * f, y + dy - r * .22f * f), Size(r * f, r * .44f * f))
                }
            }
            val loma = Path().apply {
                moveTo(w * .45f, h)
                cubicTo(w * .6f, h * .35f, w * .82f, h * .2f, w, h * .45f)
                lineTo(w, h); close()
            }
            drawPath(loma, Brush.verticalGradient(listOf(Color(0xFF6FCF3A), Color(0xFF2C8A13)), h * .3f, h))
        }
        "gotas" -> {
            drawRect(Brush.verticalGradient(listOf(Color(0xFFF4F6FA), Color(0xFFD3D8E2))))
            var y = 0f
            while (y < h) { drawLine(Color.White.copy(alpha = .5f), Offset(0f, y), Offset(w, y), 1f); y += 3f }
            val n = 6
            for (i in 0 until n) {
                val x = w * .6f + (w * .4f) * (i + .5f) / n
                val r = 7f + 3f * sin(t * 1.6f + i * 1.3f) + 3f
                drawCircle(Brush.radialGradient(listOf(Color(0xFFE8F4FF), Color(0xFF5AA8FF), Color(0xFF0B4FBF)),
                    Offset(x - r * .3f, h / 2 - r * .4f), r * 1.4f), r, Offset(x, h / 2))
                drawOval(Color.White.copy(alpha = .7f), Offset(x - r * .6f, h / 2 - r * .75f), Size(r * .9f, r * .45f))
            }
        }
        "aurora" -> {
            drawRect(Color.Black)
            val fuerza = if (sonando) 1f else .5f
            listOf(Triple(Color(0xFF3FA9F5), 0f, .32f), Triple(Color(0xFF7A5CFF), 1.7f, .24f), Triple(Color(0xFF39E6D0), 3.1f, .18f))
                .forEachIndexed { k, (color, fase, alto) ->
                    val camino = Path()
                    var x = 0f
                    while (x <= w + 8) {
                        val y = h / 2 + sin(x / 70f + t * (1.1f + k * .4f) + fase) * h * alto * fuerza + sin(x / 23f + t * 2.3f) * 2
                        if (x == 0f) camino.moveTo(0f, y) else camino.lineTo(x, y)
                        x += 8f
                    }
                    for ((grosor, alfa) in listOf(7f to .16f, 3f to .45f, 1.2f to 1f)) {
                        drawPath(camino, color.copy(alpha = alfa), style = Stroke(grosor, cap = StrokeCap.Round))
                    }
                }
        }
        "brillo" -> {
            drawRect(Brush.verticalGradient(listOf(Color(0xFFF2F2F2), Color(0xFFC4C4C4), Color(0xFFDADADA))))
            for (i in 0 until h.toInt() step 2) drawLine(Color.White.copy(alpha = .25f + azar(i) * .2f), Offset(0f, i.toFloat()), Offset(w, i.toFloat()), 1f)
            val x = (t * 160f) % (w + 300f) - 150f
            drawRect(Brush.horizontalGradient(listOf(Color.Transparent, Color.White.copy(alpha = .6f), Color.Transparent), x - 80, x + 80),
                Offset(x - 80, 0f), Size(160f, h))
            for (i in 0 until 18) {
                val amp = if (sonando) abs(sin(t * 4 + i * .6f)) * h * .5f + 3 else 3f
                val xx = w - 14 - i * 7f
                drawLine(Color(0xFF5D7FA8), Offset(xx, h / 2 - amp / 2), Offset(xx, h / 2 + amp / 2), 3f, StrokeCap.Round)
            }
        }
        "flechas" -> {
            drawRect(Color(0xFF0F2F18))
            val x0 = w * .6f
            var i = 0
            var x = x0 + 10
            while (x < w) {
                val baja = i % 3 != 2
                val vel = 18f + (i * 7) % 11
                var y = (t * vel + i * 13) % (h + 16) - 8
                if (!baja) y = h - y
                val color = if (baja) Color(0xFF7DFF6E) else Color(0xFF6EC8FF)
                val punta = Path().apply {
                    if (baja) { moveTo(x, y + 6); lineTo(x - 5, y); lineTo(x + 5, y) } else { moveTo(x, y - 6); lineTo(x - 5, y); lineTo(x + 5, y) }
                    close()
                }
                drawPath(punta, color)
                drawRect(color.copy(alpha = .6f), Offset(x - 1.5f, if (baja) y - 8 else y), Size(3f, 8f))
                x += 24f
                i++
            }
        }
        "lluvia" -> {
            drawRect(Color.Black)
            val paso = 9f
            var c = 0
            var x = 0f
            while (x < w) {
                val vel = 40f + azar(c) * 60f
                val cabeza = (t * vel + azar(c + 50) * h * 2) % (h + 60f)
                for (k in 0 until 6) {
                    val y = cabeza - k * 8
                    if (y in -8f..h) {
                        val color = if (k == 0) Color(0xFFB4FFC8) else Color(0xFF39FF6A).copy(alpha = (0.8f - k * .14f).coerceAtLeast(0f))
                        val largo = 3f + azar(c * 7 + k + (cabeza / 8).toInt()) * 4f
                        drawRect(color, Offset(x, y), Size(paso - 4, largo))
                    }
                }
                x += paso
                c++
            }
            var y = 0f
            while (y < h) { drawRect(Color.Black.copy(alpha = .45f), Offset(0f, y), Size(w, 1f)); y += 3f }
        }
        "grilla" -> {
            val horizonte = h * .55f
            drawRect(Brush.verticalGradient(listOf(Color(0xFF1A0640), Color(0xFF5A0C6E)), 0f, horizonte), size = Size(w, horizonte))
            val cx = w * .8f
            clipRect(bottom = horizonte) {
                drawCircle(Brush.verticalGradient(listOf(Color(0xFFFFD23F), Color(0xFFFF2FD6)), horizonte - 26, horizonte), 26f, Offset(cx, horizonte))
                for (i in 0 until 4) drawRect(Color(0xFF1A0640), Offset(cx - 28, horizonte - 4 - i * 6), Size(56f, 1.5f + i * .4f))
            }
            drawRect(Color(0xFF0A0218), Offset(0f, horizonte), Size(w, h - horizonte))
            for (i in -14..14) drawLine(Color(0xCC22E4FF), Offset(cx + i * 6, horizonte), Offset(cx + i * 90, h), 1f)
            val fase = (t * .8f) % 1f
            for (k in 0 until 6) {
                val z = (k + fase) / 6f
                val yy = horizonte + (h - horizonte) * z * z
                drawLine(Color(0xFFFF2FD6).copy(alpha = .3f + .7f * z), Offset(0f, yy), Offset(w, yy), 1f)
            }
        }
        "casete" -> {
            drawRect(Color(0xFF2A1A10))
            val x0 = w * .6f
            val ancho = minOf(170f, w - x0 - 8)
            drawRoundRect(Color(0xFF3B2414), Offset(x0, 3f), Size(ancho, h - 6), CornerRadius(6f, 6f))
            drawRect(Color(0xFFFFB347), Offset(x0 + 8, 6f), Size(ancho - 16, 6f))
            val giro = t * (if (sonando) 4f else .3f)
            for (f in listOf(.3f, .7f)) {
                val c = Offset(x0 + ancho * f, h / 2 + 3)
                drawCircle(Color(0xFFF6EAD2), 8f, c)
                for (k in 0 until 3) {
                    val a = giro + k * 2.094f
                    drawLine(Color(0xFF3B2414), c, Offset(c.x + kotlin.math.cos(a) * 7, c.y + sin(a) * 7), 2f)
                }
            }
        }
        "vinilo" -> {
            drawRect(Brush.horizontalGradient(listOf(Color(0xFF24160C), Color(0xFF5A3820))))
            val r = h * 1.4f
            val c = Offset(w * .82f, h / 2)
            clipRect {
                drawCircle(Color(0xFF0C0C0C), r, c)
                var k = 6f
                while (k < r) { drawCircle(Color(0x99404040), k, c, style = Stroke(1f)); k += 4f }
                val g = if (sonando) t * 3.5f else 0f
                for (d in listOf(0f, 3.1416f)) drawLine(Color(0x40FFFFFF),
                    Offset(c.x + kotlin.math.cos(g + d) * r * .3f, c.y + sin(g + d) * r * .3f),
                    Offset(c.x + kotlin.math.cos(g + d) * r * .9f, c.y + sin(g + d) * r * .9f), 3f)
                drawCircle(Color(0xFFD4A24C), r * .28f, c)
            }
            drawLine(Color(0xFFC8C8C8), Offset(w - 6, 2f), Offset(c.x - r * .55f, c.y + 6), 2.5f)
        }
        "pixeles" -> {
            drawRect(Color.Black)
            val dibujo = listOf("0011100", "0111110", "1101011", "1111111", "0101010", "1000001")
            val tam = 3f
            val paso = (t * 25) % 80
            val x0 = w * .45f + (if (paso < 40) paso else 80 - paso)
            val colores = listOf(Color(0xFFFF2E88), Color(0xFF3CF2FF), Color(0xFFFFE14D))
            for (n in 0 until ((w * .5f) / 34).toInt()) {
                dibujo.forEachIndexed { fy, fila ->
                    fila.forEachIndexed { fx, ch ->
                        if (ch == '1') drawRect(colores[n % 3], Offset(x0 + n * 34 + fx * tam, 4 + fy * tam), Size(tam, tam))
                    }
                }
            }
            val nave = (t * 70) % (w * .5f) + w * .45f
            drawRect(Color(0xFF7DFF6E), Offset(nave, h - 7), Size(13f, 4f))
        }
        "osciloscopio" -> {
            drawRect(Color(0xFF06140B))
            var x = 0f
            while (x < w) { drawLine(Color(0x287CFF9A), Offset(x, 0f), Offset(x, h), 1f); x += 20f }
            val camino = Path()
            val amp = h * (if (sonando) .38f else .08f)
            x = w * .45f
            var primero = true
            while (x < w) {
                val y = h / 2 + sin(x / 9 + t * 9) * amp * (.6f + .4f * sin(x / 47 + t * 2))
                if (primero) { camino.moveTo(x, y); primero = false } else camino.lineTo(x, y)
                x += 3f
            }
            drawPath(camino, Color(0x557CFF9A), style = Stroke(5f))
            drawPath(camino, Color(0xFF7CFF9A), style = Stroke(2f))
        }
        "olas" -> {
            drawRect(Brush.verticalGradient(listOf(Color(0xFF0E5A86), Color(0xFF031624))))
            listOf(Triple(Color(0x96147A9C), .35f, 1f), Triple(Color(0x961F9CB8), .5f, 1.5f), Triple(Color(0x962FE0D0), .68f, 2.1f))
                .forEachIndexed { k, (color, alto, vel) ->
                    val ola = Path().apply {
                        moveTo(0f, h)
                        var x = 0f
                        while (x <= w + 10) { lineTo(x, h * alto + sin(x / 40 + t * vel + k) * 4); x += 10f }
                        lineTo(w, h); close()
                    }
                    drawPath(ola, color)
                }
        }
        "fuego" -> {
            drawRect(Color(0xFF080201))
            var x = w * .45f
            var i = 0
            while (x < w) {
                val alto = h * (.55f + .45f * abs(sin(t * 3.1f + i * .7f)) * abs(sin(t * 1.7f + i * .31f))) * (if (sonando) 1f else .45f)
                val llama = Path().apply {
                    moveTo(x - 5, h)
                    quadraticTo(x - 6, h - alto * .5f, x + sin(t * 6 + i) * 2, h - alto)
                    quadraticTo(x + 6, h - alto * .5f, x + 5, h)
                    close()
                }
                drawPath(llama, Brush.verticalGradient(listOf(Color(0x00500000), Color(0xFFC2210A), Color(0xFFFF8A1A), Color(0xFFFFE27A)), h - alto, h))
                x += 7f
                i++
            }
        }
        "corazones" -> {
            drawRect(Brush.horizontalGradient(listOf(Color(0xFFFFD1E6), Color(0xFFFF6FA8))))
            for (i in 0 until 16) {
                val tam = 4f + (i * 7) % 6
                val x = w * .45f + azar(i) * w * .55f + sin(t * 1.5f + i) * 5
                val y = h + tam - ((t * (10 + i % 5 * 4) + i * 17) % (h + 2 * tam))
                val corazon = Path().apply {
                    moveTo(x, y + tam * .9f)
                    cubicTo(x - tam * 1.3f, y, x - tam * .6f, y - tam, x, y - tam * .3f)
                    cubicTo(x + tam * .6f, y - tam, x + tam * 1.3f, y, x, y + tam * .9f)
                }
                drawPath(corazon, if (i % 3 == 0) Color(0xFFFF3D8B) else Color.White.copy(alpha = .5f + .4f * abs(sin(t * 2 + i))))
            }
        }
        "teletexto" -> {
            drawRect(Color.Black)
            val colores = listOf(Color.Red, Color.Green, Color.Yellow, Color.Blue, Color.Magenta, Color.Cyan, Color.White)
            val pagina = 100 + (t / 2.5f).toInt() % 800
            val filas = minOf(4, ((t % 2.5f) * 4).toInt()) + 1
            val x0 = w * .45f
            for (f in 0 until filas) {
                var c = 0
                while (x0 + c * 8 < w - 20) {
                    val r = azar(pagina * 131 + f * 37 + c)
                    if (r < .55f) drawRect(colores[(r * 100).toInt() % 7], Offset(x0 + c * 8, 3 + f * 7f), Size(7f, 6f))
                    c++
                }
            }
        }
        "dial" -> {
            drawRect(Color(0xFF2B1A10))
            val x0 = w * .45f
            val ancho = w - x0 - 8
            drawRoundRect(Brush.verticalGradient(listOf(Color(0xFFFFCF7A), Color(0xFFC8822A))), Offset(x0, 3f), Size(ancho, h - 6), CornerRadius(12f, 12f))
            for (k in 0..20) {
                val x = x0 + 10 + k * (ancho - 20) / 20
                drawLine(Color(0xFF3A2008), Offset(x, h - 7), Offset(x, h - (if (k % 5 == 0) 14 else 10)), 1f)
            }
            val busca = (sin(t * (if (sonando) .5f else .15f)) + 1) / 2
            val xa = x0 + 10 + busca * (ancho - 20)
            drawLine(Color(0xFFC2210A), Offset(xa, 5f), Offset(xa, h - 5), 2f)
        }
        "vhs" -> {
            drawRect(Color(0xFF0B1A8A))
            val y = (t * 25) % (h + 30) - 15
            for (k in 0 until 3) drawRect(Color.White.copy(alpha = (50 - k * 12) / 255f), Offset(w * .45f, y + k * 4), Size(w * .55f, 2f))
            for (i in 0 until 40) drawRect(Color.White.copy(alpha = .27f), Offset(w * .45f + azar(i + (t * 30).toInt()) * w * .55f, azar(i * 3 + (t * 30).toInt()) * h), Size(2f, 1f))
            drawRect(if (sonando) Color.White else Color(0xFFC6D0FF), Offset(w - 30, h / 2 - 6), Size(4f, 12f))
            val play = Path().apply { moveTo(w - 22, h / 2 - 7); lineTo(w - 10, h / 2); lineTo(w - 22, h / 2 + 7); close() }
            drawPath(play, Color.White)
        }
        "burbujas" -> {
            drawRect(Brush.linearGradient(listOf(Color(0xFFBFE8FB), Color(0xFF7FCFF2), Color(0xFF55C2A8)), Offset.Zero, Offset(w, h)))
            for (i in 0 until 26) {
                val r = 3f + azar(i) * 8f
                val vel = 8f + azar(i + 60) * 14f
                val y = h + r - ((t * vel + azar(i + 120) * (h + 2 * r)) % (h + 2 * r))
                val x = w * .55f + azar(i + 200) * w * .45f + sin(t * 1.5f + i) * 4
                drawCircle(Brush.radialGradient(listOf(Color.White.copy(alpha = .9f), Color.White.copy(alpha = .2f), Color.White.copy(alpha = .1f)),
                    Offset(x - r * .3f, y - r * .3f), r * 1.2f), r, Offset(x, y))
                drawCircle(Color.White.copy(alpha = .7f), r, Offset(x, y), style = Stroke(1f))
            }
        }
    }
}

/** ⚙ Apariencia: la galería de temas. Se aplican al tocarlos (y quedan guardados). */
@Composable
fun PantallaApariencia(vm: Modelo) {
    BackHandler { vm.apariencia = false }
    Column(Modifier.fillMaxSize().background(C.fondo).statusBarsPadding().navigationBarsPadding()) {
        Row(Modifier.fillMaxWidth().background(C.panel).padding(horizontal = 16.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically) {
            Text("🎨 Apariencia", color = C.titulo, fontWeight = FontWeight.Bold, fontSize = 18.sp, modifier = Modifier.weight(1f))
            Boton("Listo", estilo = Estilo.PRIMARIO, chico = true) { vm.apariencia = false }
        }
        BandaRetro("Así se ve la banda de este tema", true)
        LazyColumn(contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp), modifier = Modifier.fillMaxSize()) {
            item {
                Tarjeta {
                    Interruptor("Animaciones arriba (estrellas, ecualizador…)", C.animada) { vm.elegirAnimadas(it) }
                    Pista("Los mismos temas están en la PC: Vista → Apariencia y temas.")
                }
            }
            items(TEMAS, key = { it.id }) { tema ->
                val elegido = tema.id == C.tema.id
                Row(
                    Modifier.fillMaxWidth().padding(vertical = 5.dp).clip(RoundedCornerShape(12.dp))
                        .background(if (elegido) C.chipActivo else C.panel)
                        .border(if (elegido) 2.dp else 1.dp, if (elegido) C.acento else C.borde, RoundedCornerShape(12.dp))
                        .clickable { vm.elegirTema(tema) }.padding(10.dp),
                    horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically,
                ) {
                    VistaPrevia(tema)
                    Column(Modifier.weight(1f)) {
                        Text((if (elegido) "✓ " else "") + tema.nombre, color = C.titulo, fontWeight = FontWeight.Bold)
                        Text(tema.epoca, color = C.acentoClaro, fontSize = 12.sp)
                        Text(tema.descripcion, color = C.tenue, fontSize = 12.sp, maxLines = 3, overflow = TextOverflow.Ellipsis)
                    }
                }
            }
        }
    }
}

/** Una ventanita dibujada con los colores del tema. */
@Composable
private fun VistaPrevia(t: TemaCel) {
    Canvas(Modifier.width(96.dp).height(72.dp).clip(RoundedCornerShape(6.dp))) {
        val w = size.width
        val h = size.height
        drawRect(col(t.fondo))
        drawRect(Brush.verticalGradient(t.barra.map { col(it) }.let { if (it.size == 1) it + it else it }), size = Size(w, h * .18f))
        drawRect(col(t.lcdFondo), Offset(0f, h * .18f), Size(w, h * .14f))
        drawRect(col(t.lcdTexto), Offset(w * .06f, h * .23f), Size(w * .45f, h * .04f))
        val r = androidx.compose.ui.geometry.CornerRadius(t.radio / 3f, t.radio / 3f)
        drawRoundRect(col(t.panel), Offset(w * .05f, h * .38f), Size(w * .9f, h * .32f), r)
        drawRoundRect(col(t.borde), Offset(w * .05f, h * .38f), Size(w * .9f, h * .32f), r, style = Stroke(1.5f))
        for (i in 0 until 3) drawRect(if (i == 1) col(t.acento) else col(t.texto), Offset(w * .1f, h * (.44f + i * .08f)), Size(w * (.5f - i * .1f), h * .03f))
        for (i in 0 until 3) {
            val b = Offset(w * (.06f + i * .31f), h * .76f)
            drawRoundRect(degrade(t.boton, t.brillo), b, Size(w * .27f, h * .16f), r)
            drawRoundRect(col(t.botonBorde), b, Size(w * .27f, h * .16f), r, style = Stroke(1.2f))
        }
    }
}

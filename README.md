<img src="organizador/icono.png" alt="TorrentVision" width="96">

# TorrentVision

**Torrent para todos.**

Aplicación de escritorio para bajar, organizar y ver películas, series y videos por categorías, con una app para el celular que la maneja desde el sillón.

*TVon es el nombre del proyecto en el código: el programa, la carpeta de datos y el paquete de la app siguen llamándose así por dentro.*

## Descargar

**[⬇ TorrentVision-Setup-1.10.29.exe](https://github.com/facuperma/TVon-App-de-escritorio-para-organizar-y-ver-videos/raw/main/instalador/TorrentVision-Setup-1.10.29.exe)** (91 MB): para la PC (Windows 10/11, 64 bits). No pide Python ni permisos de administrador. Como no está firmado, Windows puede decir «Windows protegió su PC»: **Más información → Ejecutar de todas formas**.

**[⬇ TorrentVision-Android-1.1.29.apk](https://github.com/facuperma/TVon-App-de-escritorio-para-organizar-y-ver-videos/raw/main/instalador/TorrentVision-Android-1.1.29.apk)** (3 MB): app para el celular (Android 8 o más nuevo).

También desde la **[página de TorrentVision](https://facuperma.github.io/TVon-App-de-escritorio-para-organizar-y-ver-videos/#bajar)** (en la compu muestra un QR para bajar la app).

**¿Es el original?** El botón **🔒 Bajar verificado** de esa página compara la huella SHA-256 con la de [`instalador/SHA256.txt`](instalador/SHA256.txt). A mano: `Get-FileHash TorrentVision-Setup-1.10.29.exe` en PowerShell.

La biblioteca y la configuración se guardan en `%LOCALAPPDATA%\TVon`.

## Desde el código fuente

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py        (o doble clic en TVon.bat)
```

Para generar el instalador: `pip install pyinstaller` y `python empaquetado\construir.py` (requiere [Inno Setup 6](https://jrsoftware.org/isinfo.php)); queda en `compilado\`. La app Android: JDK 17, Android SDK 35 y `gradlew assembleRelease` en `android\`.

## Lo principal

- **Biblioteca:** agregá archivos o carpetas (o arrastralos). No se copian ni se mueven, solo se guarda la ruta. Los videos de *Videos* y *Documentos* y los que terminan de bajarse en *Descargas* entran solos, con su título limpio, subtítulos y categoría (`Videos\Peliculas\<título>`). Lo que quitás no vuelve solo.
- **Categorías y Favoritos:** clic derecho para asignar, quitar o crear; **⚡ Categoría rápida** con el título del video; **★ Favoritos** siempre primera. Las categorías con algo por ver van en amarillo y las completas en verde.
- **Vistos y dónde quedaste:** recuerda el punto de cada video (visto al pasar el 90 %), la **cola de reproducción** (☰), el **siguiente capítulo automático** y **⏭ Saltar intro** en las series.
- **Fichas:** póster, sinopsis, géneros y puntaje de cada película y serie (Wikipedia y TVmaze sin configurar nada; con una clave gratis de TMDb sale mejor y en español).
- **🧲 Torrents:** pegá un magnet o abrí un `.torrent`; baja con [aria2](https://aria2.github.io) (incluido), solo la película (sin extras), sin programas ni ejecutables, y sigue en segundo plano junto al reloj.
- **🎞 Dominio público:** unas 25.000 películas del Internet Archive, con descarga automática opcional.
- **🎬 Letterboxd y búsqueda:** tu watchlist pública y las 500 mejor puntuadas, marcando las que ya tenés; el buscador de arriba filtra la biblioteca y, con Enter, busca cualquier película o serie para bajar (entiende «temporada 2», `S03E07`, «completa»…).
- **Subtítulos:** `.srt`/`.vtt` junto al video se cargan solos; búsqueda en OpenSubtitles (clave gratis) y subdivx; los que bajás por tu cuenta (`.srt`, `.zip`, `.rar`, `.7z`, packs de temporada) se ubican solos junto a su video. Sincronía fina (◀◀ ◀ ▶ ▶▶, 🎯 Ahora; teclas G / H) que se recuerda por video.
- **📺 Chromecast y Roku:** el botón 📺 manda el video a la tele (MKV, HEVC o DTS los convierte ffmpeg: botón *Instalar ffmpeg*). El canal de **Roku** muestra la biblioteca con un reproductor estilo Netflix: [`roku/LEEME.md`](roku/LEEME.md).
- **Varios videos:** *Abrir en ventana* (📌 siempre encima), **⏻ Apagar** al terminar, **🗑 Eliminar del disco** (a la Papelera) y **🖥 Modo Fullscreen** (F11).
- **🎨 23 temas retro** (*Vista → Apariencia*): colores, letra, forma de botones y una banda animada arriba (Galaxia P2P, Lámpara de llama, Luna, Gel azul, Fósforo, Neón Y2K, Casete 85, Arcade 8 bits, Videoclub…). También en el celular.

## 🎬 Tu BiriBiri, cuenta y amigos

Arriba a la derecha está **tu BiriBiri**: un muñequito 3D (Qt Quick 3D) que armás a tu gusto, con **tu foto en la cara** dentro de una escotilla redonda.

- **Aspecto:** género (hombre, mujer, no binario), 9 ojos, 10 cejas, 9 bocas (las abiertas son un hueco real con lengua y dientes), 13 prendas, 8 lentes con color de borde, peinados (el afro, redondo y suave), 10 estilos de barba y bigote, sombrero de paja, kipá y la **bandera de tu país flameando de fondo**, que se puede mover, agrandar e inclinar.
- **Poses:** normal, en T, celebrando, brazos cruzados, manos en la cintura, corriendo, acostado haciéndose el lindo, sentado con las piernas cruzadas, haciendo la vertical, saludando, volando, nadando, bailando, patada de karate y dormido. Se gira arrastrándolo, en cualquier dirección; con la rueda del mouse se le hace zoom y con el clic derecho se mueve la vista (doble clic: vuelve todo).
- **Otros lugares:** además de apoyado en el logo, puede **nadar detrás del logo**, estar **sentado debajo de la lista**, **acostado arriba del buscador**, **saludando en la esquina del reproductor** o **parado sobre la barra de abajo** (pestaña *🧍 Pose y lugar*).
- **Mascota:** un perro (labrador, salchicha, pug, husky, dálmata, caniche) o un gato (atigrado, siamés, negro, naranja, persa, manchado), con el color que quieras, parado a su lado. Juntos pueden hacerse mimos, darse un premio (hueso o pescadito), llenar el plato o jugar a la pelota (pestaña *🐾 Mascota*).
- **Cuenta y amigos:** sin correo (usuario, contraseña y código de recuperación); cada película suma 10 puntos y cada capítulo 2. Por ahora las cuentas son locales; el servidor para usarlo entre casas está en [`servidor_social/`](servidor_social/LEEME.md). No se manda qué viste, solo una huella de cada título.

## 📱 La app del celular (ON)

Botón **📱 ON** en la barra superior: muestra un código QR. Escaneálo con la app (o con la cámara: la página ofrece bajar la app, abrirla ya conectada o **usarlo en el navegador sin instalar nada**). El celular y la PC tienen que estar en la misma wifi; fuera de casa, con [Tailscale](https://tailscale.com/download).

- **Control:** reproductor completo, subtítulos, cola, volumen, 📺 Tele (Chromecast y Roku), **touchpad** (mover, clic, clic derecho, rueda) y **teclado en vivo** que se abre solo al tocar un campo de texto de la PC (con tildes, ñ y emojis).
- **Pantalla:** ves y manejás la pantalla de la PC con el dedo (fluida, normal o nítida) y proyectás la del celular con Miracast.
- **Inicio estilo Jellyfin:** pósters, *Seguir viendo*, *A continuación*, géneros y series por temporada. **Ver en el celular** manda la película por la conexión cifrada, con subtítulos y retomando donde quedaste (la PC la convierte si hace falta).
- **Magnets y subtítulos:** tocá un link magnet y va directo a la PC; pegá el link de un subtítulo o mandá el archivo y se pone junto a su película.
- **Se vincula una sola vez** (QR o *📡 Vincular sin QR*, con un código de 6 números para comparar) y se reconecta sola aunque la PC cambie de IP. Con ON encendido, cerrar la ventana deja TorrentVision junto al reloj; *Arrancar con Windows* es opcional.
- **Sin PC:** *▶ Entrar a la app* la convierte en videoteca del celular: baja películas de dominio público (y torrents, activando el motor desde ➕ Agregar), las guarda en *Películas/TorrentVision* y recuerda dónde quedaste. Solo wifi por defecto y siempre deja 1 GB libre.

## 🔒 Seguridad

- **Nunca ejecuta lo que baja:** de los torrents no se bajan programas ni accesos directos (.exe, .msi, .bat, .ps1, .lnk, .jar, .dll, .iso…); en el celular solo el video y sus subtítulos.
- **ON va por HTTPS** con un certificado propio; la app lo comprueba con la huella del QR (*certificate pinning*) y la sesión se guarda cifrada con el Android Keystore. Solo se acepta desde la red de casa o Tailscale; el QR sirve una sola vez, hay límite de intentos y cada celular tiene su sesión (*Dispositivos vinculados* → Desvincular). Otras páginas no pueden mandarle órdenes (CSRF, DNS rebinding).
- **Datos guardados:** las claves se cifran con DPAPI de Windows; de los celulares solo se guarda una huella SHA-256.
- **Internet:** todo por HTTPS, sin seguir redirecciones sin cifrar; los torrents usan tráfico cifrado entre pares. Compartir pantalla, mouse y teclado se puede apagar en las opciones de ON. La primera vez Windows pregunta por el firewall: permitilo solo en **redes privadas**.

## Atajos

| Tecla | Acción |
|---|---|
| ↑ / ↓ | Archivo anterior / siguiente |
| Espacio o clic en el video | Reproducir / pausar |
| ← / → · Shift+← / → | Retroceder / adelantar 5 s · 15 s |
| F o doble clic | Pantalla completa (Esc para salir) |
| F11 | Modo Fullscreen |
| N · I | Siguiente capítulo · Saltar intro |
| Inicio | Volver al principio |
| G / H | Subtítulos 0,1 s antes / después |
| Supr | Eliminar los seleccionados (a la Papelera) |
| Ctrl+F | Buscar |

## Licencia

© 2026 Facundo Gabriel Peralta Marello. **Todos los derechos reservados** ([LICENSE](LICENSE)).

El código está publicado para que se pueda leer, pero no se puede copiar, modificar, distribuir, vender ni usar con fines comerciales sin mi autorización por escrito. Los instaladores oficiales se pueden bajar e instalar para uso personal. Las versiones anteriores al 03/11/2026 se publicaron con la licencia MIT.

### Componentes de terceros

Conservan sus propias licencias:

- [aria2](https://github.com/aria2/aria2) 1.37.0: GPL v2, incluido sin modificar como programa aparte (`organizador\bin\aria2-LICENCIA.txt`).
- [PySide6 / Qt](https://www.qt.io/qt-for-python): LGPL v3, sin modificar. [cryptography](https://github.com/pyca/cryptography): Apache 2.0 / BSD. [segno](https://github.com/heuer/segno): BSD.
- App de Android: AndroidX, Jetpack Compose, Media3 (ExoPlayer) y OkHttp (Apache 2.0); libtorrent4j (MIT) y libtorrent (BSD), que se bajan aparte solo si se activan los torrents; lector de QR de Google Play Services según los términos de Google.

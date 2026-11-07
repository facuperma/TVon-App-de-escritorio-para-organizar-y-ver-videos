# TorrentVision para Roku

Canal para Roku (probado la sintaxis; falta probarlo en el aparato real) que muestra la biblioteca de la PC y la reproduce.

## Instalar (modo desarrollador, una sola vez)
1. En el control del Roku: **Inicio ×3, Arriba ×2, Derecha, Izquierda, Derecha, Izquierda, Derecha**. Activá el modo desarrollador, elegí una contraseña y dejá que reinicie.
2. En la PC: `python roku/instalar.py <IP del Roku> <contraseña>` (ej.: `python roku/instalar.py 192.168.1.36 miclave`). También se puede abrir `http://<IP del Roku>` en el navegador y subir `instalador/TorrentVision-Roku.zip`.

## Vincular
1. En la PC, TorrentVision abierto con **ON encendido**.
2. Abrí el canal **TorrentVision** en el Roku: busca la PC solo y muestra un **código de 6 números**.
3. Aprobalo en la PC (aparece un cartel) o en la app del celular (Control → 📺 Roku). Listo: no vuelve a pedirlo.
Si no encuentra la PC, tecla `*` → «Escribir la IP de la PC» (la muestra el botón ON).

## Desde el celular
En Control → 📺 Roku: pausa, ±30 s, subtítulos, parar. Con una película elegida: «📺 Ver en el Roku» (si el canal está cerrado, la PC lo abre sola; en el Roku hay que tener «Control por apps móviles» en *Predeterminado* o *Permisivo*).

## Seguridad
El Roku no puede validar el certificado de TorrentVision, así que usa un servidor aparte en HTTP (puerto 8770): solo IPs de la red de la casa, solo lectura de la biblioteca, y su token no sirve para manejar la PC (ni el de un celular sirve en el Roku). Se desvincula desde ON → Dispositivos vinculados.

## Si un video no anda
`*` → «Modo compatible»: la PC convierte con ffmpeg (necesita ffmpeg; no se puede adelantar). El canal lo prueba solo si hay un error.

# Servidor de cuentas de TorrentVision

Cuentas con usuario y contraseña (sin correo), el muñequito, los puntos por lo visto y los amigos. Solo usa Python (biblioteca estándar).

```
python servidor_social/servidor.py --puerto 8780 --base social.db
```

- **Probar en casa:** correlo en la PC y en TorrentVision (🧍 arriba a la derecha → Cuenta) poné `http://localhost:8780` (o la IP de la PC en la red).
- **Con amigos por internet:** tiene que estar en un servidor accesible y con **HTTPS** (TorrentVision no acepta `http://` fuera de la red de la casa). Por ejemplo detrás de Caddy, o en un hosting de Python; con un proxy propio, agregá `--detras-de-proxy`.
- **Sin correo:** al crear la cuenta se muestra un código de recuperación una sola vez; es la única forma de cambiar la contraseña.
- **Puntos:** película 10, capítulo 2, hasta 60 por día, cada una una sola vez. El servidor recibe huellas (SHA-256), no los títulos.
- **Seguridad:** contraseñas con scrypt, sesiones guardadas como SHA-256, freno de intentos por IP, el avatar se valida (solo colores y opciones conocidas).

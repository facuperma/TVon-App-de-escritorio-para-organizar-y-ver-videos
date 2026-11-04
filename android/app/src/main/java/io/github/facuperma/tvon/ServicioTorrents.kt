package io.github.facuperma.tvon

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/**
 * Mantiene vivos los torrents del celular con la pantalla apagada (Android lo exige con una
 * notificación fija). Se va solo cuando no queda nada por bajar.
 */
class ServicioTorrents : Service() {
    private val alcance = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        canales(this)
        ServiceCompat.startForeground(this, AVANCE, aviso("Preparando los torrents…", null),
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC else 0)
        alcance.launch { vigilar() }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int = START_STICKY

    private suspend fun vigilar() {
        if (!Torrents.iniciar(this)) return terminar()
        val prefs = getSharedPreferences("videoteca", Context.MODE_PRIVATE)
        val gestor = getSystemService(NotificationManager::class.java)
        var vacio = 0
        while (alcance.isActive) {
            val terminados = Torrents.actualizar(this, prefs.getBoolean("solo_wifi", true))
            for (nombre in terminados) {
                gestor.notify(nombre.hashCode(), NotificationCompat.Builder(this, LISTOS)
                    .setSmallIcon(android.R.drawable.stat_sys_download_done)
                    .setContentTitle("Lista para ver")
                    .setContentText(nombre)
                    .setContentIntent(abrirApp())
                    .setAutoCancel(true)
                    .build())
            }
            val lista = Torrents.lista
            // Unos segundos de gracia: el link recién pegado tarda en registrarse
            vacio = if (lista.isEmpty() && !Torrents.hayAlgo(this)) vacio + 1 else 0
            if (vacio >= 10) return terminar()
            val texto = when (lista.size) {
                0 -> "Buscando el torrent en la red…"
                1 -> "${lista[0].nombre} · ${(lista[0].progreso * 100).toInt()} % · ${lista[0].estado}"
                else -> "${lista.size} torrents · ${(lista.map { it.progreso }.average() * 100).toInt()} %"
            }
            gestor.notify(AVANCE, aviso(texto, lista.takeIf { it.size == 1 }?.first()?.progreso))
            delay(1000)
        }
    }

    /** Android 15 corta este tipo de servicio después de 6 horas por día: se pausa y se avisa. */
    override fun onTimeout(startId: Int, fgsType: Int) {
        getSystemService(NotificationManager::class.java).notify(PAUSA, NotificationCompat.Builder(this, LISTOS)
            .setSmallIcon(android.R.drawable.stat_sys_warning)
            .setContentTitle("Torrents en pausa")
            .setContentText("Android frenó la descarga después de varias horas. Abrí TorrentVision para seguir.")
            .setContentIntent(abrirApp())
            .setAutoCancel(true)
            .build())
        terminar()
    }

    private fun terminar() {
        ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    override fun onDestroy() {
        alcance.cancel()
        super.onDestroy()
    }

    private fun abrirApp(): PendingIntent = PendingIntent.getActivity(this, 0,
        Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)

    private fun aviso(texto: String, progreso: Float?): Notification =
        NotificationCompat.Builder(this, BAJANDO)
            .setSmallIcon(android.R.drawable.stat_sys_download)
            .setContentTitle("TorrentVision · torrents")
            .setContentText(texto)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setSilent(true)
            .setContentIntent(abrirApp())
            .apply { if (progreso != null) setProgress(1000, (progreso * 1000).toInt(), false) }
            .build()

    companion object {
        private const val BAJANDO = "torrents"
        private const val LISTOS = "listas"
        private const val AVANCE = 41
        private const val PAUSA = 42

        fun iniciar(contexto: Context) {
            ContextCompat.startForegroundService(contexto, Intent(contexto, ServicioTorrents::class.java))
        }

        private fun canales(contexto: Context) {
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
            val gestor = contexto.getSystemService(NotificationManager::class.java)
            gestor.createNotificationChannel(NotificationChannel(BAJANDO, "Torrents bajando", NotificationManager.IMPORTANCE_LOW))
            gestor.createNotificationChannel(NotificationChannel(LISTOS, "Películas listas", NotificationManager.IMPORTANCE_DEFAULT))
        }
    }
}

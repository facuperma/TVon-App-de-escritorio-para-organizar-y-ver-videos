' TorrentVision para Roku: pantalla única que cambia de estado:
'   buscando → emparejando (código en pantalla) → inicio (filas) → episodios → video
' La PC (TorrentVision) guarda todo; el Roku solo muestra y reproduce.

sub init()
    m.fondo = m.top.findNode("fondo")
    m.seccion = m.top.findNode("seccion")
    m.mensaje = m.top.findNode("mensaje")
    m.codigo = m.top.findNode("codigo")
    m.ayuda = m.top.findNode("ayuda")
    m.filas = m.top.findNode("filas")
    m.episodios = m.top.findNode("episodios")
    m.pie = m.top.findNode("pie")
    m.video = m.top.findNode("video")

    m.filas.observeField("rowItemSelected", "alElegir")
    m.episodios.observeField("itemSelected", "alElegirEpisodio")
    m.video.observeField("state", "alEstadoVideo")
    m.panel = m.top.findNode("panel")
    m.menuVideo = m.top.findNode("menuVideo")
    m.menuVideo.observeField("itemSelected", "alMenuVideo")
    m.pistas = []          ' los subtítulos del video: [{ TrackName, Description }]
    m.avisoIntro = m.top.findNode("avisoIntro")
    m.intro = []           ' [inicio, fin] en ms de la intro (series), si la PC ya la detectó
    m.accionesMenu = []
    ' Menú de arriba y grilla de Películas / Series
    m.menuSup = m.top.findNode("menuSup")
    m.menuMarca = m.top.findNode("menuMarca")
    m.menuFoco = m.top.findNode("menuFoco")
    m.logoTop = m.top.findNode("logoTop")
    m.introFondo = m.top.findNode("introFondo")
    m.introTexto = m.top.findNode("introTexto")
    m.navego = false       ' true si se está moviendo por los botones del reproductor (OK ya no salta la intro)
    m.espera = 0           ' segundos seguidos cargando sin que arranque
    m.quieto = 0           ' segundos seguidos «reproduciendo» sin avanzar
    m.posAnt = -1
    m.firmaBotones = ""
    m.objetivoAplicado = false
    m.edadObjetivo = 0
    m.menuEtiquetas = [m.top.findNode("menuInicio"), m.top.findNode("menuPeliculas"), m.top.findNode("menuSeries")]
    m.secciones = ["inicio", "pelicula", "serie"]
    m.menuSel = 0
    m.enMenu = false
    m.volver = "inicio"
    m.grilla = m.top.findNode("grilla")
    m.grilla.observeField("itemSelected", "alElegirGrilla")
    ' El reproductor estilo Netflix
    m.controles = m.top.findNode("controles")
    m.ctrlTitulo = m.top.findNode("ctrlTitulo")
    m.ctrlTiempo = m.top.findNode("ctrlTiempo")
    m.ctrlBotones = m.top.findNode("ctrlBotones")
    m.ctrlFoco = m.top.findNode("ctrlFoco")
    m.barraLlena = m.top.findNode("barraLlena")
    m.barraPunto = m.top.findNode("barraPunto")
    m.botones = []
    m.botonFoco = 0
    m.enBarra = false
    ' Subtítulos dibujados por el canal
    m.capaSubs = m.top.findNode("capaSubs")
    m.subEtiquetas = [m.top.findNode("subTexto"), m.top.findNode("subSombra1"), m.top.findNode("subSombra2")]
    m.cues = []
    m.idxCue = 0
    m.subActivo = -1
    m.retraso = 0
    m.escalaSubs = 1.0
    m.toast = m.top.findNode("toast")
    m.toastTimer = CreateObject("roSGNode", "Timer")
    m.toastTimer.duration = 3.5
    m.toastTimer.observeField("fire", "alToast")
    m.video.notificationInterval = 0.1
    m.video.observeField("position", "alPosicion")
    m.desde = 0            ' ms: el video convertido por la PC empieza acá (se suma a la posición del Roku)
    m.durTotal = 0         ' ms: duración del video entero (el convertido no la sabe)
    m.modoFicha = ""       ' "" tal cual · "audio" / "video": convertido por la PC (adelantar = pedirlo de nuevo)
    m.objetivo = -1
    m.ocultar = CreateObject("roSGNode", "Timer")
    m.ocultar.duration = 8
    m.ocultar.observeField("fire", "alOcultar")
    m.saltoTimer = CreateObject("roSGNode", "Timer")
    m.saltoTimer.duration = 0.6
    m.saltoTimer.observeField("fire", "alSalto")
    ' Si la PC no contesta (apagada, TorrentVision cerrado), se reintenta sola cada unos segundos
    m.reintentoTimer = CreateObject("roSGNode", "Timer")
    m.reintentoTimer.duration = 8
    m.reintentoTimer.observeField("fire", "alReintento")

    m.tareas = []          ' las tareas en curso (si nadie las guarda, se pierden)
    m.pantalla = "buscando"
    m.base = ""
    m.token = ""
    m.compat = ""          ' "" = tal cual, "audio" o "video" = la PC convierte con ffmpeg
    m.actual = { id: 0, titulo: "", siguiente: 0 }
    m.reintento = 0
    m.solicitud = ""
    m.intentosSondeo = 0
    m.episodiosAbiertos = false
    m.pc = ""              ' id de la PC vinculada: si le cambia la IP, se la busca por este id
    m.ultimoPase = ""
    m.reubicando = false
    m.reubicado = false

    leerRegistro()

    ' Una vez por segundo se actualiza lo que el latido le cuenta a la PC
    m.reloj = CreateObject("roSGNode", "Timer")
    m.reloj.duration = 1
    m.reloj.repeat = true
    m.reloj.observeField("fire", "alReloj")
    m.reloj.control = "start"

    m.sondeo = CreateObject("roSGNode", "Timer")
    m.sondeo.duration = 2
    m.sondeo.repeat = true
    m.sondeo.observeField("fire", "alSondeo")

    if m.base <> "" and m.token <> "" then
        iniciarLatido()
        mostrarInicio()
    else
        buscarPC()
    end if
end sub

' --- Lo guardado en el Roku --------------------------------------------------------------------------

sub leerRegistro()
    r = CreateObject("roRegistrySection", "tvon")
    if r.Exists("base") then m.base = r.Read("base")
    if r.Exists("token") then m.token = r.Read("token")
    if r.Exists("compat") then m.compat = r.Read("compat")
    if r.Exists("pc") then m.pc = r.Read("pc")
end sub

sub vinculado(token as String, datos as Object)
    m.token = token
    guardarRegistro("base", m.base)
    guardarRegistro("token", m.token)
    if datos <> invalid and datos.id <> invalid then
        m.pc = datos.id
        guardarRegistro("pc", m.pc)
    end if
    m.reubicado = false
    iniciarLatido()
    mostrarInicio()
end sub

sub guardarRegistro(clave as String, valor as String)
    r = CreateObject("roRegistrySection", "tvon")
    r.Write(clave, valor)
    r.Flush()
end sub

sub borrarRegistro(clave as String)
    r = CreateObject("roRegistrySection", "tvon")
    r.Delete(clave)
    r.Flush()
end sub

' --- Pedidos a la PC ---------------------------------------------------------------------------------

sub pedir(metodo as String, ruta as String, cuerpo as String, etiqueta as String)
    t = CreateObject("roSGNode", "Api")
    t.url = m.base + ruta
    t.metodo = metodo
    t.cuerpo = cuerpo
    t.etiqueta = etiqueta
    t.observeField("respuesta", "alRespuesta")
    m.tareas.Push(t)
    if m.tareas.Count() > 12 then m.tareas.Shift()
    t.control = "RUN"
end sub

function con_token(ruta as String) as String
    separador = "?"
    if Instr(1, ruta, "?") > 0 then separador = "&"
    return ruta + separador + "t=" + m.token
end function

' (roUrlTransfer no se puede crear en el hilo de la pantalla: se usa el método del texto)
function escapar(texto as String) as String
    return texto.EncodeUriComponent()
end function

sub alRespuesta(evento as Object)
    r = evento.getData()
    if r = invalid then return
    if r.codigo = 401 and r.etiqueta <> "estado" then
        desvincular("Este Roku ya no está vinculado a la PC.")
        return
    end if
    if r.etiqueta = "solicitar" then
        alSolicitar(r)
    else if r.etiqueta = "pase" then
        alPase(r)
    else if r.etiqueta = "id" then
        if r.codigo = 200 and r.datos <> invalid and r.datos.id <> invalid then
            m.pc = r.datos.id
            guardarRegistro("pc", m.pc)
        end if
    else if r.etiqueta = "estado" then
        alEstado(r)
    else if r.etiqueta = "inicio" then
        alInicio(r)
    else if r.etiqueta = "serie" then
        alSerie(r)
    else if r.etiqueta = "ficha" then
        alFicha(r)
    else if r.etiqueta = "hola" then
        alHola(r)
    else if r.etiqueta = "catalogo" then
        alCatalogo(r)
    else if r.etiqueta = "subs" then
        if r.codigo = 200 and r.datos <> invalid and r.datos.cues <> invalid then
            m.cues = r.datos.cues
            m.idxCue = 0
        end if
    end if
end sub

' --- Buscar la PC y emparejar ------------------------------------------------------------------------

sub cambiarPantalla(nombre as String)
    m.pantalla = nombre
    m.filas.visible = (nombre = "inicio")
    m.grilla.visible = (nombre = "grilla")
    m.episodios.visible = (nombre = "episodios")
    m.video.visible = (nombre = "video")
    m.menuSup.visible = (nombre = "inicio" or nombre = "grilla")
    m.logoTop.visible = (nombre <> "inicio" and nombre <> "grilla" and nombre <> "video")
    if nombre <> "video" then
        m.controles.visible = false
        m.avisoIntro.visible = false
        m.panel.visible = false
    end if
    hayTexto = (nombre = "buscando" or nombre = "emparejando" or nombre = "error")
    m.mensaje.visible = hayTexto
    m.codigo.visible = hayTexto
    m.ayuda.visible = hayTexto
    m.fondo.visible = (nombre <> "video")
    if nombre = "inicio" then
        m.seccion.text = ""
        m.pie.text = "◀ Menú     OK Elegir     ✱ Opciones"
        m.enMenu = false
        marcarMenu()
        m.filas.setFocus(true)
    else if nombre = "grilla" then
        m.seccion.text = ""
        m.pie.text = "◀ Menú     OK Elegir     Atrás: Menú"
        m.enMenu = false
        marcarMenu()
        m.grilla.setFocus(true)
    else if nombre = "episodios" then
        m.pie.text = "Atrás: volver"
        m.episodios.setFocus(true)
    else if nombre = "video" then
        m.pie.text = ""
        m.top.setFocus(true)
    else
        m.pie.text = "* Opciones"
        m.top.setFocus(true)
    end if
end sub

' --- Menú de arriba: Inicio · Películas · Series ---------------------------------------------------------

sub marcarMenu()
    for i = 0 to 2
        if i = m.menuSel and m.enMenu then
            m.menuEtiquetas[i].color = "0x000000FF"       ' sobre la píldora blanca
        else if i = m.menuSel then
            m.menuEtiquetas[i].color = "0xFFFFFFFF"
        else
            m.menuEtiquetas[i].color = "0x9FB3CCFF"
        end if
    end for
    y = 146 + m.menuSel * 68
    m.menuFoco.translation = [14, y]
    m.menuFoco.visible = m.enMenu
    m.menuMarca.translation = [8, y + 10]
end sub

sub irSeccion(i as Integer)
    m.menuSel = i
    if m.secciones[i] = "inicio" then
        if m.filas.content = invalid then
            mostrarInicio()
        else
            cambiarPantalla("inicio")
        end if
    else
        cambiarPantalla("grilla")
        m.grilla.content = invalid
        m.mensaje.visible = true
        m.mensaje.text = "Cargando…"
        pedir("GET", con_token("/roku/catalogo?tipo=" + m.secciones[i]), "", "catalogo")
    end if
    if m.enMenu then m.top.setFocus(true)
end sub

sub alCatalogo(r as Object)
    m.mensaje.visible = false
    if r.codigo <> 200 or r.datos = invalid then return
    raiz = CreateObject("roSGNode", "ContentNode")
    for each it in r.datos.items
        raiz.appendChild(tarjeta(it))
    end for
    m.grilla.content = raiz
    if raiz.getChildCount() = 0 then
        m.mensaje.visible = true
        m.mensaje.text = "No hay nada acá todavía."
    end if
    if not m.enMenu and m.pantalla = "grilla" then m.grilla.setFocus(true)
end sub

sub alElegirGrilla()
    item = m.grilla.content.getChild(m.grilla.itemSelected)
    if item <> invalid then elegirItem(item, "grilla")
end sub

sub buscarPC()
    m.sondeo.control = "stop"
    cambiarPantalla("buscando")
    m.mensaje.text = "Buscando TorrentVision en tu red…"
    m.codigo.text = ""
    m.ayuda.text = "Lo más fácil: en la app del celular, Control → Roku → «Conectar un Roku». O abrí TorrentVision en la PC con ON encendido (misma red wifi)."
    b = CreateObject("roSGNode", "Buscar")
    b.observeField("resultado", "alBuscar")
    m.buscador = b
    b.control = "RUN"
end sub

' La PC vinculada no contesta en su IP de siempre: se la busca en la red por su id (no se confunde con otra PC)
sub reubicar()
    m.reubicado = true
    m.reubicando = true
    if m.latido <> invalid then m.latido.control = "STOP"
    cambiarPantalla("buscando")
    m.mensaje.text = "Buscando tu PC en la red…"
    m.codigo.text = ""
    m.ayuda.text = "¿Está prendida, con TorrentVision abierto y ON encendido?"
    b = CreateObject("roSGNode", "Buscar")
    b.quiero = m.pc
    b.observeField("resultado", "alBuscar")
    m.buscador = b
    b.control = "RUN"
end sub

sub alBuscar(evento as Object)
    r = evento.getData()
    if m.pantalla <> "buscando" then return   ' mientras tanto se vinculó desde el celular
    if m.reubicando then
        m.reubicando = false
        if r <> invalid and r.ok = true then
            m.base = "http://" + r.ip + ":" + r.puerto.ToStr()
            guardarRegistro("base", m.base)
            iniciarLatido()
            mostrarInicio()
        else
            cambiarPantalla("error")
            m.mensaje.text = "No encontré tu PC en la red."
            m.ayuda.text = "Prendé la PC y abrí TorrentVision con ON encendido. Apretá OK para reintentar."
            m.pantalla = "reintentar"
        end if
        return
    end if
    if r <> invalid and r.ok = true then
        m.base = "http://" + r.ip + ":" + r.puerto.ToStr()
        pedirEmparejar()
    else
        cambiarPantalla("error")
        m.mensaje.text = "No encontré la PC."
        m.codigo.text = ""
        m.ayuda.text = "Revisá que TorrentVision esté abierto con ON encendido y que la PC esté en la misma red." + Chr(10) + "Apretá OK para volver a buscar, o * para escribir la IP a mano."
    end if
end sub

sub pedirEmparejar()
    cambiarPantalla("emparejando")
    m.mensaje.text = "Conectando con la PC…"
    m.codigo.text = ""
    m.ayuda.text = ""
    info = CreateObject("roDeviceInfo")
    cuerpo = FormatJson({ nombre: info.GetFriendlyName() })
    pedir("POST", "/roku/solicitar", cuerpo, "solicitar")
end sub

sub alSolicitar(r as Object)
    if r.codigo = 200 and r.datos <> invalid then
        m.solicitud = r.datos.id
        m.intentosSondeo = 0
        m.mensaje.text = "En la PC (o en la app del celular, pestaña Control → Roku) aprobá este código:"
        m.codigo.text = r.datos.codigo
        m.ayuda.text = "Tiene que ser el mismo que ves acá. Si no lo pediste vos, rechazalo."
        m.sondeo.control = "start"
    else
        cambiarPantalla("error")
        mensaje = "La PC no aceptó el pedido."
        if r.datos <> invalid and r.datos.error <> invalid then mensaje = r.datos.error
        m.mensaje.text = mensaje
        m.codigo.text = ""
        m.ayuda.text = "Apretá OK para volver a intentar."
    end if
end sub

sub alSondeo()
    if m.pantalla <> "emparejando" or m.solicitud = "" then return
    m.intentosSondeo = m.intentosSondeo + 1
    if m.intentosSondeo > 65 then
        m.sondeo.control = "stop"
        buscarPC()
        return
    end if
    pedir("GET", "/roku/solicitud?id=" + m.solicitud, "", "estado")
end sub

sub alEstado(r as Object)
    if r.datos = invalid then return
    estado = r.datos.estado
    if estado = "aprobada" and r.datos.token <> invalid then
        m.sondeo.control = "stop"
        vinculado(r.datos.token, r.datos)
    else if estado = "rechazada" or estado = "vencida" then
        m.sondeo.control = "stop"
        cambiarPantalla("error")
        m.mensaje.text = "La PC rechazó el pedido o venció."
        m.codigo.text = ""
        m.ayuda.text = "Apretá OK para volver a intentar."
    end if
end sub

' «Conectar el Roku» desde el celular: la PC abrió el canal con un pase de un solo uso (sin código)
sub alVincular()
    v = m.top.vincular
    if v = invalid or v.pase = invalid or v.pase = m.ultimoPase then return
    m.ultimoPase = v.pase
    m.sondeo.control = "stop"
    m.reubicando = false
    if m.latido <> invalid then m.latido.control = "STOP"
    if m.pantalla = "video" then m.video.control = "stop"
    m.base = "http://" + v.ip + ":" + v.puerto
    cambiarPantalla("emparejando")
    m.mensaje.text = "Conectando con la PC…"
    m.codigo.text = ""
    m.ayuda.text = ""
    info = CreateObject("roDeviceInfo")
    pedir("POST", "/roku/pase", FormatJson({ pase: v.pase, nombre: info.GetFriendlyName() }), "pase")
end sub

sub alPase(r as Object)
    if r.codigo = 200 and r.datos <> invalid and r.datos.token <> invalid then
        vinculado(r.datos.token, r.datos)
    else
        cambiarPantalla("error")
        mensaje = "No se pudo conectar con la PC."
        if r.datos <> invalid and r.datos.error <> invalid then mensaje = r.datos.error
        m.mensaje.text = mensaje
        m.codigo.text = ""
        m.ayuda.text = "Volvé a tocar «Conectar un Roku» en el celular, o apretá OK para buscar la PC."
    end if
end sub

sub desvincular(texto as String)
    m.sondeo.control = "stop"
    if m.latido <> invalid then m.latido.control = "STOP"
    m.video.control = "stop"
    m.token = ""
    borrarRegistro("token")
    cambiarPantalla("error")
    m.mensaje.text = texto
    m.codigo.text = ""
    m.ayuda.text = "Apretá OK para volver a vincular."
end sub

' --- Latido: lo que se le cuenta a la PC y las órdenes del celular ---------------------------------------------

sub iniciarLatido()
    if m.latido <> invalid then m.latido.control = "STOP"
    l = CreateObject("roSGNode", "Latido")
    l.base = m.base
    l.token = m.token
    l.estado = { estado: "inactivo", pos: 0, dur: 0, id: 0, titulo: "" }
    l.observeField("ordenes", "alOrdenes")
    l.observeField("desvinculado", "alDesvinculado")
    m.latido = l
    l.control = "RUN"
end sub

sub alDesvinculado()
    desvincular("La PC desvinculó este Roku.")
end sub

function posActual() as Float
    if m.objetivo >= 0 then return m.objetivo
    return m.video.position + m.desde / 1000.0
end function

function durActual() as Float
    if m.durTotal > 0 then return m.durTotal / 1000.0
    return m.video.duration
end function

function enIntro() as Boolean
    if m.pantalla <> "video" or m.intro.Count() <> 2 then return false
    ms = posActual() * 1000
    return ms >= m.intro[0] - 500 and ms < m.intro[1] - 1500
end function

sub saltarIntro()
    if m.intro.Count() = 2 then irA(m.intro[1] / 1000)
    m.avisoIntro.visible = false
    m.navego = false
end sub

sub mostrarIntro()
    ver = enIntro() and not m.panel.visible
    if ver <> m.avisoIntro.visible then m.avisoIntro.visible = ver
    if ver then
        ' Blanco sólido = «OK salta»; atenuado = estás en otro botón
        if m.controles.visible and m.navego then
            m.introFondo.color = "0x000000AA"
            m.introTexto.color = "0xFFFFFFFF"
        else
            m.introFondo.color = "0xFFFFFFFF"
            m.introTexto.color = "0x000000FF"
        end if
    end if
end sub

sub alReloj()
    mostrarIntro()
    if m.controles.visible then actualizarBarra()
    vigilarVideo()
    if m.latido = invalid then return
    e = { estado: "inactivo", pos: 0, dur: 0, id: 0, titulo: "" }
    if m.pantalla = "video" then
        s = m.video.state
        e.estado = "reproduciendo"
        if s = "paused" then e.estado = "pausa"
        if s = "finished" then e.estado = "terminado"
        e.pos = Int(posActual() * 1000)
        e.dur = Int(durActual() * 1000)
        e.id = m.actual.id
        e.titulo = m.actual.titulo
        nombres = []
        for each p in m.pistas
            nombres.Push(p.Description)
        end for
        e.subs = nombres
        e.sub = subtituloActual()
        e.retraso = m.retraso
        e.escala = m.escalaSubs
    end if
    m.latido.estado = e
end sub

sub alOrdenes(evento as Object)
    lista = evento.getData()
    if lista = invalid then return
    for each o in lista
        ejecutarOrden(o)
    end for
end sub

sub ejecutarOrden(o as Object)
    c = o.c
    if c = "reproducir" then
        reproducir(Int(o.id))
    else if m.pantalla <> "video" then
        return
    else if c = "alternar" then
        if m.video.state = "paused" then
            m.video.control = "resume"
        else
            m.video.control = "pause"
        end if
    else if c = "adelantar" then
        irA(posActual() + o.ms / 1000)
    else if c = "ir_a" then
        irA(o.ms / 1000)
    else if c = "detener" then
        cerrarVideo()
    else if c = "subtitulos" then
        if o.activo = true then m.video.globalCaptionMode = "On" else m.video.globalCaptionMode = "Off"
    else if c = "subtitulo" then
        elegirSubtitulo(Int(o.n))
    else if c = "retraso" then
        m.retraso = Int(o.ms)
        avisar2("Subtítulos: " + textoRetraso())
    else if c = "tamano" then
        m.escalaSubs = o.escala
        aplicarTamano()
    else if c = "aviso" then
        avisar2(o.texto)
    else if c = "siguiente" then
        if m.actual.siguiente > 0 then
            siguiente = m.actual.siguiente
            cerrarVideo()
            reproducir(Int(siguiente))
        end if
    end if
end sub

sub irA(segundos as Float)
    if segundos < 0.5 then segundos = 0.5      ' justo en 0 algunos videos se quedan con la imagen congelada
    d = durActual()
    if d > 0 and segundos > d - 2 then segundos = d - 2
    ' La barra se mueve ya; el salto real se hace una sola vez, un instante después del último toque
    m.objetivo = segundos
    m.objetivoAplicado = false
    m.saltoTimer.control = "stop"
    m.saltoTimer.control = "start"
    actualizarBarra()
end sub

sub alSalto()
    if m.objetivo < 0 or m.actual.id <= 0 then return
    if m.modoFicha <> "" then
        ' Convertido por la PC: se pide de nuevo desde ahí
        pedirFicha(Int(m.actual.id), m.modoFicha, Int(m.objetivo * 1000))
    else
        m.video.seek = m.objetivo
        m.objetivoAplicado = true
        m.edadObjetivo = 0
    end if
end sub

' Cada segundo: si el video no arranca o se queda quieto, se pasa al modo que convierte la PC
sub vigilarVideo()
    if m.pantalla <> "video" then
        m.espera = 0
        m.quieto = 0
        return
    end if
    s = m.video.state
    if m.objetivoAplicado then
        m.edadObjetivo = m.edadObjetivo + 1
        if m.edadObjetivo > 6 then
            m.objetivo = -1
            m.objetivoAplicado = false
        end if
    end if
    if s = "buffering" or s = "none" then
        m.espera = m.espera + 1
    else
        m.espera = 0
    end if
    limite = 18
    if m.modoFicha = "video" then limite = 40
    if m.espera >= limite and m.objetivo < 0 then
        m.espera = 0
        reintentarOAvisar()
        return
    end if
    posVideo = m.video.position
    if s = "playing" and Abs(posVideo - m.posAnt) < 0.05 and m.objetivo < 0 then
        m.quieto = m.quieto + 1
    else
        m.quieto = 0
    end if
    m.posAnt = posVideo
    if m.quieto >= 8 then
        m.quieto = 0
        reintentarOAvisar()
    end if
end sub

sub alPedido()
    p = m.top.pedido
    if p <> invalid and p.id <> invalid and m.token <> "" then reproducir(Int(p.id))
end sub

' --- Inicio: las filas -----------------------------------------------------------------------------------

sub mostrarInicio()
    cambiarPantalla("inicio")
    m.filas.visible = false
    m.mensaje.visible = true
    m.mensaje.text = "Cargando tu biblioteca…"
    pedir("GET", con_token("/roku/inicio"), "", "inicio")
end sub

sub alInicio(r as Object)
    if r.codigo <= 0 and m.pc <> "" and not m.reubicado then
        reubicar()   ' sin respuesta: quizás el router le dio otra IP a la PC
        return
    end if
    if r.codigo <> 200 or r.datos = invalid then
        cambiarPantalla("error")
        m.mensaje.text = "No pude leer la biblioteca de la PC."
        m.codigo.text = ""
        m.ayuda.text = "¿Está prendida, con TorrentVision abierto y ON encendido? Vuelvo a intentar solo en unos segundos (u OK para ya)."
        m.pantalla = "reintentar"
        m.reintentoTimer.control = "start"
        return
    end if
    raiz = CreateObject("roSGNode", "ContentNode")
    for each fila in r.datos.filas
        nodo = raiz.createChild("ContentNode")
        nodo.title = fila.titulo
        for each it in fila.items
            nodo.appendChild(tarjeta(it))
        end for
    end for
    if raiz.getChildCount() = 0 then
        cambiarPantalla("error")
        m.mensaje.text = "La biblioteca está vacía."
        m.codigo.text = ""
        m.ayuda.text = "Agregá carpetas o películas en TorrentVision y apretá OK."
        m.pantalla = "reintentar"
        return
    end if
    m.filas.content = raiz
    m.reubicado = false
    if m.pc = "" then pedir("GET", "/roku/hola", "", "id")   ' vinculado con una versión anterior
    cambiarPantalla("inicio")
    m.mensaje.visible = false
end sub

function tarjeta(it as Object) as Object
    n = CreateObject("roSGNode", "ContentNode")
    n.title = it.titulo
    n.description = it.sub
    if it.poster <> "" then n.HDPosterUrl = m.base + con_token(it.poster)
    n.addFields({ tipo: it.tipo, idv: it.id, clave: it.clave, progreso: it.progreso, visto: it.visto })
    return n
end function

sub alElegir(evento as Object)
    sel = evento.getData()
    fila = m.filas.content.getChild(sel[0])
    if fila = invalid then return
    item = fila.getChild(sel[1])
    if item = invalid then return
    elegirItem(item, "inicio")
end sub

sub elegirItem(item as Object, desde as String)
    if item.tipo = "seccion" then
        irSeccion(Int(Val(item.clave)))
        return
    end if
    m.volver = desde
    m.episodiosAbiertos = false
    if item.tipo = "serie" then
        m.serieTitulo = item.title
        pedir("GET", con_token("/roku/serie?c=" + escapar(item.clave)), "", "serie")
    else
        reproducir(Int(item.idv))
    end if
end sub

' --- Series: lista de episodios ------------------------------------------------------------------------

sub alSerie(r as Object)
    if r.codigo <> 200 or r.datos = invalid then return
    raiz = CreateObject("roSGNode", "ContentNode")
    m.idsEpisodios = []
    elegido = 0
    i = 0
    for each e in r.datos.episodios
        n = raiz.createChild("ContentNode")
        marca = ""
        if e.visto = true then marca = "  ✓"
        if e.progreso > 0 then marca = "  " + Int(e.progreso * 100).ToStr() + "%"
        n.title = e.titulo + marca
        m.idsEpisodios.Push(e.id)
        if r.datos.seguir <> invalid and r.datos.seguir = e.id then elegido = i
        i = i + 1
    end for
    m.episodios.content = raiz
    cambiarPantalla("episodios")
    m.seccion.text = r.datos.titulo
    m.episodios.jumpToItem = elegido
end sub

sub alElegirEpisodio(evento as Object)
    i = evento.getData()
    m.episodiosAbiertos = true
    if i >= 0 and i < m.idsEpisodios.Count() then reproducir(Int(m.idsEpisodios[i]))
end sub

' --- Reproducir --------------------------------------------------------------------------------------

sub reproducir(id as Integer)
    if m.token = "" then return
    m.reintento = 0
    pedirFicha(id, m.compat, -1)
end sub

sub pedirFicha(id as Integer, modo as String, desde as Integer)
    m.pendiente = id
    m.modoActual = modo
    extra = ""
    if desde >= 0 then extra = "&desde=" + desde.ToStr()
    pedir("GET", con_token("/roku/ficha?id=" + id.ToStr() + "&modo=" + modo + extra), "", "ficha")
end sub

sub alFicha(r as Object)
    if r.codigo <> 200 or r.datos = invalid then
        texto = "No se pudo abrir el video."
        if r.datos <> invalid and r.datos.error <> invalid then texto = r.datos.error
        avisar(texto)
        return
    end if
    f = r.datos
    ' Si es el mismo video pedido de nuevo (adelantar en uno convertido), se mantiene el subtítulo elegido
    mismo = (m.pantalla = "video" and m.actual.id = f.id)
    m.desde = 0
    if f.desde <> invalid then m.desde = f.desde
    m.durTotal = 0
    if f.dur <> invalid then m.durTotal = f.dur
    m.modoFicha = ""
    if f.modo <> invalid then m.modoFicha = f.modo
    m.objetivo = -1
    m.objetivoAplicado = false
    m.espera = 0
    m.quieto = 0
    m.posAnt = -1
    c = CreateObject("roSGNode", "ContentNode")
    c.url = m.base + con_token(f.url)
    c.title = f.titulo
    c.streamFormat = f.formato
    c.playStart = f.pos / 1000
    pistas = []
    elegida = -1
    for each s in f.subtitulos
        pistas.Push({ Description: s.texto, n: s.n })
        if s.elegido = true and elegida < 0 then elegida = pistas.Count() - 1
    end for
    m.pistas = pistas
    m.actual = { id: f.id, titulo: f.titulo, siguiente: f.siguiente }
    m.intro = []
    if f.intro <> invalid and f.intro.Count() = 2 then m.intro = f.intro
    m.video.content = c
    m.video.globalCaptionMode = "Off"
    if not mismo then
        m.retraso = 0
        if f.retraso <> invalid then m.retraso = f.retraso
        elegirSubtitulo(elegida)
    end if
    m.ctrlTitulo.text = f.titulo
    cambiarPantalla("video")
    m.video.control = "play"
    mostrarControles()
end sub

sub alEstadoVideo()
    s = m.video.state
    if s = "finished" then
        siguiente = m.actual.siguiente
        cerrarVideo()
        if siguiente > 0 then reproducir(Int(siguiente))
    else if s = "error" then
        reintentarOAvisar()
    else if s = "paused" then
        mostrarControles()
    end if
end sub

sub reintentarOAvisar()
    ' Algo que el Roku no pudo abrir: la PC lo convierte entero (imagen y sonido) desde donde iba
    if m.modoFicha <> "video" and m.reintento < 2 then
        m.reintento = m.reintento + 1
        pedirFicha(Int(m.actual.id), "video", Int(posActual() * 1000))
    else
        cerrarVideo()
        avisar("El Roku no puede reproducir este video (ni convertido por la PC).")
    end if
end sub

sub alReintento()
    if m.pantalla = "reintentar" and m.token <> "" then
        m.reubicado = false
        mostrarInicio()
    end if
end sub

' --- El reproductor, como Netflix -----------------------------------------------------------------------

sub mostrarControles()
    firma = m.pistas.Count().ToStr() + "|" + m.actual.siguiente.ToStr() + "|" + m.video.state
    if firma <> m.firmaBotones then
        m.firmaBotones = firma
        armarBotones()
    end if
    actualizarBarra()
    mostrarIntro()
    m.controles.visible = true
    m.ocultar.control = "stop"
    m.ocultar.control = "start"
end sub

sub ocultarControles()
    m.controles.visible = false
    m.navego = false
    mostrarIntro()
end sub

sub alOcultar()
    ' En pausa quedan a la vista (como Netflix)
    if m.video.state <> "paused" and not m.panel.visible then ocultarControles()
end sub

sub armarBotones()
    pausa = "Pausa"
    if m.video.state = "paused" then pausa = "Reproducir"
    m.botones = [[pausa, "pausa", 150], ["-10 s", "atras", 110], ["+10 s", "adelante", 110]]
    if m.pistas.Count() > 0 then m.botones.Push(["Subtítulos", "subs", 160])
    if m.actual.siguiente > 0 then m.botones.Push(["Siguiente episodio", "siguiente", 250])
    m.botones.Push(["Salir", "salir", 110])
    if m.botonFoco >= m.botones.Count() then m.botonFoco = m.botones.Count() - 1
    m.ctrlBotones.removeChildrenIndex(m.ctrlBotones.getChildCount(), 0)
    x = 0
    for each b in m.botones
        l = CreateObject("roSGNode", "Label")
        l.text = b[0]
        l.width = b[2]
        l.height = 52
        l.horizAlign = "center"
        l.vertAlign = "center"
        l.font = "font:MediumSystemFont"
        l.color = "0xFFFFFFFF"
        l.translation = [x, 0]
        m.ctrlBotones.appendChild(l)
        x = x + b[2] + 14
    end for
    ubicarFoco()
end sub

sub ubicarFoco()
    x = 0
    for i = 0 to m.botonFoco - 1
        x = x + m.botones[i][2] + 14
    end for
    m.ctrlFoco.translation = [60 + x, 622]
    m.ctrlFoco.width = m.botones[m.botonFoco][2]
    if m.enBarra = invalid then m.enBarra = false
    m.ctrlFoco.visible = not m.enBarra
    m.barraPunto.width = 16
    m.barraPunto.height = 16
    if m.enBarra then
        m.barraPunto.width = 26
        m.barraPunto.height = 26
    end if
    for i = 0 to m.ctrlBotones.getChildCount() - 1
        if i = m.botonFoco and not m.enBarra then
            m.ctrlBotones.getChild(i).color = "0x000000FF"
        else
            m.ctrlBotones.getChild(i).color = "0xFFFFFFFF"
        end if
    end for
end sub

sub actualizarBarra()
    d = durActual()
    p = posActual()
    frac = 0
    if d > 0 then frac = p / d
    if frac < 0 then frac = 0
    if frac > 1 then frac = 1
    m.barraLlena.width = Int(1040 * frac)
    r = Int(m.barraPunto.width / 2)
    m.barraPunto.translation = [60 - r + Int(1040 * frac), 583 - r]
    ' Como Netflix: lo que falta
    m.ctrlTiempo.text = reloj(Int(d - p))
end sub

sub alternarPausa()
    if m.video.state = "paused" then
        m.video.control = "resume"
    else
        m.video.control = "pause"
    end if
end sub

sub activarBoton(accion as String)
    if accion = "pausa" then
        alternarPausa()
    else if accion = "atras" then
        irA(posActual() - 10)
    else if accion = "adelante" then
        irA(posActual() + 10)
    else if accion = "subs" then
        abrirSubs()
        return
    else if accion = "siguiente" then
        siguiente = m.actual.siguiente
        cerrarVideo()
        reproducir(Int(siguiente))
        return
    else if accion = "salir" then
        cerrarVideo()
        return
    end if
    mostrarControles()
end sub

' --- Subtítulos (panel a la derecha) ---

sub abrirSubs()
    if m.pistas.Count() = 0 then return
    raiz = CreateObject("roSGNode", "ContentNode")
    m.accionesMenu = []
    actual = subtituloActual()
    opciones = [["Desactivados", "sub:-1"]]
    for i = 0 to m.pistas.Count() - 1
        opciones.Push([m.pistas[i].Description, "sub:" + i.ToStr()])
    end for
    elegido = 0
    for i = 0 to opciones.Count() - 1
        marca = "     "
        if opciones[i][1] = "sub:" + actual.ToStr() then
            marca = "✓  "
            elegido = i
        end if
        n = raiz.createChild("ContentNode")
        n.title = marca + opciones[i][0]
        m.accionesMenu.Push(opciones[i][1])
    end for
    if actual >= 0 then
        tam = "Normal"
        if m.escalaSubs < 0.9 then tam = "Chico"
        if m.escalaSubs > 1.15 then tam = "Grande"
        extras = [["—  Ahora: " + textoRetraso(), "nada"], ["Que salgan antes (−0,5 s)", "ret:-500"],
                  ["Que salgan después (+0,5 s)", "ret:500"], ["Sincronizar solos con el audio", "sync"],
                  ["Tamaño: " + tam, "tam"]]
        for each o in extras
            n = raiz.createChild("ContentNode")
            n.title = o[0]
            m.accionesMenu.Push(o[1])
        end for
    end if
    m.menuVideo.content = raiz
    m.menuVideo.jumpToItem = elegido
    ocultarControles()
    m.panel.visible = true
    m.menuVideo.setFocus(true)
end sub

sub cerrarSubs()
    m.panel.visible = false
    m.top.setFocus(true)
    mostrarControles()
end sub

sub alMenuVideo()
    i = m.menuVideo.itemSelected
    if i < 0 or i >= m.accionesMenu.Count() then return
    a = m.accionesMenu[i]
    if Left(a, 4) = "sub:" then
        elegirSubtitulo(Int(Val(a.Mid(4))))
        cerrarSubs()
    else if Left(a, 4) = "ret:" then
        m.retraso = m.retraso + Int(Val(a.Mid(4)))
        avisar2("Subtítulos: " + textoRetraso())
        abrirSubs()
        m.menuVideo.jumpToItem = i
    else if a = "sync" then
        pedir("POST", con_token("/roku/sincronizar"), "{}", "sync")
        avisar2("Sincronizando los subtítulos con el audio… (puede tardar un rato)")
        cerrarSubs()
    else if a = "tam" then
        if m.escalaSubs < 0.9 then
            m.escalaSubs = 1.0
        else if m.escalaSubs < 1.15 then
            m.escalaSubs = 1.3
        else
            m.escalaSubs = 0.8
        end if
        aplicarTamano()
        abrirSubs()
        m.menuVideo.jumpToItem = i
    end if
end sub

function subtituloActual() as Integer
    return m.subActivo
end function

sub alPosicion()
    mostrarIntro()
    if m.controles.visible then actualizarBarra()
    if m.objetivoAplicado and m.objetivo >= 0 then
        ' Ya saltó: la barra deja de mostrar el destino cuando la posición real lo alcanzó
        if Abs(m.video.position + m.desde / 1000.0 - m.objetivo) < 3 then
            m.objetivo = -1
            m.objetivoAplicado = false
        end if
    end if
    if m.cues.Count() = 0 or m.subActivo < 0 then
        m.capaSubs.visible = false
        return
    end if
    t = m.video.position * 1000 + m.desde - m.retraso
    i = m.idxCue
    if i >= m.cues.Count() then i = m.cues.Count() - 1
    if i < 0 then i = 0
    while i > 0 and m.cues[i][0] > t
        i = i - 1
    end while
    while i < m.cues.Count() - 1 and m.cues[i][1] <= t
        i = i + 1
    end while
    m.idxCue = i
    c = m.cues[i]
    texto = ""
    if c[0] <= t and t < c[1] then texto = c[2]
    for each l in m.subEtiquetas
        l.text = texto
    end for
    m.capaSubs.visible = (texto <> "")
end sub

sub aplicarTamano()
    fuente = "font:MediumBoldSystemFont"
    if m.escalaSubs < 0.9 then fuente = "font:SmallBoldSystemFont"
    if m.escalaSubs > 1.15 then fuente = "font:LargeBoldSystemFont"
    for each l in m.subEtiquetas
        l.font = fuente
    end for
end sub

function textoRetraso() as String
    if m.retraso = 0 then return "sincronizados"
    seg = Abs(m.retraso) / 1000.0
    texto = Str(Int(seg * 10 + 0.5) / 10.0).Trim().Replace(".", ",") + " s"
    if m.retraso > 0 then return texto + " después"
    return texto + " antes"
end function

sub avisar2(texto as String)
    m.toast.text = texto
    m.toast.visible = true
    m.toastTimer.control = "stop"
    m.toastTimer.control = "start"
end sub

sub alToast()
    m.toast.visible = false
end sub

function reloj(segundos as Integer) as String
    if segundos < 0 then segundos = 0
    h = Int(segundos / 3600)
    mi = Int((segundos mod 3600) / 60)
    s = segundos mod 60
    if h > 0 then return h.ToStr() + ":" + Right("0" + mi.ToStr(), 2) + ":" + Right("0" + s.ToStr(), 2)
    return mi.ToStr() + ":" + Right("0" + s.ToStr(), 2)
end function

sub elegirSubtitulo(n as Integer)
    m.video.globalCaptionMode = "Off"
    m.cues = []
    m.idxCue = 0
    m.capaSubs.visible = false
    if n < 0 or n >= m.pistas.Count() then
        m.subActivo = -1
        return
    end if
    m.subActivo = n
    pedir("GET", con_token("/roku/subs?id=" + m.actual.id.ToStr() + "&n=" + m.pistas[n].n.ToStr()), "", "subs")
end sub

sub cerrarVideo()
    ' Por dónde iba, ya (el latido lo guarda cada 10 s: así no se pierde nada al salir)
    if m.actual.id > 0 and durActual() > 0 and m.pantalla = "video" then
        fin = { estado: "detenido", pos: Int(posActual() * 1000), dur: Int(durActual() * 1000), id: m.actual.id, titulo: m.actual.titulo }
        pedir("POST", con_token("/roku/latido"), FormatJson(fin), "fin")
    end if
    m.panel.visible = false
    m.controles.visible = false
    m.avisoIntro.visible = false
    m.navego = false
    m.firmaBotones = ""
    m.saltoTimer.control = "stop"
    m.objetivoAplicado = false
    m.objetivo = -1
    m.intro = []
    m.cues = []
    m.capaSubs.visible = false
    m.video.control = "stop"
    if m.episodiosAbiertos = true then
        cambiarPantalla("episodios")
    else if m.volver = "grilla" then
        cambiarPantalla("grilla")
    else
        cambiarPantalla("inicio")
    end if
end sub

sub avisar(texto as String)
    d = CreateObject("roSGNode", "StandardMessageDialog")
    d.title = "TorrentVision"
    d.message = [texto]
    d.buttons = ["OK"]
    d.observeField("buttonSelected", "alCerrarAviso")
    m.top.dialog = d
end sub

sub alCerrarAviso()
    if m.top.dialog <> invalid then m.top.dialog.close = true
end sub

' --- Opciones (tecla *) ---------------------------------------------------------------------------------

sub mostrarOpciones()
    d = CreateObject("roSGNode", "StandardMessageDialog")
    d.title = "Opciones"
    d.message = ["Si un video no tiene sonido o no arranca, activá el modo compatible: la PC lo convierte (consume más de la PC y no se puede adelantar)."]
    estado = "No"
    if m.compat <> "" then estado = "Sí"
    d.buttons = ["Modo compatible: " + estado, "Escribir la IP de la PC", "Desvincular de esta PC", "Cerrar"]
    d.observeField("buttonSelected", "alOpcion")
    m.top.dialog = d
end sub

sub alOpcion(evento as Object)
    i = evento.getData()
    alCerrarAviso()
    if i = 0 then
        if m.compat = "" then m.compat = "audio" else m.compat = ""
        guardarRegistro("compat", m.compat)
    else if i = 1 then
        pedirIP()
    else if i = 2 then
        borrarRegistro("token")
        borrarRegistro("base")
        borrarRegistro("pc")
        m.pc = ""
        if m.latido <> invalid then m.latido.control = "STOP"
        m.token = ""
        buscarPC()
    end if
end sub

sub pedirIP()
    d = CreateObject("roSGNode", "StandardKeyboardDialog")
    d.title = "IP de la PC (la muestra el botón ON de TorrentVision)"
    d.text = ""
    d.buttons = ["Conectar", "Cancelar"]
    d.observeField("buttonSelected", "alIP")
    m.top.dialog = d
end sub

sub alIP(evento as Object)
    i = evento.getData()
    texto = m.top.dialog.text
    alCerrarAviso()
    if i = 0 and texto <> "" then
        m.base = "http://" + texto.Trim() + ":8770"
        pedir("GET", "/roku/hola", "", "hola")
    end if
end sub

sub alHola(r as Object)
    if r.codigo = 200 then
        pedirEmparejar()
    else
        avisar("No encontré TorrentVision en esa IP (puerto 8770). Revisá que ON esté encendido.")
    end if
end sub

' --- Botones del control remoto ---------------------------------------------------------------------------

function onKeyEvent(tecla as String, presionada as Boolean) as Boolean
    if not presionada then return false
    if m.pantalla = "video" then return teclaVideo(tecla)
    if tecla = "options" then
        mostrarOpciones()
        return true
    end if
    if m.pantalla = "inicio" or m.pantalla = "grilla" then
        if m.enMenu then
            if tecla = "up" and m.menuSel > 0 then
                irSeccion(m.menuSel - 1)
            else if tecla = "down" and m.menuSel < 2 then
                irSeccion(m.menuSel + 1)
            else if tecla = "right" or tecla = "OK" then
                m.enMenu = false
                marcarMenu()
                if m.pantalla = "inicio" then m.filas.setFocus(true) else m.grilla.setFocus(true)
            else if tecla = "back" then
                return false     ' desde el menú, Atrás sale del canal
            end if
            return true
        end if
        if tecla = "left" or tecla = "back" then
            ' ◀ (en la primera columna) o Atrás: al menú lateral
            m.enMenu = true
            marcarMenu()
            m.top.setFocus(true)
            return true
        end if
        return false
    end if
    if m.pantalla = "episodios" and tecla = "back" then
        cambiarPantalla(m.volver)
        return true
    end if
    if (m.pantalla = "error" or m.pantalla = "reintentar") and tecla = "OK" then
        if m.token <> "" then
            m.reubicado = false
            mostrarInicio()
        else
            buscarPC()
        end if
        return true
    end if
    return false
end function

function teclaVideo(tecla as String) as Boolean
    if m.panel.visible then
        if tecla = "back" or tecla = "left" or tecla = "options" then
            cerrarSubs()
            return true
        end if
        return false   ' arriba, abajo y OK los maneja la lista de subtítulos
    end if
    if tecla = "back" then
        if m.controles.visible and m.video.state <> "paused" then
            ocultarControles()
        else
            cerrarVideo()
        end if
        return true
    end if
    if tecla = "rewind" then
        irA(posActual() - 30)
        mostrarControles()
        return true
    end if
    if tecla = "fastforward" then
        irA(posActual() + 30)
        mostrarControles()
        return true
    end if
    if tecla = "play" then
        alternarPausa()
        mostrarControles()
        return true
    end if
    ' «Saltar intro» a la vista: OK salta, salvo que ya te estés moviendo por los botones
    if tecla = "OK" and m.avisoIntro.visible and not (m.controles.visible and m.navego) then
        saltarIntro()
        return true
    end if
    if m.controles.visible then
        ' Como Netflix: arriba la barra (◀▶ adelanta/atrasa), abajo los botones (◀▶ elige)
        if tecla = "up" then
            m.enBarra = true
            m.navego = true
            ubicarFoco()
        else if tecla = "down" then
            m.enBarra = false
            m.navego = true
            ubicarFoco()
        else if tecla = "left" and m.enBarra then
            m.navego = true
            irA(posActual() - 10)
        else if tecla = "right" and m.enBarra then
            m.navego = true
            irA(posActual() + 10)
        else if tecla = "OK" and m.enBarra then
            alternarPausa()
        else if tecla = "left" then
            m.navego = true
            if m.botonFoco > 0 then m.botonFoco = m.botonFoco - 1
            ubicarFoco()
        else if tecla = "right" then
            m.navego = true
            if m.botonFoco < m.botones.Count() - 1 then m.botonFoco = m.botonFoco + 1
            ubicarFoco()
        else if tecla = "OK" then
            activarBoton(m.botones[m.botonFoco][1])
            return true
        else if tecla = "options" then
            abrirSubs()
            return true
        end if
        mostrarIntro()
        m.ocultar.control = "stop"
        m.ocultar.control = "start"
        return true
    end if
    ' Sin los controles a la vista
    if tecla = "OK" then
        alternarPausa()
        mostrarControles()
    else if tecla = "left" then
        m.enBarra = true
        irA(posActual() - 10)
        mostrarControles()
    else if tecla = "right" then
        m.enBarra = true
        irA(posActual() + 10)
        mostrarControles()
    else if tecla = "options" then
        abrirSubs()
    else
        m.botonFoco = 0
        m.enBarra = (tecla <> "down")
        mostrarControles()
        ubicarFoco()
    end if
    return true
end function

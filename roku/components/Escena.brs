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
    m.panelTitulo = m.top.findNode("panelTitulo")
    m.panelInfo = m.top.findNode("panelInfo")
    m.menuVideo = m.top.findNode("menuVideo")
    m.menuVideo.observeField("itemSelected", "alMenuVideo")
    m.pistas = []          ' los subtítulos del video: [{ TrackName, Description }]
    m.modoMenu = "principal"
    m.accionesMenu = []
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
    end if
end sub

' --- Buscar la PC y emparejar ------------------------------------------------------------------------

sub cambiarPantalla(nombre as String)
    m.pantalla = nombre
    m.filas.visible = (nombre = "inicio")
    m.episodios.visible = (nombre = "episodios")
    m.video.visible = (nombre = "video")
    hayTexto = (nombre = "buscando" or nombre = "emparejando" or nombre = "error")
    m.mensaje.visible = hayTexto
    m.codigo.visible = hayTexto
    m.ayuda.visible = hayTexto
    m.fondo.visible = (nombre <> "video")
    if nombre = "inicio" then
        m.seccion.text = ""
        m.pie.text = "* Opciones"
        m.filas.setFocus(true)
    else if nombre = "episodios" then
        m.pie.text = "Atrás: volver"
        m.episodios.setFocus(true)
    else if nombre = "video" then
        m.pie.text = ""
        m.video.setFocus(true)
    else
        m.pie.text = "* Opciones"
        m.top.setFocus(true)
    end if
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

sub alReloj()
    if m.latido = invalid then return
    e = { estado: "inactivo", pos: 0, dur: 0, id: 0, titulo: "" }
    if m.pantalla = "video" then
        s = m.video.state
        e.estado = "reproduciendo"
        if s = "paused" then e.estado = "pausa"
        if s = "finished" then e.estado = "terminado"
        e.pos = Int(m.video.position * 1000)
        e.dur = Int(m.video.duration * 1000)
        e.id = m.actual.id
        e.titulo = m.actual.titulo
        nombres = []
        for each p in m.pistas
            nombres.Push(p.Description)
        end for
        e.subs = nombres
        e.sub = subtituloActual()
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
        irA(m.video.position + o.ms / 1000)
    else if c = "ir_a" then
        irA(o.ms / 1000)
    else if c = "detener" then
        cerrarVideo()
    else if c = "subtitulos" then
        if o.activo = true then m.video.globalCaptionMode = "On" else m.video.globalCaptionMode = "Off"
    else if c = "subtitulo" then
        elegirSubtitulo(Int(o.n))
    end if
end sub

sub irA(segundos as Float)
    if segundos < 0 then segundos = 0
    if m.video.duration > 0 and segundos > m.video.duration - 1 then segundos = m.video.duration - 1
    m.video.seek = segundos
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
    pedirFicha(id, m.compat)
end sub

sub pedirFicha(id as Integer, modo as String)
    m.pendiente = id
    m.modoActual = modo
    pedir("GET", con_token("/roku/ficha?id=" + id.ToStr() + "&modo=" + modo), "", "ficha")
end sub

sub alFicha(r as Object)
    if r.codigo <> 200 or r.datos = invalid then
        texto = "No se pudo abrir el video."
        if r.datos <> invalid and r.datos.error <> invalid then texto = r.datos.error
        avisar(texto)
        return
    end if
    f = r.datos
    c = CreateObject("roSGNode", "ContentNode")
    c.url = m.base + con_token(f.url)
    c.title = f.titulo
    c.streamFormat = f.formato
    c.playStart = f.pos / 1000
    pistas = []
    elegida = ""
    for each s in f.subtitulos
        direccion = m.base + con_token("/roku/subtitulo?id=" + f.id.ToStr() + "&n=" + s.n.ToStr())
        pistas.Push({ Language: "spa", TrackName: direccion, Description: s.texto })
        if s.elegido = true or elegida = "" then elegida = direccion
    end for
    if pistas.Count() > 0 then c.update({ SubtitleTracks: pistas }, true)
    m.pistas = pistas
    m.actual = { id: f.id, titulo: f.titulo, siguiente: f.siguiente }
    m.video.content = c
    m.video.globalCaptionMode = "Off"
    if pistas.Count() > 0 then
        m.video.globalCaptionMode = "On"
        m.video.subtitleTrack = elegida
    end if
    cambiarPantalla("video")
    m.video.control = "play"
end sub

sub alEstadoVideo()
    s = m.video.state
    if s = "finished" then
        siguiente = m.actual.siguiente
        cerrarVideo()
        if siguiente > 0 then reproducir(Int(siguiente))
    else if s = "error" then
        reintentarOAvisar()
    end if
end sub

sub reintentarOAvisar()
    ' Sonido que el Roku no entiende (DTS…) o un contenedor raro: la PC lo convierte (primero solo el audio)
    if m.reintento = 0 and m.modoActual <> "audio" and m.modoActual <> "video" then
        m.reintento = 1
        pedirFicha(Int(m.actual.id), "audio")
    else if m.reintento = 1 and m.modoActual = "audio" then
        m.reintento = 2
        pedirFicha(Int(m.actual.id), "video")
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

' --- El menú durante la película ----------------------------------------------------------------------

sub abrirPanel()
    m.modoMenu = "principal"
    armarMenu()
    m.panelTitulo.text = m.actual.titulo
    m.panel.visible = true
    m.menuVideo.setFocus(true)
end sub

sub cerrarPanel()
    m.panel.visible = false
    if m.pantalla = "video" then m.video.setFocus(true)
end sub

function subtituloActual() as Integer
    if m.video.globalCaptionMode <> "On" then return -1
    for i = 0 to m.pistas.Count() - 1
        if m.pistas[i].TrackName = m.video.subtitleTrack then return i
    end for
    return -1
end function

sub armarMenu()
    raiz = CreateObject("roSGNode", "ContentNode")
    m.accionesMenu = []
    actual = subtituloActual()
    if m.modoMenu = "subs" then
        m.panelInfo.text = "Subtítulos"
        opciones = [["Sin subtítulos", -1]]
        for i = 0 to m.pistas.Count() - 1
            opciones.Push([m.pistas[i].Description, i])
        end for
        for each o in opciones
            marca = "     "
            if o[1] = actual then marca = "✓  "
            n = raiz.createChild("ContentNode")
            n.title = marca + o[0]
            m.accionesMenu.Push("sub:" + o[1].ToStr())
        end for
    else
        m.panelInfo.text = reloj(Int(m.video.position)) + " / " + reloj(Int(m.video.duration))
        nombre = "no"
        if actual >= 0 then nombre = m.pistas[actual].Description
        pausa = "Pausar"
        if m.video.state = "paused" then pausa = "Seguir viendo"
        opciones = [[pausa, "pausa"], ["Volver 30 segundos", "atras30"], ["Adelantar 1 minuto", "adelante60"]]
        if m.pistas.Count() > 0 then opciones.Push(["Subtítulos: " + nombre, "subs"])
        if m.actual.siguiente > 0 then opciones.Push(["Siguiente capítulo", "siguiente"])
        opciones.Push(["Parar y volver a la lista", "parar"])
        opciones.Push(["Cerrar este menú", "cerrar"])
        for each o in opciones
            n = raiz.createChild("ContentNode")
            n.title = o[0]
            m.accionesMenu.Push(o[1])
        end for
    end if
    m.menuVideo.content = raiz
    m.menuVideo.jumpToItem = 0
end sub

function reloj(segundos as Integer) as String
    if segundos < 0 then segundos = 0
    h = Int(segundos / 3600)
    mi = Int((segundos mod 3600) / 60)
    s = segundos mod 60
    if h > 0 then return h.ToStr() + ":" + Right("0" + mi.ToStr(), 2) + ":" + Right("0" + s.ToStr(), 2)
    return mi.ToStr() + ":" + Right("0" + s.ToStr(), 2)
end function

sub alMenuVideo()
    i = m.menuVideo.itemSelected
    if i < 0 or i >= m.accionesMenu.Count() then return
    accion = m.accionesMenu[i]
    if Left(accion, 4) = "sub:" then
        elegirSubtitulo(Int(Val(accion.Mid(4))))
        cerrarPanel()
    else if accion = "subs" then
        m.modoMenu = "subs"
        armarMenu()
    else if accion = "pausa" then
        if m.video.state = "paused" then
            m.video.control = "resume"
        else
            m.video.control = "pause"
        end if
        cerrarPanel()
    else if accion = "atras30" then
        irA(m.video.position - 30)
        cerrarPanel()
    else if accion = "adelante60" then
        irA(m.video.position + 60)
        cerrarPanel()
    else if accion = "siguiente" then
        siguiente = m.actual.siguiente
        cerrarPanel()
        cerrarVideo()
        reproducir(Int(siguiente))
    else if accion = "parar" then
        cerrarPanel()
        cerrarVideo()
    else
        cerrarPanel()
    end if
end sub

sub elegirSubtitulo(n as Integer)
    if n < 0 or n >= m.pistas.Count() then
        m.video.globalCaptionMode = "Off"
    else
        m.video.globalCaptionMode = "On"
        m.video.subtitleTrack = m.pistas[n].TrackName
    end if
end sub

sub cerrarVideo()
    ' Por dónde iba, ya (el latido lo guarda cada 10 s: así no se pierde nada al salir)
    if m.actual.id > 0 and m.video.duration > 0 and m.pantalla = "video" then
        fin = { estado: "detenido", pos: Int(m.video.position * 1000), dur: Int(m.video.duration * 1000), id: m.actual.id, titulo: m.actual.titulo }
        pedir("POST", con_token("/roku/latido"), FormatJson(fin), "fin")
    end if
    m.panel.visible = false
    m.video.control = "stop"
    if m.episodiosAbiertos = true then
        cambiarPantalla("episodios")
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
    if tecla = "options" and m.pantalla <> "video" then
        mostrarOpciones()
        return true
    end if
    if m.pantalla = "video" then
        if m.panel.visible then
            if tecla = "back" or tecla = "options" or tecla = "left" then
                if m.modoMenu = "subs" and tecla <> "options" then
                    m.modoMenu = "principal"
                    armarMenu()
                else
                    cerrarPanel()
                end if
                return true
            end if
            return false
        end if
        if tecla = "back" then
            cerrarVideo()
            return true
        end if
        if tecla = "options" or tecla = "up" or tecla = "down" then
            abrirPanel()
            return true
        end if
        return false
    end if
    if m.pantalla = "episodios" and tecla = "back" then
        cambiarPantalla("inicio")
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

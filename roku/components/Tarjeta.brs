sub init()
    m.poster = m.top.findNode("poster")
    m.titulo = m.top.findNode("titulo")
    m.barra = m.top.findNode("barra")
    m.fondoBarra = m.top.findNode("fondoBarra")
    m.visto = m.top.findNode("visto")
    m.grande = m.top.findNode("grande")
    m.fondo = m.top.findNode("sinPoster")
end sub

sub alContenido()
    c = m.top.itemContent
    if c = invalid then return
    m.poster.uri = c.HDPosterUrl
    t = c.title
    if c.description <> invalid and c.description <> "" then t = t + Chr(10) + c.description
    m.titulo.text = t
    progreso = 0
    if c.progreso <> invalid then progreso = c.progreso
    m.barra.visible = progreso > 0
    m.fondoBarra.visible = progreso > 0
    m.barra.width = 180 * progreso
    m.visto.visible = (c.visto = true)
    seccion = (c.tipo = "seccion")
    m.grande.visible = seccion
    if seccion then
        m.grande.text = c.title
        m.titulo.text = c.description
        m.fondo.color = "0x3DAEEBFF"
    else
        m.fondo.color = "0x1B2A44FF"
    end if
end sub

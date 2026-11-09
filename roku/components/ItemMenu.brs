sub init()
    m.pastilla = m.top.findNode("pastilla")
    m.marca = m.top.findNode("marca")
    m.texto = m.top.findNode("texto")
end sub

sub alContenido()
    c = m.top.itemContent
    if c = invalid then return
    m.texto.text = c.title
    pintar()
end sub

sub alFoco()
    pintar()
end sub

' Con el foco: píldora blanca y letras negras. Sin foco pero es la sección abierta: letras blancas y una marca celeste
sub pintar()
    c = m.top.itemContent
    activo = false
    if c <> invalid and c.activo = true then activo = true
    foco = m.top.itemHasFocus
    m.pastilla.visible = foco
    m.marca.visible = activo and not foco
    if foco then
        m.texto.color = "0x000000FF"
    else if activo then
        m.texto.color = "0xFFFFFFFF"
    else
        m.texto.color = "0x9FB3CCFF"
    end if
end sub

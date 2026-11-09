' Un pedido HTTP a la PC (en una tarea: la interfaz no puede esperar la red).
sub init()
    m.top.functionName = "ejecutar"
end sub

sub ejecutar()
    u = CreateObject("roUrlTransfer")
    puerto = CreateObject("roMessagePort")
    u.SetMessagePort(puerto)
    u.SetUrl(m.top.url)
    u.AddHeader("X-TVon", "1")
    u.RetainBodyOnError(true)
    if m.top.metodo = "POST" then
        u.AddHeader("Content-Type", "application/json")
        u.AsyncPostFromString(m.top.cuerpo)
    else
        u.AsyncGetToString()
    end if
    codigo = 0
    texto = ""
    espera = 8000
    if m.top.etiqueta = "ficha" then espera = 45000     ' la PC prueba el video antes de mandarlo
    evento = wait(espera, puerto)
    if type(evento) = "roUrlEvent" then
        codigo = evento.GetResponseCode()
        texto = evento.GetString()
    else
        u.AsyncCancel()
    end if
    datos = invalid
    if texto <> invalid and texto <> "" then datos = ParseJson(texto)
    m.top.respuesta = { codigo: codigo, datos: datos, etiqueta: m.top.etiqueta }
end sub

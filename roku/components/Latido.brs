' Cada 2 segundos le cuenta a la PC por dónde va y recibe las órdenes del celular (pausa, adelantar…).
sub init()
    m.top.functionName = "bucle"
end sub

sub bucle()
    while true
        u = CreateObject("roUrlTransfer")
        puerto = CreateObject("roMessagePort")
        u.SetMessagePort(puerto)
        u.SetUrl(m.top.base + "/roku/latido?t=" + m.top.token)
        u.AddHeader("X-TVon", "1")
        u.AddHeader("Content-Type", "application/json")
        u.RetainBodyOnError(true)
        estado = m.top.estado
        if estado = invalid then estado = {}
        u.AsyncPostFromString(FormatJson(estado))
        evento = wait(5000, puerto)
        if type(evento) = "roUrlEvent" then
            codigo = evento.GetResponseCode()
            if codigo = 401 then
                m.top.desvinculado = true
                return
            end if
            if codigo = 200 then
                datos = ParseJson(evento.GetString())
                if datos <> invalid and datos.ordenes <> invalid and datos.ordenes.Count() > 0 then
                    m.top.ordenes = datos.ordenes
                end if
            end if
        else
            u.AsyncCancel()
        end if
        sleep(2000)
    end while
end sub

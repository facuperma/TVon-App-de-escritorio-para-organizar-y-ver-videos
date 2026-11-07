' TorrentVision para Roku: ve la biblioteca de la PC por la red de la casa.
sub Main(args as Dynamic)
    pantalla = CreateObject("roSGScreen")
    puerto = CreateObject("roMessagePort")
    pantalla.SetMessagePort(puerto)
    escena = pantalla.CreateScene("Escena")
    pantalla.Show()

    ' El celular (o la PC) puede abrir el canal ya con una película: contentId = id del video
    entrada = CreateObject("roInput")
    entrada.SetMessagePort(puerto)
    pedirDesde(escena, args)

    while true
        msg = wait(0, puerto)
        if type(msg) = "roSGScreenEvent" then
            if msg.isScreenClosed() then return
        else if type(msg) = "roInput" then
            pedirDesde(escena, msg.GetInfo())
        end if
    end while
end sub

sub pedirDesde(escena as Object, datos as Dynamic)
    if datos <> invalid and datos.contentId <> invalid then
        id = Int(Val(datos.contentId.ToStr()))
        if id > 0 then escena.pedido = { id: id }
    end if
end sub

' Busca TorrentVision en la red: pregunta «TVON?» por difusión UDP (puerto 8765) y la PC contesta con su puerto para el Roku.
sub init()
    m.top.functionName = "buscar"
end sub

sub buscar()
    udp = CreateObject("roDatagramSocket")
    puerto = CreateObject("roMessagePort")
    udp.SetMessagePort(puerto)
    udp.SetBroadcast(true)
    udp.NotifyReadable(true)

    destinos = ["255.255.255.255:8765"]
    info = CreateObject("roDeviceInfo")
    direcciones = info.GetIPAddrs()
    for each nombre in direcciones
        partes = direcciones[nombre].Split(".")
        if partes.Count() = 4 then destinos.Push(partes[0] + "." + partes[1] + "." + partes[2] + ".255:8765")
    end for

    ' quiero = el id de la PC ya vinculada (si le cambió la IP): las demás PC de la casa no cuentan
    quiero = m.top.quiero
    for intento = 1 to 6
        for each destino in destinos
            direccion = CreateObject("roSocketAddress")
            direccion.SetAddress(destino)
            udp.SetSendToAddress(direccion)
            udp.SendStr("TVON?")
        end for
        evento = wait(1500, puerto)
        while type(evento) = "roSocketEvent" and udp.GetCountRcvdBytes() > 0
            texto = udp.ReceiveStr(512)
            datos = ParseJson(texto)
            origen = udp.GetReceivedFromAddress()
            if datos <> invalid and datos.tvon <> invalid and datos.roku <> invalid and datos.roku > 0 and origen <> invalid then
                id = ""
                if datos.id <> invalid then id = datos.id
                if quiero = "" or quiero = id then
                    m.top.resultado = { ok: true, ip: origen.GetHostName(), puerto: datos.roku, id: id }
                    return
                end if
            end if
            evento = wait(200, puerto)
        end while
    end for
    m.top.resultado = { ok: false }
end sub

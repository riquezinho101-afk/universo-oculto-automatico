import os
import re
import subprocess
import requests
import json

FPS = 30
W, H = 1920, 1080
PASTA = "cenas_novas"

HEADERS = {
    "User-Agent": "UniversoOculto/4.0 video production"
}

BUSCAS = {
    "ABERTURA": ["Earth from space video", "Earth rotation"],
    "PLANETA QUE VIBRA": [
        "ocean waves video",
        "seismograph video",
        "earthquake science"
    ],
    "DIA QUE ESTÁ FICANDO": [
        "Moon orbit Earth animation",
        "Earth rotation animation"
    ],
    "DESERTO QUE NÃO É": [
        "Antarctica dry valleys video",
        "McMurdo Dry Valleys"
    ],
    "TERRA JÁ FOI ROXA": [
        "purple bacteria microscopy",
        "halobacteria microscopy"
    ],
    "GRAVIDADE NÃO É": [
        "Earth gravity visualization",
        "Earth satellite animation"
    ],
    "NÚCLEO É TÃO QUENTE": [
        "Earth core animation",
        "Earth interior animation"
    ],
    "OCEANO OCULTO": [
        "Earth mantle animation",
        "ringwoodite mineral"
    ],
    "ENCERRAMENTO": [
        "Earth from space video",
        "Earth at night satellite"
    ]
}


def executar(comando):
    subprocess.run(comando, check=True)


def extrair_partes(roteiro):
    partes = []
    titulo = None
    linhas = []

    def salvar():
        if titulo:
            texto = " ".join(linhas).strip()
            if len(texto) > 40:
                partes.append((titulo, texto))

    for linha in roteiro.splitlines():
        linha = linha.strip()

        match = re.match(
            r"^\[(ABERTURA|PARTE\s*\d+\s*:.*|ENCERRAMENTO)\]$",
            linha,
            re.I
        )

        if match:
            salvar()
            titulo = match.group(1)
            linhas = []
            continue

        if titulo and linha:
            linhas.append(linha)

    salvar()

    if len(partes) < 5:
        raise RuntimeError(
            f"Foram encontradas apenas {len(partes)} seções."
        )

    return partes


def termos_da_secao(titulo):
    titulo = titulo.upper()

    for chave, termos in BUSCAS.items():
        if chave in titulo:
            return termos

    return ["Earth from space video"]


def pesquisar_video(termo):
    url = "https://commons.wikimedia.org/w/api.php"

    parametros = {
        "action": "query",
        "generator": "search",
        "gsrsearch": "filetype:video " + termo,
        "gsrnamespace": 6,
        "gsrlimit": 8,
        "prop": "imageinfo",
        "iiprop": "url",
        "format": "json"
    }

    resposta = requests.get(
        url,
        params=parametros,
        headers=HEADERS,
        timeout=45
    )

    resposta.raise_for_status()

    paginas = resposta.json().get(
        "query", {}
    ).get("pages", {})

    resultados = []

    for pagina in paginas.values():
        info = pagina.get("imageinfo", [{}])[0]
        link = info.get("url")

        if link and re.search(
            r"\.(webm|mp4|ogv|mov)(?:$|\?)",
            link,
            re.I
        ):
            resultados.append({
                "nome": pagina.get("title", ""),
                "url": link
            })

    return resultados


def baixar_video(termos, numero):
    vistos = set()

    for termo in termos:
        print("Buscando vídeo:", termo)

        try:
            resultados = pesquisar_video(termo)

            for item in resultados:
                if item["url"] in vistos:
                    continue

                vistos.add(item["url"])

                destino = f"{PASTA}/original_{numero}.video"

                try:
                    resposta = requests.get(
                        item["url"],
                        headers=HEADERS,
                        timeout=120,
                        stream=True
                    )

                    resposta.raise_for_status()

                    tamanho = 0

                    with open(destino, "wb") as arquivo:
                        for bloco in resposta.iter_content(1024 * 1024):
                            if bloco:
                                arquivo.write(bloco)
                                tamanho += len(bloco)

                                if tamanho > 250 * 1024 * 1024:
                                    raise RuntimeError(
                                        "Vídeo maior que 250 MB."
                                    )

                    if tamanho < 10000:
                        raise RuntimeError("Arquivo muito pequeno.")

                    print("Vídeo encontrado:", item["nome"])
                    return destino

                except Exception as erro:
                    print("Não foi possível usar este vídeo:", erro)

                    if os.path.exists(destino):
                        os.remove(destino)

        except Exception as erro:
            print("Busca indisponível:", erro)

    return None


def criar_cena(video_origem, destino, duracao):
    filtro = (
        f"scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},"
        "setsar=1,fps=30,format=yuv420p"
    )

    executar([
        "ffmpeg", "-y",
        "-stream_loop", "-1",
        "-i", video_origem,
        "-t", str(max(2, duracao)),
        "-vf", filtro,
        "-an",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-profile:v", "high",
        "-pix_fmt", "yuv420p",
        "-r", str(FPS),
        "-g", "60",
        "-movflags", "+faststart",
        destino
    ])


def criar_fallback(destino, titulo, duracao):
    print("Criando cena animada de apoio:", titulo)

    filtro = (
        "drawbox=x=0:y=0:w=iw:h=ih:"
        "color=0x07182f:t=fill,"
        "drawbox=x='iw/2-200+80*sin(t)':"
        "y='ih/2-200+50*cos(t)':"
        "w=400:h=400:color=0x176b9c@0.8:t=8,"
        "drawtext=text='UNIVERSO OCULTO':"
        "fontcolor=white:fontsize=54:"
        "x=(w-text_w)/2:y=(h-text_h)/2"
    )

    executar([
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c=0x07101f:s={W}x{H}:r={FPS}",
        "-vf", filtro,
        "-t", str(max(2, duracao)),
        "-an",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        destino
    ])


def criar_video():
    for arquivo in ["roteiro.md", "narracao.wav"]:
        if not os.path.exists(arquivo):
            raise FileNotFoundError(arquivo)

    os.makedirs(PASTA, exist_ok=True)

    with open("roteiro.md", encoding="utf-8") as arquivo:
        roteiro = arquivo.read()

    partes = extrair_partes(roteiro)

    duracao_audio = float(subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        "narracao.wav"
    ]).decode().strip())

    pesos = [len(texto) for _, texto in partes]
    total = sum(pesos)

    cenas = []

    for i, (titulo, texto) in enumerate(partes):
        print(f"\nPreparando cena {i+1}: {titulo}")

        duracao = duracao_audio * pesos[i] / total

        origem = baixar_video(
            termos_da_secao(titulo),
            i
        )

        destino = f"{PASTA}/cena_{i}.mp4"

        if origem:
            criar_cena(origem, destino, duracao)
        else:
            criar_fallback(destino, titulo, duracao)

        cenas.append(destino)

    with open("lista_nova.txt", "w", encoding="utf-8") as arquivo:
        for cena in cenas:
            arquivo.write(
                "file '" + os.path.abspath(cena) + "'\n"
            )

    executar([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", "lista_nova.txt",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        "-r", str(FPS),
        "-an",
        "video_novo_unido.mp4"
    ])

    executar([
        "ffmpeg", "-y",
        "-i", "video_novo_unido.mp4",
        "-i", "narracao.wav",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        "universo_oculto_novo.mp4"
    ])

    executar([
        "ffmpeg", "-v", "error",
        "-i", "universo_oculto_novo.mp4",
        "-map", "0:v:0",
        "-f", "null", "-"
    ])

    print("\nNOVA VERSÃO CRIADA E VERIFICADA!")


if __name__ == "__main__":
    criar_video()
          

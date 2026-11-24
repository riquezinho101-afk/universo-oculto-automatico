
import os
import re
import subprocess
import unicodedata
import requests

from PIL import Image, ImageOps, ImageEnhance

LARGURA = 1920
ALTURA = 1080
FPS = 30

PASTA = "cenas"

def executar(comando):
    subprocess.run(comando, check=True)


def limpar_texto(texto):
    texto = re.sub(r"\*\*(.*?)\*\*", r"\1", texto)
    texto = re.sub(r"\*(.*?)\*", r"\1", texto)
    texto = re.sub(r"\[.*?\]", "", texto)
    return texto.strip()


def normalizar(texto):
    texto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def extrair_partes(roteiro):
    partes = []
    titulo_atual = None
    linhas_atuais = []

    def salvar_parte():
        if titulo_atual:
            texto = limpar_texto("\n".join(linhas_atual))
            if len(texto) > 60:
                partes.append((titulo_atual, texto))

    for linha in roteiro.splitlines():
        linha = linha.strip()

        if not linha:
            continue

        cabecalho = re.match(r"^#{1,3}\s+(.+)$", linha)
        negrito = re.match(r"^\*\*(.+?)\*\*\s*$", linha)

        if cabecalho or negrito:
            salvar_parte()

            titulo = limpar_texto(
                cabecalho.group(1) if cabecalho else negrito.group(1)
            )

            titulo_normalizado = normalizar(titulo)

            if any(palavra in titulo_normalizado for palavra in [
                "titulo do video", "canal:", "duracao:",
                "estilo:", "tom:"
            ]):
                titulo_atual = None
                linhas_atual = []
                continue

            titulo_atual = titulo
            linhas_atual = []
            continue

        if titulo_atual is None:
            continue

        if re.match(r"^\[.*\]$", linha):
            continue

        if re.match(r"^\*\*(Canal|Duração|Estilo|Tom)\s*:", linha, re.I):
            continue

        linhas_atual.append(linha)

    salvar_parte()

    if not partes:
        raise RuntimeError(
            "Não encontrei as seções do roteiro. Verifique os títulos do arquivo roteiro.md."
        )

    return partes


def termos_de_busca(titulo):
    t = normalizar(titulo)

    if any(x in t for x in ["ringwoodita", "interior da terra", "agua no interior"]):
        return [
            "ringwoodite mineral crystal",
            "Earth mantle mineral",
            "Earth mantle scientific illustration"
        ]

    if any(x in t for x in ["terra roxa", "terra primitiva", "vida primitiva"]):
        return [
            "Archean Earth geological landscape",
            "early Earth illustration",
            "purple bacteria landscape"
        ]

    if any(x in t for x in ["hudson", "gravidade", "gravidade da terra"]):
        return [
            "Hudson Bay Canada satellite",
            "Hudson Bay aerial view",
            "Earth gravity anomaly map"
        ]

    if any(x in t for x in ["geocoroa", "exosfera", "atmosfera"]):
        return [
            "Earth geocorona ultraviolet image",
            "Earth hydrogen exosphere NASA",
            "Earth atmosphere from space"
        ]

    if any(x in t for x in ["mcmurdo", "vales secos", "antartida", "antartica"]):
        return [
            "McMurdo Dry Valleys Antarctica",
            "Antarctica dry valleys landscape",
            "Taylor Valley Antarctica"
        ]

    if any(x in t for x in ["nucleo", "centro da terra", "temperatura"]):
        return [
            "Earth inner core scientific illustration",
            "Earth layers cross section",
            "Earth core diagram"
        ]

    if any(x in t for x in ["ouro", "oceano", "agua do mar"]):
        return [
            "gold nuggets",
            "ocean seawater scientific research",
            "gold element mineral"
        ]

    if any(x in t for x in ["abertura", "introducao", "encerramento"]):
        return [
            "Earth planet from space NASA",
            "planet Earth blue marble"
        ]

    palavras = re.findall(r"[a-zA-Z]{4,}", titulo)
    busca = " ".join(palavras[:7])

    return [
        busca,
        "Earth planet " + busca
    ]


def buscar_imagem(termos, destino):
    url = "https://commons.wikimedia.org/w/api.php"

    cabecalhos = {
        "User-Agent": "UniversoOcultoVideo/1.0 (video educational project)"
    }

    for termo in termos:
        print("Procurando imagem:", termo)

        parametros = {
            "action": "query",
            "generator": "search",
            "gsrsearch": "filetype:bitmap " + termo,
            "gsrnamespace": 6,
            "gsrlimit": 15,
            "prop": "imageinfo",
            "iiprop": "url",
            "iiurlwidth": 1920,
            "format": "json"
        }

        try:
            resposta = requests.get(
                url,
                params=parametros,
                headers=cabecalhos,
                timeout=40
            )
            resposta.raise_for_status()

            paginas = resposta.json().get("query", {}).get("pages", {})

            for pagina in paginas.values():
                info = pagina.get("imageinfo", [{}])[0]
                imagem_url = info.get("thumburl") or info.get("url")

                if not imagem_url:
                    continue

                try:
                    imagem = requests.get(
                        imagem_url,
                        headers=cabecalhos,
                        timeout=40
                    )
                    imagem.raise_for_status()

                    with open(destino, "wb") as arquivo:
                        arquivo.write(imagem.content)

                    with Image.open(destino) as teste:
                        teste.verify()

                    print("Imagem encontrada:", pagina.get("title"))
                    return True

                except Exception:
                    continue

        except Exception as erro:
            print("Falha na busca:", erro)

    return False


def preparar_imagem(origem, destino):
    with Image.open(origem) as imagem:
        imagem = imagem.convert("RGB")

        imagem = ImageOps.fit(
            imagem,
            (LARGURA, ALTURA),
            method=Image.Resampling.LANCZOS
        )

        imagem = ImageEnhance.Contrast(imagem).enhance(1.10)
        imagem.save(destino, quality=95)


def criar_cena(imagem, destino, duracao):
    quadros = max(1, int(duracao * FPS))

    filtro = (
        "zoompan="
        "z='min(zoom+0.0005,1.15)':"
        "x='iw/2-(iw/zoom/2)':"
        "y='ih/2-(ih/zoom/2)':"
        f"d={quadros}:"
        f"s={LARGURA}x{ALTURA}:"
        f"fps={FPS},"
        "format=yuv420p"
    )

    executar([
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", imagem,
        "-vf", filtro,
        "-frames:v", str(quadros),
        "-an",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        destino
    ])


def criar_video():
    if not os.path.exists("narracao.wav"):
        raise FileNotFoundError("Arquivo narracao.wav não encontrado.")

    if not os.path.exists("roteiro.md"):
        raise FileNotFoundError("Arquivo roteiro.md não encontrado.")

    os.makedirs(PASTA, exist_ok=True)

    with open("roteiro.md", encoding="utf-8") as arquivo:
        roteiro = arquivo.read()

    partes = extrair_partes(roteiro)

    print("Seções encontradas:", len(partes))

    duracao_audio = float(subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        "narracao.wav"
    ]).decode().strip())

    pesos = [max(len(texto), 1) for _, texto in partes]
    total = sum(pesos)

    arquivos = []

    for numero, (titulo, texto) in enumerate(partes):
        print()
        print(f"Preparando cena {numero + 1}/{len(partes)}: {titulo}")

        duracao_cena = duracao_audio * pesos[numero] / total

        original = f"{PASTA}/original_{numero}.jpg"
        imagem = f"{PASTA}/cena_{numero}.jpg"
        video = f"{PASTA}/video_{numero}.mp4"

        termos = termos_de_busca(titulo)

        if not buscar_imagem(termos, original):
            raise RuntimeError(
                f"Não encontrei imagem para a seção: {titulo}"
            )

        preparar_imagem(original, imagem)

        criar_cena(imagem, video, duracao_cena)

        arquivos.append(video)

    with open("lista_cenas.txt", "w", encoding="utf-8") as arquivo:
        for video in arquivos:
            arquivo.write(f"file '{video}'\n")

    print()
    print("Juntando cenas e narração...")

    executar([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", "lista_cenas.txt",
        "-i", "narracao.wav",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        "universo_oculto.mp4"
    ])

    if not os.path.exists("universo_oculto.mp4"):
        raise RuntimeError("O arquivo de vídeo não foi criado.")

    print("VÍDEO CRIADO COM SUCESSO!")


if __name__ == "__main__":
    criar_video()

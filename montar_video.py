
import os
import re
import subprocess
import requests
from PIL import Image, ImageOps, ImageEnhance, ImageDraw, ImageFont

W, H, FPS = 1920, 1080, 30
PASTA = "cenas"
HEADERS = {"User-Agent": "UniversoOcultoVideo/2.0"}

BUSCAS = {
    "ABERTURA": [
        "Earth Blue Marble NASA",
        "Earth rotating in space"
    ],
    "PLANETA QUE VIBRA": [
        "ocean waves seismology microseism",
        "seismic waves Earth scientific illustration"
    ],
    "DIA QUE ESTÁ FICANDO": [
        "Earth Moon from space NASA",
        "Moon tidal forces Earth illustration"
    ],
    "DESERTO QUE NÃO É": [
        "McMurdo Dry Valleys Antarctica",
        "Antarctica polar desert landscape"
    ],
    "TERRA JÁ FOI ROXA": [
        "purple bacteria microorganisms",
        "retinal molecule purple bacteria"
    ],
    "GRAVIDADE NÃO É": [
        "Hudson Bay Canada satellite",
        "Earth gravity anomaly map"
    ],
    "NÚCLEO É TÃO QUENTE": [
        "Earth inner core cross section",
        "Earth layers scientific illustration"
    ],
    "OCEANO OCULTO": [
        "ringwoodite mineral crystal",
        "Earth mantle ringwoodite illustration"
    ],
    "ENCERRAMENTO": [
        "Earth at night from space NASA",
        "Earth planet from space"
    ]
}


def executar(cmd):
    subprocess.run(cmd, check=True)


def limpar(texto):
    texto = re.sub(r"\*\*(.*?)\*\*", r"\1", texto)
    texto = re.sub(r"\*(.*?)\*", r"\1", texto)
    return texto.strip()


def extrair_partes(roteiro):
    partes = []
    titulo = None
    linhas = []

    def salvar():
        if titulo:
            texto = limpar(" ".join(linhas))
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

        if not titulo or not linha:
            continue

        if linha.startswith("(") or linha.startswith("**("):
            continue

        linha = re.sub(r"^\*\*Locutor:\*\*\s*", "", linha)
        linha = re.sub(r"^Locutor:\s*", "", linha)

        if linha:
            linhas.append(linha)

    salvar()

    if len(partes) < 5:
        raise RuntimeError(
            f"Roteiro incompatível: encontrei {len(partes)} seções."
        )

    return partes


def buscas_do_titulo(titulo):
    t = titulo.upper()

    for chave, termos in BUSCAS.items():
        if chave in t:
            return termos

    return ["Earth planet from space", "Earth landscape"]


def buscar_imagens(termo, quantidade=5):
    url = "https://commons.wikimedia.org/w/api.php"

    parametros = {
        "action": "query",
        "generator": "search",
        "gsrsearch": "filetype:bitmap " + termo,
        "gsrnamespace": 6,
        "gsrlimit": quantidade,
        "prop": "imageinfo",
        "iiprop": "url",
        "iiurlwidth": 1920,
        "format": "json"
    }

    resposta = requests.get(
        url,
        params=parametros,
        headers=HEADERS,
        timeout=45
    )
    resposta.raise_for_status()

    paginas = resposta.json().get("query", {}).get("pages", {})
    resultados = []

    for pagina in paginas.values():
        info = pagina.get("imageinfo", [{}])[0]
        link = info.get("thumburl") or info.get("url")

        if link:
            resultados.append((pagina.get("title", ""), link))

    return resultados


def baixar_duas_imagens(termos, numero):
    encontradas = []
    nomes = set()

    for termo in termos:
        print("Pesquisando:", termo)

        try:
            resultados = buscar_imagens(termo)

            for nome, link in resultados:
                if nome in nomes:
                    continue

                try:
                    resposta = requests.get(
                        link,
                        headers=HEADERS,
                        timeout=45
                    )
                    resposta.raise_for_status()

                    caminho = f"{PASTA}/original_{numero}_{len(encontradas)}.jpg"

                    with open(caminho, "wb") as f:
                        f.write(resposta.content)

                    with Image.open(caminho) as img:
                        img.verify()

                    nomes.add(nome)
                    encontradas.append(caminho)

                    print("Imagem encontrada:", nome)

                    if len(encontradas) == 2:
                        return encontradas

                except Exception:
                    continue

        except Exception as erro:
            print("Busca temporariamente indisponível:", erro)

    if not encontradas:
        raise RuntimeError(
            f"Nenhuma imagem encontrada para a cena {numero + 1}."
        )

    # Se só uma imagem foi encontrada, não inventa outra.
    # O mesmo arquivo poderá receber movimentos diferentes.
    if len(encontradas) == 1:
        encontradas.append(encontradas[0])

    return encontradas


def preparar_imagem(origem, destino, titulo):
    with Image.open(origem) as img:
        img = img.convert("RGB")
        img = ImageOps.fit(
            img,
            (W, H),
            method=Image.Resampling.LANCZOS
        )

        img = ImageEnhance.Contrast(img).enhance(1.10)

        camada = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        desenho = ImageDraw.Draw(camada)

        desenho.rectangle(
            (0, 850, W, H),
            fill=(0, 0, 0, 175)
        )

        try:
            fonte = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                48
            )
        except Exception:
            fonte = ImageFont.load_default()

        titulo = titulo.upper()[:65]

        desenho.text(
            (75, 900),
            titulo,
            font=fonte,
            fill=(255, 255, 255, 255)
        )

        img = Image.alpha_composite(
            img.convert("RGBA"),
            camada
        )

        img.convert("RGB").save(destino, quality=95)


def criar_clipe(imagem, destino, duracao, movimento):
    quadros = max(1, int(duracao * FPS))

    if movimento == 0:
        zoom = "min(zoom+0.0005,1.15)"
        x = "iw/2-(iw/zoom/2)"
    else:
        zoom = "min(zoom+0.0005,1.15)"
        x = "iw/2-(iw/zoom/2)"

    filtro = (
        f"zoompan=z='{zoom}':"
        f"x='{x}':"
        "y='ih/2-(ih/zoom/2)':"
        f"d={quadros}:"
        f"s={W}x{H}:"
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
    for arquivo in ["roteiro.md", "narracao.wav"]:
        if not os.path.exists(arquivo):
            raise FileNotFoundError(arquivo)

    os.makedirs(PASTA, exist_ok=True)

    with open("roteiro.md", encoding="utf-8") as f:
        roteiro = f.read()

    partes = extrair_partes(roteiro)

    print("Seções identificadas:", len(partes))

    duracao_audio = float(subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        "narracao.wav"
    ]).decode().strip())

    pesos = [len(texto) for _, texto in partes]
    total = sum(pesos)

    lista = []

    for i, (titulo, texto) in enumerate(partes):
        print(f"\nPreparando seção {i + 1}: {titulo}")

        duracao_secao = duracao_audio * pesos[i] / total
        duracao_clipe = duracao_secao / 2

        termos = buscas_do_titulo(titulo)
        originais = baixar_duas_imagens(termos, i)

        for j, original in enumerate(originais):
            imagem = f"{PASTA}/final_{i}_{j}.jpg"
            video = f"{PASTA}/clipe_{i}_{j}.mp4"

            preparar_imagem(original, imagem, titulo)

            criar_clipe(
                imagem,
                video,
                duracao_clipe,
                j
            )

            lista.append(video)

    with open("lista_cenas.txt", "w", encoding="utf-8") as f:
        for video in lista:
            f.write(f"file '{video}'\n")

    print("\nMontando vídeo e narração...")

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
        raise RuntimeError("O vídeo não foi criado.")

    print("\nVÍDEO CRIADO COM SUCESSO!")


if __name__ == "__main__":
    criar_video()

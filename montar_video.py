import os
import re
import math
import subprocess
import requests
from PIL import Image, ImageOps, ImageEnhance, ImageDraw, ImageFont

W, H, FPS = 1920, 1080, 30
PASTA = "cenas"
HEADERS = {"User-Agent": "UniversoOculto/3.1"}

BUSCAS = {
    "ABERTURA": ["Earth Blue Marble NASA", "Earth from space"],
    "PLANETA QUE VIBRA": [
        "seismograph", "seismometer", "seismic waves",
        "ocean waves", "earthquake seismogram"
    ],
    "DIA QUE ESTÁ FICANDO": [
        "Earth Moon from space NASA",
        "Moon tidal forces Earth", "Earth rotation"
    ],
    "DESERTO QUE NÃO É": [
        "McMurdo Dry Valleys Antarctica",
        "Antarctica polar desert", "Antarctic landscape"
    ],
    "TERRA JÁ FOI ROXA": [
        "purple bacteria", "purple microorganisms", "halobacteria"
    ],
    "GRAVIDADE NÃO É": [
        "Hudson Bay Canada satellite",
        "Earth gravity anomaly map", "Earth geoid gravity"
    ],
    "NÚCLEO É TÃO QUENTE": [
        "Earth inner core cross section",
        "Earth layers diagram", "Earth core illustration"
    ],
    "OCEANO OCULTO": [
        "ringwoodite mineral", "Earth mantle ringwoodite",
        "water in Earth's mantle"
    ],
    "ENCERRAMENTO": [
        "Earth at night from space NASA",
        "Earth planet from space", "Blue Marble Earth"
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


def buscar_imagens(termo):
    url = "https://commons.wikimedia.org/w/api.php"

    parametros = {
        "action": "query",
        "generator": "search",
        "gsrsearch": "filetype:bitmap " + termo,
        "gsrnamespace": 6,
        "gsrlimit": 8,
        "prop": "imageinfo",
        "iiprop": "url",
        "iiurlwidth": 1920,
        "format": "json"
    }

    resposta = requests.get(
        url, params=parametros,
        headers=HEADERS, timeout=45
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


def baixar_arquivo(link, caminho):
    resposta = requests.get(
        link, headers=HEADERS, timeout=60
    )
    resposta.raise_for_status()

    with open(caminho, "wb") as f:
        f.write(resposta.content)

    with Image.open(caminho) as img:
        img.verify()

    return caminho


def criar_fallback(titulo, destino, variacao):
    print("Criando ilustração de apoio:", titulo)

    img = Image.new("RGB", (W, H), (8, 13, 30))
    draw = ImageDraw.Draw(img)

    for y in range(H):
        tom = int(12 + 22 * y / H)
        draw.line((0, y, W, y), fill=(5, tom, tom + 28))

    cx, cy = 1450, 430
    raio = 230 + variacao * 25

    draw.ellipse(
        (cx-raio, cy-raio, cx+raio, cy+raio),
        fill=(20, 80, 135),
        outline=(100, 190, 230),
        width=8
    )

    draw.arc(
        (cx-raio+35, cy-raio+35,
         cx+raio-35, cy+raio-35),
        20, 300, fill=(80, 180, 130), width=18
    )

    try:
        fonte = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            62
        )
        menor = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            30
        )
    except Exception:
        fonte = ImageFont.load_default()
        menor = fonte

    draw.text(
        (100, 390), limpar(titulo).upper()[:55],
        font=fonte, fill=(255, 255, 255)
    )

    draw.text(
        (105, 490), "UNIVERSO OCULTO",
        font=menor, fill=(120, 205, 235)
    )

    if variacao == 0:
        for x in range(100, 1100, 45):
            altura = 25 + abs(math.sin(x / 45)) * 100
            draw.line(
                (x, 750, x, 750-altura),
                fill=(80, 190, 220), width=5
            )
    else:
        for i in range(8):
            y = 700 + i * 30
            draw.arc(
                (100+i*20, y-100, 900, y+150),
                0, 180, fill=(80, 160, 210), width=4
            )

    img.save(destino, quality=94)


def baixar_duas_imagens(termos, numero, titulo):
    encontradas = []
    nomes = set()

    for termo in termos:
        print("Pesquisando:", termo)

        try:
            resultados = buscar_imagens(termo)

            for nome, link in resultados:
                if nome in nomes:
                    continue

                caminho = (
                    f"{PASTA}/original_{numero}_{len(encontradas)}.jpg"
                )

                try:
                    baixar_arquivo(link, caminho)
                    nomes.add(nome)
                    encontradas.append(caminho)
                    print("Imagem encontrada:", nome)

                    if len(encontradas) == 2:
                        return encontradas

                except Exception as erro:
                    print("Imagem ignorada:", erro)

        except Exception as erro:
            print("Busca indisponível:", erro)

    while len(encontradas) < 2:
        destino = (
            f"{PASTA}/fallback_{numero}_{len(encontradas)}.jpg"
        )
        criar_fallback(titulo, destino, len(encontradas))
        encontradas.append(destino)

    return encontradas


def preparar_imagem(origem, destino, titulo):
    with Image.open(origem) as img:
        img = img.convert("RGB")

        img = ImageOps.fit(
            img, (W, H),
            method=Image.Resampling.LANCZOS
        )

        img = ImageEnhance.Contrast(img).enhance(1.08)

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

        desenho.text(
            (75, 900),
            limpar(titulo).upper()[:65],
            font=fonte,
            fill=(255, 255, 255, 255)
        )

        img = Image.alpha_composite(
            img.convert("RGBA"), camada
        )

        img.convert("RGB").save(destino, quality=95)


def criar_clipe(imagem, destino, duracao, movimento):
    quadros = max(1, int(duracao * FPS))

    if movimento == 0:
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"
    else:
        x = "iw/2-(iw/zoom/2)+sin(on/45)*35"
        y = "ih/2-(ih/zoom/2)+cos(on/55)*20"

    filtro = (
        "scale=2200:-2,"
        "zoompan="
        "z='min(zoom+0.0007,1.18)':"
        f"x='{x}':y='{y}':"
        f"d={quadros}:"
        f"s={W}x{H}:"
        f"fps={FPS},"
        "setsar=1,format=yuv420p"
    )

    executar([
        "ffmpeg", "-y",
        "-loop", "1", "-framerate", str(FPS),
        "-i", imagem,
        "-vf", filtro,
        "-frames:v", str(quadros),
        "-an",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "stillimage",
        "-profile:v", "high",
        "-level", "4.1",
        "-pix_fmt", "yuv420p",
        "-r", str(FPS),
        "-g", "60",
        "-bf", "0",
        "-f", "mpegts",
        destino
    ])


def verificar_video(caminho):
    print("\nVerificando integridade do vídeo...")

    executar([
        "ffmpeg",
        "-v", "error",
        "-i", caminho,
        "-map", "0:v:0",
        "-f", "null",
        "-"
    ])

    duracao = float(subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        caminho
    ]).decode().strip())

    if duracao <= 0:
        raise RuntimeError("Duração inválida no vídeo final.")

    print(f"Verificação concluída. Duração: {duracao:.2f} segundos.")


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
        print(f"\nPreparando seção {i+1}: {titulo}")

        duracao_secao = duracao_audio * pesos[i] / total
        duracao_clipe = duracao_secao / 2

        originais = baixar_duas_imagens(
            buscas_do_titulo(titulo), i, titulo
        )

        for j, original in enumerate(originais):
            imagem = f"{PASTA}/final_{i}_{j}.jpg"
            video = f"{PASTA}/clipe_{i}_{j}.ts"

            preparar_imagem(original, imagem, titulo)
            criar_clipe(imagem, video, duracao_clipe, j)

            lista.append(video)

    with open("lista_cenas.txt", "w", encoding="utf-8") as f:
        for video in lista:
            f.write(f"file '{os.path.abspath(video)}'\n")

    print("\nUnindo cenas em MPEG-TS...")

    executar([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", "lista_cenas.txt",
        "-c", "copy",
        "-f", "mpegts",
        "video_unido.ts"
    ])

    print("\nAdicionando narração...")

    executar([
        "ffmpeg", "-y",
        "-fflags", "+genpts",
        "-i", "video_unido.ts",
        "-i", "narracao.wav",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-af", "aresample=async=1:first_pts=0",
        "-shortest",
        "-avoid_negative_ts", "make_zero",
        "-movflags", "+faststart",
        "universo_oculto.mp4"
    ])

    if not os.path.exists("universo_oculto.mp4"):
        raise RuntimeError("O vídeo final não foi criado.")

    verificar_video("universo_oculto.mp4")

    print("\nVÍDEO CRIADO E VERIFICADO COM SUCESSO!")


if __name__ == "__main__":
    criar_video()
    

import os
import re
import subprocess
import requests
from PIL import Image, ImageOps, ImageEnhance

LARGURA = 1920
ALTURA = 1080
FPS = 30

def executar(comando):
    subprocess.run(comando, check=True)

def buscar_imagem(termo, destino):
    url = "https://commons.wikimedia.org/w/api.php"

    parametros = {
        "action": "query",
        "generator": "search",
        "gsrsearch": f"filetype:bitmap {termo}",
        "gsrnamespace": 6,
        "gsrlimit": 10,
        "prop": "imageinfo",
        "iiprop": "url",
        "iiurlwidth": 1920,
        "format": "json"
    }

    resposta = requests.get(
        url,
        params=parametros,
        headers={"User-Agent": "UniversoOcultoVideo/1.0"},
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
            imagem = requests.get(imagem_url, timeout=40)
            imagem.raise_for_status()

            with open(destino, "wb") as arquivo:
                arquivo.write(imagem.content)

            with Image.open(destino) as teste:
                teste.verify()

            return True
        except Exception:
            continue

    return False

def preparar_imagem(origem, destino):
    with Image.open(origem) as imagem:
        imagem = imagem.convert("RGB")
        imagem = ImageOps.fit(
            imagem,
            (LARGURA, ALTURA),
            method=Image.Resampling.LANCZOS
        )
        imagem = ImageEnhance.Contrast(imagem).enhance(1.12)
        imagem.save(destino, quality=95)

def extrair_partes(roteiro):
    partes = re.split(r"(?m)^#{1,3}\s+", roteiro)
    resultado = []

    for parte in partes:
        linhas = parte.strip().splitlines()

        if not linhas:
            continue

        titulo = linhas[0].strip()
        texto = "\n".join(linhas[1:]).strip()

        texto = re.sub(r"\[.*?\]", "", texto)
        texto = re.sub(r"\*\*(.*?)\*\*", r"\1", texto)

        if len(texto) > 80:
            resultado.append((titulo, texto))

    return resultado

def criar_video():
    if not os.path.exists("narracao.wav"):
        raise FileNotFoundError("Arquivo narracao.wav não encontrado.")

    if not os.path.exists("roteiro.md"):
        raise FileNotFoundError("Arquivo roteiro.md não encontrado.")

    with open("roteiro.md", encoding="utf-8") as arquivo:
        roteiro = arquivo.read()

    partes = extrair_partes(roteiro)

    if not partes:
        raise RuntimeError("Não consegui identificar as partes do roteiro.")

    os.makedirs("cenas", exist_ok=True)

    duracao = float(subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        "narracao.wav"
    ]).decode().strip())

    pesos = [max(len(texto), 1) for _, texto in partes]
    total = sum(pesos)

    arquivos = []
    tempo_inicio = 0

    for numero, (titulo, texto) in enumerate(partes):
        print(f"Preparando cena {numero + 1}: {titulo}")

        duracao_cena = duracao * pesos[numero] / total

        original = f"cenas/original_{numero}.jpg"
        imagem = f"cenas/cena_{numero}.jpg"
        video = f"cenas/video_{numero}.mp4"

        termo = titulo.replace(":", " ").replace("-", " ")
        sucesso = buscar_imagem(
            f"Earth planet {termo}",
            original
        )

        if not sucesso:
            sucesso = buscar_imagem("planet Earth from space", original)

        if not sucesso:
            raise RuntimeError(
                f"Não foi possível encontrar imagem para: {titulo}"
            )

        preparar_imagem(original, imagem)

        quadros = max(1, int(duracao_cena * FPS))

        executar([
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", imagem,
            "-vf",
            (
                f"zoompan=z='min(zoom+0.0005,1.12)':"
                f"x='iw/2-(iw/zoom/2)':"
                f"y='ih/2-(ih/zoom/2)':"
                f"d={quadros}:s={LARGURA}x{ALTURA}:fps={FPS},"
                "format=yuv420p"
            ),
            "-frames:v", str(quadros),
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            video
        ])

        arquivos.append(video)
        tempo_inicio += duracao_cena

    with open("lista_cenas.txt", "w") as arquivo:
        for video in arquivos:
            arquivo.write(f"file '{video}'\n")

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

    print("VÍDEO CRIADO COM SUCESSO!")

if __name__ == "__main__":
    criar_video()


import os
import re
import subprocess
import requests
from PIL import Image, ImageOps, ImageEnhance

W = 1920
H = 1080
FPS = 30
PASTA = "cenas"

def executar(cmd):
    subprocess.run(cmd, check=True)

def limpar_texto(texto):
    texto = re.sub(r"\*\*(.*?)\*\*", r"\1", texto)
    texto = re.sub(r"\*(.*?)\*", r"\1", texto)
    texto = texto.replace('"', '')
    return texto.strip()

def extrair_partes(roteiro):
    partes = []
    titulo = None
    linhas = []

    def salvar():
        if titulo:
            texto = limpar_texto("\n".join(linhas))
            if len(texto) > 40:
                partes.append((titulo, texto))

    for linha in roteiro.splitlines():
        linha = linha.strip()

        # Reconhece os títulos reais do roteiro
        cabecalho = re.match(
            r"^\[(ABERTURA|PARTE\s*\d+\s*:.*|ENCERRAMENTO)\]$",
            linha,
            re.IGNORECASE
        )

        if cabecalho:
            salvar()
            titulo = cabecalho.group(1).strip()
            linhas = []
            continue

        if not titulo or not linha:
            continue

        # Ignora instruções visuais, trilha e efeitos
        if linha.startswith("(") or linha.startswith("**("):
            continue

        # Remove identificação do locutor
        linha = re.sub(r"^\*\*Locutor:\*\*\s*", "", linha)
        linha = re.sub(r"^Locutor:\s*", "", linha)

        if linha:
            linhas.append(linha)

    salvar()

    if len(partes) < 5:
        raise RuntimeError(
            f"Foram encontradas apenas {len(partes)} seções. "
            "Verifique se roteiro.md contém os títulos entre colchetes."
        )

    return partes

def termos_de_busca(titulo):
    t = titulo.lower()

    if "abertura" in t:
        return ["Earth Blue Marble NASA", "planet Earth from space"]

    if "planeta que vibra" in t:
        return ["Earth seismic waves ocean microseism", "ocean waves seismology"]

    if "dia que está ficando" in t:
        return ["Earth Moon from space NASA", "Earth Moon tidal interaction"]

    if "deserto que não é" in t:
        return ["McMurdo Dry Valleys Antarctica", "Antarctica polar desert"]

    if "terra já foi roxa" in t:
        return ["purple Earth hypothesis retinal", "purple bacteria microorganisms"]

    if "gravidade não é igual" in t:
        return ["Hudson Bay Canada satellite", "Earth gravity anomaly map"]

    if "núcleo é tão quente" in t:
        return ["Earth inner core cutaway illustration", "Earth layers core diagram"]

    if "oceano oculto" in t:
        return ["ringwoodite mineral crystal", "Earth mantle ringwoodite"]

    if "encerramento" in t:
        return ["Earth at night from space NASA", "Earth planet from space"]

    return ["planet Earth from space"]

def buscar_imagem(termos, destino):
    url = "https://commons.wikimedia.org/w/api.php"

    cabecalho = {
        "User-Agent": "UniversoOcultoVideo/1.0"
    }

    for termo in termos:
        print("Buscando:", termo)

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
                headers=cabecalho,
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
                    img = requests.get(
                        imagem_url,
                        headers=cabecalho,
                        timeout=40
                    )
                    img.raise_for_status()

                    with open(destino, "wb") as f:
                        f.write(img.content)

                    with Image.open(destino) as teste:
                        teste.verify()

                    print("Imagem encontrada:", pagina.get("title"))
                    return True

                except Exception:
                    continue

        except Exception as erro:
            print("Erro na busca:", erro)

    return False

def preparar_imagem(origem, destino):
    with Image.open(origem) as img:
        img = img.convert("RGB")
        img = ImageOps.fit(
            img,
            (W, H),
            method=Image.Resampling.LANCZOS
        )
        img = ImageEnhance.Contrast(img).enhance(1.10)
        img.save(destino, quality=95)

def criar_cena(imagem, destino, duracao):
    quadros = max(1, int(duracao * FPS))

    filtro = (
        "zoompan="
        "z='min(zoom+0.0005,1.15)':"
        "x='iw/2-(iw/zoom/2)':"
        "y='ih/2-(ih/zoom/2)':"
        f"d={quadros}:"
        f"s={W}x{H}:"
        f"fps={FPS},format=yuv420p"
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
            raise FileNotFoundError(f"Arquivo não encontrado: {arquivo}")

    os.makedirs(PASTA, exist_ok=True)

    with open("roteiro.md", encoding="utf-8") as f:
        roteiro = f.read()

    partes = extrair_partes(roteiro)

    print(f"Seções identificadas: {len(partes)}")

    duracao_audio = float(subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        "narracao.wav"
    ]).decode().strip())

    pesos = [len(texto) for _, texto in partes]
    total = sum(pesos)
    videos = []

    for i, (titulo, texto) in enumerate(partes):
        print(f"\nCena {i + 1}/{len(partes)}: {titulo}")

        duracao = duracao_audio * pesos[i] / total

        original = f"{PASTA}/original_{i}.jpg"
        imagem = f"{PASTA}/cena_{i}.jpg"
        video = f"{PASTA}/video_{i}.mp4"

        if not buscar_imagem(termos_de_busca(titulo), original):
            raise RuntimeError(
                f"Não foi possível encontrar imagem para: {titulo}"
            )

        preparar_imagem(original, imagem)
        criar_cena(imagem, video, duracao)
        videos.append(video)

    with open("lista_cenas.txt", "w", encoding="utf-8") as f:
        for video in videos:
            f.write(f"file '{video}'\n")

    print("\nJuntando vídeo e narração...")

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

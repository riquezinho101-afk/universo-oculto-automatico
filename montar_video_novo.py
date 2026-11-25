import os
import re
import json
import subprocess
import requests
from urllib.parse import quote

FPS = 30
W, H = 1920, 1080
PASTA = "cenas_novas"
MAX_VIDEO_BYTES = 250 * 1024 * 1024
MAX_RESULTS = 30

HEADERS = {
    "User-Agent": "UniversoOculto/5.0 (video production; contact: channel owner)"
}

BUSCAS = {
    "ABERTURA": ["Earth from space", "Earth rotation"],
    "PLANETA QUE VIBRA": [
        "ocean waves", "seismograph", "earthquake",
        "microseism ocean waves"
    ],
    "DIA QUE ESTÁ FICANDO": [
        "Earth rotation", "Earth day length", "Earth rotation animation"
    ],
    "DESERTO QUE NÃO É": [
        "Antarctica dry valleys", "McMurdo Dry Valleys",
        "Antarctic desert landscape"
    ],
    "TERRA JÁ FOI ROXA": [
        "halobacteria", "purple bacteria", "halophile archaea"
    ],
    "GRAVIDADE NÃO É": [
        "Earth gravity", "gravity field Earth", "satellite orbit Earth"
    ],
    "NÚCLEO É TÃO QUENTE": [
        "Earth core", "Earth interior", "Earth layers animation"
    ],
    "OCEANO OCULTO": [
        "Earth mantle", "ringwoodite mineral", "deep Earth water"
    ],
    "ENCERRAMENTO": ["Earth from space", "Earth at night"]
}

API_COMMONS = "https://commons.wikimedia.org/w/api.php"


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
            f"Foram encontradas apenas {len(partes)} seções no roteiro."
        )
    return partes


def termos_da_secao(titulo):
    titulo = titulo.upper()
    for chave, termos in BUSCAS.items():
        if chave in titulo:
            return termos
    # Não usar uma busca genérica por Terra para qualquer seção.
    return []


def pesquisar_video(termo):
    parametros = {
        "action": "query",
        "generator": "search",
        "gsrsearch": f"{termo} filetype:video",
        "gsrnamespace": 6,
        "gsrlimit": MAX_RESULTS,
        "prop": "imageinfo",
        "iiprop": "url|mime|size|extmetadata",
        "format": "json"
    }

    resposta = requests.get(
        API_COMMONS,
        params=parametros,
        headers=HEADERS,
        timeout=45
    )
    resposta.raise_for_status()
    dados = resposta.json()

    resultados = []
    paginas = dados.get("query", {}).get("pages", {})

    for pagina in paginas.values():
        infos = pagina.get("imageinfo", [])
        if not infos:
            continue

        info = infos[0]
        link = info.get("url", "")
        mime = info.get("mime", "")
        tamanho = info.get("size", 0)

        if not link or not mime.startswith("video/"):
            continue
        if tamanho and tamanho > MAX_VIDEO_BYTES:
            continue

        meta = info.get("extmetadata", {})
        def meta_value(chave):
            valor = meta.get(chave, {}).get("value", "")
            return re.sub(r"<[^>]+>", "", str(valor)).strip()

        resultados.append({
            "nome": pagina.get("title", ""),
            "url": link,
            "mime": mime,
            "size": tamanho,
            "licenca": meta_value("LicenseShortName"),
            "termos_licenca": meta_value("UsageTerms"),
            "autor": meta_value("Artist"),
            "credito": meta_value("Credit"),
            "url_licenca": meta_value("LicenseUrl"),
            "atribuicao": meta_value("AttributionRequired")
        })

    return resultados


def validar_video(caminho):
    """Confirma que o arquivo baixado contém um fluxo de vídeo legível."""
    resultado = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_type,width,height",
            "-of", "json", caminho
        ],
        check=True,
        capture_output=True,
        text=True
    )
    dados = json.loads(resultado.stdout or "{}")
    return bool(dados.get("streams"))


def baixar_video(termos, numero):
    vistos = set()
    destino = f"{PASTA}/original_{numero}.video"

    for termo in termos:
        print("Pesquisando no Wikimedia Commons:", termo)

        try:
            resultados = pesquisar_video(termo)
        except Exception as erro:
            print("Falha na pesquisa:", erro)
            continue

        for item in resultados:
            url = item["url"]
            if url in vistos:
                continue
            vistos.add(url)

            try:
                print("Testando arquivo:", item["nome"])
                resposta = requests.get(
                    url,
                    headers=HEADERS,
                    timeout=(30, 120),
                    stream=True
                )
                resposta.raise_for_status()

                tamanho = 0
                with open(destino, "wb") as arquivo:
                    for bloco in resposta.iter_content(1024 * 1024):
                        if not bloco:
                            continue
                        tamanho += len(bloco)
                        if tamanho > MAX_VIDEO_BYTES:
                            raise RuntimeError("Arquivo excede 250 MB.")
                        arquivo.write(bloco)

                if tamanho < 10000:
                    raise RuntimeError("Arquivo baixado é pequeno demais.")

                if not validar_video(destino):
                    raise RuntimeError("O arquivo não contém vídeo válido.")

                item["arquivo_local"] = destino
                print("Vídeo válido encontrado:", item["nome"])
                return item

            except Exception as erro:
                print("Arquivo descartado:", erro)
                if os.path.exists(destino):
                    os.remove(destino)

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
    if total <= 0:
        raise RuntimeError("O roteiro não contém texto suficiente.")

    cenas = []
    creditos = []

    for i, (titulo, texto) in enumerate(partes):
        print(f"\nPreparando cena {i + 1}: {titulo}")
        duracao = duracao_audio * pesos[i] / total

        termos = termos_da_secao(titulo)
        if not termos:
            raise RuntimeError(
                f"Não há termos de pesquisa definidos para a seção: {titulo}"
            )

        item = baixar_video(termos, i)
        if not item:
            raise RuntimeError(
                f"Nenhum vídeo válido foi encontrado para '{titulo}'. "
                "A geração foi interrompida para não inserir uma tela genérica."
            )

        destino = f"{PASTA}/cena_{i}.mp4"
        criar_cena(item["arquivo_local"], destino, duracao)
        cenas.append(destino)

        creditos.append(
            "\n".join([
                f"Seção: {titulo}",
                f"Arquivo: {item['nome']}",
                f"Autor: {item.get('autor') or 'Não informado nos metadados'}",
                f"Crédito: {item.get('credito') or 'Não informado nos metadados'}",
                f"Licença: {item.get('licenca') or 'Verificar na página do arquivo'}",
                f"Termos: {item.get('termos_licenca') or 'Verificar na página do arquivo'}",
                f"URL da licença: {item.get('url_licenca') or 'Ver página do arquivo'}",
                f"Página do arquivo: https://commons.wikimedia.org/wiki/{quote(item['nome'].replace(' ', '_'))}",
                "Confira as condições de atribuição e uso antes de publicar."
            ])
        )

    with open("creditos_cenas.txt", "w", encoding="utf-8") as arquivo:
        arquivo.write(
            "\n\n" + ("-" * 60) + "\n\n".join(creditos)
        )

    with open("lista_nova.txt", "w", encoding="utf-8") as arquivo:
        for cena in cenas:
            caminho = os.path.abspath(cena).replace("\\", "\\\\").replace("'", r"'\''")
            arquivo.write(f"file '{caminho}'\n")

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
    print("Confira também o arquivo creditos_cenas.txt antes de publicar.")


if __name__ == "__main__":
    criar_video()

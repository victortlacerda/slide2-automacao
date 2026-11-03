"""Regenera as imagens do README a partir do script rodando de verdade nos DXFs de exemplo.

Rodar da raiz do repositório:   python docs/gerar_imagens.py
Precisa do LibreOffice (soffice) e do pdftoppm para a imagem da planilha.
"""
import builtins
import importlib.util
import io
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import openpyxl  # noqa: E402
from PIL import Image, ImageChops  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "docs" / "imagens"
DXF = RAIZ / "exemplos" / "quatro_secoes_em_grade.dxf"
JANELAS = [(-3, -18, 46, 9), (57, -19, 106, 11), (-3, -57, 46, -29), (57, -57, 106, -32)]

spec = importlib.util.spec_from_file_location(
    "cad_para_planilha", RAIZ / "modulos" / "02_cad_para_planilha" / "cad_para_planilha.py")
cpp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cpp)


def recortar(png, margem=12):
    img = Image.open(png).convert("RGB")
    fundo = Image.new("RGB", img.size, (255, 255, 255))
    caixa = ImageChops.difference(img, fundo).getbbox()
    if caixa:
        x0, y0, x1, y1 = caixa
        img = img.crop((max(x0 - margem, 0), max(y0 - margem, 0),
                        min(x1 + margem, img.width), min(y1 + margem, img.height)))
    img.save(png)


def janelas_dict():
    return [{"nome": f"Secao_{k:02d}", "xmin": a, "ymin": b, "xmax": c, "ymax": d}
            for k, (a, b, c, d) in enumerate(JANELAS, 1)]


class Gravador(io.StringIO):
    """Guarda o que o script escreve no terminal, separando perguntas e respostas."""

    def __init__(self):
        super().__init__()
        self.trechos = []

    def write(self, s):
        self.trechos.append(("saida", s))
        return len(s)


def rodada_terminal(pasta):
    respostas = iter(["m", "", "s", "1", "janela"])
    grav = Gravador()

    def falso_input(prompt=""):
        grav.trechos.append(("pergunta", prompt))
        r = next(respostas)
        grav.trechos.append(("resposta", (r or "") + "\n"))
        return r

    orig_input, orig_sel = builtins.input, cpp.selecionar_janelas
    builtins.input = falso_input
    cpp.selecionar_janelas = lambda itens: janelas_dict()  # as janelas que o usuário desenharia na tela
    dxf = pasta / DXF.name
    shutil.copy(DXF, dxf)
    stdout = sys.stdout
    sys.stdout = grav
    try:
        rc = cpp.main([str(dxf)])
    finally:
        sys.stdout = stdout
        builtins.input, cpp.selecionar_janelas = orig_input, orig_sel
    assert rc == 0, "a rodada de exemplo falhou"
    return grav.trechos, pasta / (DXF.stem + "_secoes.xlsx")


def imagem_terminal(trechos, pasta, destino):
    cores = {"pergunta": "#E6EDF3", "resposta": "#7EE787", "saida": "#9DA7B3"}
    # reconstrói cor por linha: perguntas e respostas ficam na mesma linha
    estilo = []
    for tipo, t in [("cmd", "> python cad_para_planilha.py\n"), ("saida", "\n")] + trechos:
        t = t.replace(str(pasta) + "/", "").replace(str(pasta), ".")
        partes = t.split("\n")
        for i, p in enumerate(partes):
            if not estilo or estilo[-1][1]:
                estilo.append([[], False])
            if p:
                estilo[-1][0].append((tipo, p))
            if i < len(partes) - 1:
                estilo[-1][1] = True
    estilo = [seg for seg in estilo if not any(p.startswith("Abrindo a tela") for _, p in seg[0])]
    largura_max = 130  # quebra linhas longas (avisos) para caberem na imagem
    quebradas = []
    for segs, fim in estilo:
        if len(segs) == 1 and len(segs[0][1]) > largura_max:
            tipo, t = segs[0]
            import textwrap
            for k, pedaco in enumerate(textwrap.wrap(t, largura_max, subsequent_indent="      ")):
                quebradas.append([[(tipo, pedaco)], True])
        else:
            quebradas.append([segs, fim])
    estilo = quebradas
    altura = 0.22 * len(estilo) + 0.7
    fig = plt.figure(figsize=(11.5, altura), dpi=130)
    fig.patch.set_facecolor("#0D1117")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    passo = 1 / (len(estilo) + 2)
    for n, (segs, _) in enumerate(estilo, 1):
        x = 0.02
        y = 1 - n * passo
        for tipo, p in segs:
            cor = {"cmd": "#58A6FF", **cores}.get(tipo, "#9DA7B3")
            peso = "bold" if tipo in ("resposta", "cmd") else "normal"
            t = ax.text(x, y, p, family="DejaVu Sans Mono", fontsize=8.6, color=cor, weight=peso, va="center")
            fig.canvas.draw()
            bb = t.get_window_extent().transformed(ax.transAxes.inverted())
            x = bb.x1
    fig.savefig(destino, facecolor=fig.get_facecolor())
    plt.close(fig)


def imagem_selecao(itens, destino):
    s = cpp.SeletorJanelas(itens, plt)
    for a, b, c, d in JANELAS[:3]:
        s.sel.extents = (a, c, b, d)
        s.tecla(type("E", (), {"key": "enter"})())
    a, b, c, d = JANELAS[3]
    s.sel.extents = (a, c, b, d)  # quarta janela sendo desenhada, ainda sem ENTER
    s.fig.savefig(destino, dpi=110, bbox_inches="tight")
    plt.close(s.fig)


def planilha_preenchida(xlsx, pasta):
    wb = openpyxl.load_workbook(xlsx)
    mats = [("Aterro", 18, 19, 5, 28), ("Argila siltosa", 17, 18, 15, 24), ("Silte arenoso", 19, 20, 8, 31),
            ("Argila mole", 15, 16, 8, 18)]
    for i, m in enumerate(mats, 2):
        for j, v in enumerate(m, 1):
            wb["Materiais"].cell(row=i, column=j, value=v)
    escolha = {(1, 1): "Aterro", (1, 2): "Argila siltosa", (1, 3): "Silte arenoso",
               (2, 1): "Aterro", (2, 2): "Argila siltosa", (2, 3): "Silte arenoso",
               (3, 1): "Argila siltosa", (3, 2): "Silte arenoso",
               (4, 1): "Silte arenoso", (4, 2): "Argila mole"}
    ws = wb["Regioes"]
    for r in range(2, ws.max_row + 1):
        ws.cell(row=r, column=6, value=escolha.get((ws.cell(row=r, column=1).value, ws.cell(row=r, column=2).value)))
    for nome in list(wb.sheetnames):
        if nome not in ("Regioes",):
            wb[nome].sheet_state = "hidden"
    wb.active = wb.sheetnames.index("Regioes")
    ws.print_options.gridLines = True
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    copia = pasta / "planilha_exemplo.xlsx"
    wb.save(copia)
    return copia


def imagem_planilha(xlsx, pasta, destino):
    subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(pasta), str(xlsx)],
                   check=True, capture_output=True, timeout=180)
    pdf = pasta / (xlsx.stem + ".pdf")
    subprocess.run(["pdftoppm", "-png", "-r", "140", "-f", "1", "-l", "1", str(pdf), str(pasta / "pl")], check=True)
    pagina = sorted(pasta.glob("pl*.png"))[0]
    shutil.copy(pagina, destino)
    recortar(destino)


def main():
    SAIDA.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as d:
        pasta = Path(d)
        trechos, xlsx = rodada_terminal(pasta)
        imagem_terminal(trechos, pasta, SAIDA / "terminal.png")
        import ezdxf
        itens, _ = cpp.coletar(ezdxf.readfile(DXF).modelspace(), 0.005)
        imagem_selecao(itens, SAIDA / "selecao_janelas.png")
        cpp.mostrar_janelas(itens, cpp.detectar_grupos(itens, 0.001), SAIDA / "janelas_sugeridas.png")
        shutil.copy(pasta / (DXF.stem + "_secoes_previas") / "Secao_04.png", SAIDA / "previa_regioes.png")
        imagem_planilha(planilha_preenchida(xlsx, pasta), pasta, SAIDA / "planilha_regioes.png")
    for p in sorted(SAIDA.glob("*.png")):
        print(p.relative_to(RAIZ), Image.open(p).size)


if __name__ == "__main__":
    main()

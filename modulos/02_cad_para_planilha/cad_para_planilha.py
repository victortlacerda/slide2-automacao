#!/usr/bin/env python3
"""Extrai seções de um desenho DXF e gera a planilha-padrão para o Slide2.

Fluxo:
    1. Você escolhe o DXF (janela do sistema) e responde às perguntas no terminal:
       unidade do desenho, exagero vertical, camadas CAD a usar e como delimitar
       cada seção.
    2. Cada seção é delimitada por uma JANELA (retângulo) que você desenha numa
       tela com o desenho todo. Só entram na seção as entidades que estão
       INTEIRAS dentro da janela.
    3. As linhas/polilinhas de cada seção são unidas e as regiões fechadas
       (camadas de solo) são numeradas.
    4. Sai um .xlsx com as abas Materiais, Secoes, Regioes, Vertices e Previas,
       um PNG por seção e um .json com as respostas, para repetir a rodada.

Você só precisa: preencher a aba Materiais e, na aba Regioes, escolher o
material de cada região (lista suspensa).

Execução interativa:
    python cad_para_planilha.py

Execução com argumentos (sem perguntas, útil para repetir):
    python cad_para_planilha.py desenho.dxf --unidade m --modo coordenadas \
        --janelas="0,-15,60,15;90,-15,150,15"
    python cad_para_planilha.py --config desenho_extracao.json

Dependências:  pip install ezdxf shapely openpyxl matplotlib
Este script não abre o AutoCAD nem o Slide2; lê só o arquivo DXF.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

try:
    import ezdxf
    from ezdxf import path as ezpath
    import openpyxl
    from openpyxl.drawing.image import Image as XlImage
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation
    from shapely.geometry import LineString
    from shapely.geometry.polygon import orient
    from shapely.ops import polygonize_full, unary_union
except ImportError as exc:  # pragma: no cover
    sys.exit(f"Falta a biblioteca '{exc.name}'. Instale com:\n"
             "  pip install ezdxf shapely openpyxl matplotlib")

VERSAO = "0.6"
EPS = 1e-9
UNIDADES = {"m": 1.0, "cm": 0.01, "mm": 0.001}
INSUNITS_NOME = {4: "mm", 5: "cm", 6: "m"}
TIPOS_GEOMETRIA = {"LINE", "LWPOLYLINE", "POLYLINE", "ARC", "CIRCLE", "ELLIPSE", "SPLINE"}
MAX_MATERIAIS = 20  # slots soil1..soil20 do modelo-base do Slide2


# ----------------------------------------------------------------------------
# Terminal
# ----------------------------------------------------------------------------
def perguntar(texto, padrao=None, converter=str, validar=None, msg_erro="Valor inválido."):
    """Pergunta no terminal. Sem `padrao`, a resposta é obrigatória."""
    while True:
        sufixo = f" [{padrao}]" if padrao is not None else ""
        bruto = input(f"{texto}{sufixo}: ").strip()
        if not bruto:
            if padrao is None:
                print("  Resposta obrigatória.")
                continue
            bruto = str(padrao)
        try:
            valor = converter(bruto)
        except ValueError:
            print(f"  {msg_erro}")
            continue
        if validar is not None and not validar(valor):
            print(f"  {msg_erro}")
            continue
        return valor


def escolher_dxf() -> Path:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as exc:
        raise RuntimeError("Não consegui abrir a janela de arquivos; informe o caminho do DXF como argumento.") from exc
    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
        escolhido = filedialog.askopenfilename(
            title="Selecione o desenho DXF com as seções",
            filetypes=[("Desenho DXF (*.dxf)", "*.dxf"), ("Todos os arquivos", "*.*")])
    finally:
        root.destroy()
    if not escolhido:
        raise RuntimeError("Nenhum arquivo foi selecionado. Operação cancelada.")
    return Path(escolhido)


# ----------------------------------------------------------------------------
# Leitura do DXF
# ----------------------------------------------------------------------------
def sem_duplicados(pts, eps=EPS):
    out = []
    for p in pts:
        if not out or math.dist(out[-1], p) > eps:
            out.append(p)
    return out


def percorrer(entidades, camada_pai=None, nivel=0):
    """Gera (entidade, camada), expandindo blocos (INSERT)."""
    for e in entidades:
        if e.dxftype() == "INSERT":
            if nivel < 8:
                yield from percorrer(e.virtual_entities(), e.dxf.layer, nivel + 1)
            continue
        camada = e.dxf.layer
        if camada == "0" and camada_pai:
            camada = camada_pai
        yield e, camada


def entidade_para_polilinhas(e, dist):
    """Converte a entidade em listas de (x, y); arcos e splines viram segmentos."""
    caminho = ezpath.make_path(e)
    saida = []
    for sub in caminho.sub_paths():
        pts = sem_duplicados([(float(v.x), float(v.y)) for v in sub.flattening(dist)])
        if len(pts) >= 2:
            saida.append(pts)
    return saida


def coletar(msp, dist):
    itens, ignorados = [], Counter()
    for e, camada in percorrer(msp):
        tipo = e.dxftype()
        if tipo not in TIPOS_GEOMETRIA:
            ignorados[tipo] += 1
            continue
        try:
            polis = entidade_para_polilinhas(e, dist)
        except Exception:
            ignorados[f"{tipo} (erro ao ler)"] += 1
            continue
        for pts in polis:
            itens.append({"camada": camada, "tipo": tipo, "pts": pts})
    return itens, ignorados


def bbox(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


# ----------------------------------------------------------------------------
# Janelas (delimitação das seções)
# ----------------------------------------------------------------------------
def parse_janelas(texto):
    janelas = []
    for k, item in enumerate(texto.split(";"), 1):
        campos = item.strip().split(",")
        if len(campos) != 4:
            raise ValueError(f"Janela inválida {item!r}; use x0,y0,x1,y1;x0,y0,x1,y1")
        x0, y0, x1, y1 = map(float, campos)
        janelas.append({"nome": f"Secao_{k:02d}", "xmin": min(x0, x1), "ymin": min(y0, y1),
                        "xmax": max(x0, x1), "ymax": max(y0, y1)})
    return janelas


class SeletorJanelas:
    """Tela com o desenho; arraste um retângulo, ENTER salva, BACKSPACE desfaz."""

    def __init__(self, itens, plt):
        from matplotlib.widgets import RectangleSelector
        self.plt = plt
        self.fig, self.ax = plt.subplots(figsize=(13, 7))
        for it in itens:
            xs, ys = zip(*it["pts"])
            self.ax.plot(xs, ys, lw=0.9, color="0.3")
        self.ax.set_aspect("equal")
        # Folga igual em todas as bordas (15% da maior dimensão do desenho), para haver espaço
        # de clicar fora da seção e arrastar o retângulo, mesmo com seções lado a lado.
        x0, y0, x1, y1 = bbox([p for it in itens for p in it["pts"]])
        folga = 0.15 * max(x1 - x0, y1 - y0, 1e-6)
        self.ax.set_xlim(x0 - folga, x1 + folga)
        self.ax.set_ylim(y0 - folga, y1 + folga)
        self.ax.grid(alpha=0.3)
        self.janelas, self.artistas = [], []
        self.sel = RectangleSelector(self.ax, lambda a, b: None, useblit=False, button=[1], interactive=True)
        self.fig.canvas.mpl_connect("key_press_event", self.tecla)
        self._titulo()

    def _titulo(self):
        self.ax.set_title(
            f"Arraste um retângulo em volta de UMA seção e tecle ENTER (Seção {len(self.janelas) + 1:02d}). "
            f"BACKSPACE desfaz a última. Feche a janela ao terminar. [{len(self.janelas)} salva(s)]\n"
            "Se o retângulo não aparecer, desative zoom/pan na barra de ferramentas.", fontsize=9)
        self.fig.canvas.draw_idle()

    def tecla(self, ev):
        if ev.key == "enter":
            self.salvar()
        elif ev.key == "backspace":
            self.desfazer()

    def salvar(self):
        x0, x1, y0, y1 = self.sel.extents
        if x1 - x0 <= 0 or y1 - y0 <= 0:
            return False
        n = len(self.janelas) + 1
        self.janelas.append({"nome": f"Secao_{n:02d}", "xmin": min(x0, x1), "ymin": min(y0, y1),
                             "xmax": max(x0, x1), "ymax": max(y0, y1)})
        from matplotlib.patches import Rectangle
        ret = Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ec="tab:red", lw=1.5)
        self.ax.add_patch(ret)
        txt = self.ax.text(x0, y1, f" Seção {n:02d}", color="tab:red", va="bottom", fontsize=10, weight="bold")
        self.artistas.append((ret, txt))
        try:
            self.sel.clear()
        except AttributeError:
            pass
        self._titulo()
        return True

    def desfazer(self):
        if not self.janelas:
            return
        self.janelas.pop()
        for a in self.artistas.pop():
            a.remove()
        self._titulo()


def selecionar_janelas(itens):
    import matplotlib
    if matplotlib.get_backend().lower() in {"agg", "pdf", "svg", "ps", "cairo", "template"}:
        raise RuntimeError("Não há tela gráfica disponível. Use --modo coordenadas --janelas \"x0,y0,x1,y1;...\".")
    import matplotlib.pyplot as plt
    seletor = SeletorJanelas(itens, plt)
    plt.show()
    return seletor.janelas


def detectar_grupos(itens, tol):
    """SUGESTÃO: agrupa entidades que se tocam. Pode juntar seções que se encostam."""
    from shapely.strtree import STRtree
    geoms = [LineString(it["pts"]) for it in itens]
    arvore = STRtree(geoms)
    pai = list(range(len(geoms)))

    def raiz(a):
        while pai[a] != a:
            pai[a] = pai[pai[a]]
            a = pai[a]
        return a

    for i, g in enumerate(geoms):
        for j in arvore.query(g.buffer(max(tol, 1e-6)), predicate="intersects"):
            if int(j) > i:
                pai[raiz(int(j))] = raiz(i)
    grupos = defaultdict(list)
    for i in range(len(geoms)):
        grupos[raiz(i)].append(i)
    caixas = [[bbox([p for k in m for p in itens[k]["pts"]]), m] for m in grupos.values()]

    # Um grupo que cabe inteiro no retângulo de outro (lente, bolsão que não toca nada) pertence a ele.
    caixas.sort(key=lambda c: -(c[0][2] - c[0][0]) * (c[0][3] - c[0][1]))
    finais = []
    for cx, membros in caixas:
        dono = next((f for f in finais if f[0][0] <= cx[0] and f[0][1] <= cx[1]
                     and cx[2] <= f[0][2] and cx[3] <= f[0][3]), None)
        if dono:
            dono[1] = dono[1] + membros
        else:
            finais.append([cx, membros])

    # Ordem de leitura da prancha: linhas de cima para baixo; em cada linha, da esquerda para a direita.
    finais.sort(key=lambda c: -c[0][3])
    linhas = []
    for c in finais:
        if linhas and c[0][3] > min(o[0][1] for o in linhas[-1]):  # topo acima da base de quem está na linha
            linhas[-1].append(c)
        else:
            linhas.append([c])
    janelas = []
    for linha in linhas:
        for (x0, y0, x1, y1), _ in sorted(linha, key=lambda c: c[0][0]):
            janelas.append({"nome": f"Secao_{len(janelas) + 1:02d}", "xmin": x0, "ymin": y0, "xmax": x1, "ymax": y1})
    return janelas


def mostrar_janelas(itens, janelas, png):
    """Desenha o DXF com as janelas sugeridas (cada grupo de linhas na cor do seu retângulo).

    Com tela gráfica abre uma janela e espera você fechá-la; sem tela, grava `png`.
    Devolve o caminho do PNG gravado ou None.
    """
    import matplotlib
    from matplotlib.patches import Rectangle
    interativo = matplotlib.get_backend().lower() not in {"agg", "pdf", "svg", "ps", "cairo", "template"}
    if interativo:
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(13, 7))
    else:
        from matplotlib.figure import Figure
        fig = Figure(figsize=(13, 7), dpi=110)
        ax = fig.subplots()
    cores = ["tab:blue", "tab:orange", "tab:green", "tab:purple", "tab:brown", "tab:pink", "tab:olive", "tab:cyan"]
    por_secao, _, _ = atribuir(itens, janelas)
    dentro = {id(it) for grupo in por_secao for it in grupo}
    for it in itens:  # o que ficou fora de qualquer janela, em cinza
        if id(it) not in dentro:
            xs, ys = zip(*it["pts"])
            ax.plot(xs, ys, lw=0.9, color="0.6")
    for k, (j, grupo) in enumerate(zip(janelas, por_secao)):
        cor = cores[k % len(cores)]
        for it in grupo:
            xs, ys = zip(*it["pts"])
            ax.plot(xs, ys, lw=1.4, color=cor)
        ax.add_patch(Rectangle((j["xmin"], j["ymin"]), j["xmax"] - j["xmin"], j["ymax"] - j["ymin"],
                               fill=False, ec=cor, lw=1.6, ls="--"))
        ax.text(j["xmin"], j["ymax"], f" Seção {k + 1:02d}  ({len(grupo)} entidade(s))", color=cor,
                va="bottom", fontsize=10, weight="bold")
    ax.set_aspect("equal")
    ax.margins(0.08)
    ax.grid(alpha=0.3)
    ax.set_title("Janelas SUGERIDAS pelo agrupamento. Cada cor = uma seção. Confira se nenhuma junta "
                 "duas seções nem separa uma só. Feche esta janela para responder no terminal.", fontsize=9)
    if interativo:
        plt.show()
        return None
    fig.savefig(png, bbox_inches="tight")
    return png


def atribuir(itens, janelas):
    """Entidades INTEIRAS dentro da janela entram; as cortadas são contadas."""
    por_secao = [[] for _ in janelas]
    cortadas = [0] * len(janelas)
    sem_secao = 0
    for it in itens:
        x0, y0, x1, y1 = bbox(it["pts"])
        achou = False
        for k, j in enumerate(janelas):
            eps = 1e-6 * max(j["xmax"] - j["xmin"], j["ymax"] - j["ymin"], 1.0)
            if x0 >= j["xmin"] - eps and x1 <= j["xmax"] + eps and y0 >= j["ymin"] - eps and y1 <= j["ymax"] + eps:
                por_secao[k].append(it)
                achou = True
            elif x1 >= j["xmin"] and x0 <= j["xmax"] and y1 >= j["ymin"] and y0 <= j["ymax"]:
                cortadas[k] += 1
        if not achou:
            sem_secao += 1
    return por_secao, cortadas, sem_secao


# ----------------------------------------------------------------------------
# Geometria: do desenho às regiões
# ----------------------------------------------------------------------------
def encaixar(linhas, tol):
    """Encaixa pontas e vértices que estão a menos de `tol` de outra linha.

    Corrige erros comuns de desenho: pontas que não se tocam por décimos de
    milímetro, e vértices que deveriam estar sobre a linha vizinha mas ficam
    ligeiramente fora (isso criaria regiões-lasca).
    """
    if tol <= 0 or len(linhas) < 2:
        return linhas
    from shapely.geometry import MultiPoint
    from shapely.ops import snap
    from shapely.strtree import STRtree
    arvore = STRtree(linhas)
    atual = list(linhas)
    for i, ln in enumerate(linhas):
        viz = [int(j) for j in arvore.query(ln.buffer(2 * tol)) if int(j) != i]
        if not viz:
            continue
        ref = MultiPoint([p[:2] for j in viz for p in atual[j].coords])
        novo = snap(atual[i], ref, tol)  # usa as linhas já ajustadas: pontas se fundem em vez de trocar de lugar
        if novo.geom_type == "LineString" and not novo.is_empty:
            pts = sem_duplicados([tuple(p[:2]) for p in novo.coords])
            if len(pts) >= 2:
                atual[i] = LineString(pts)
    return atual


def processar_secao(nome, itens, fator, exagero, zerar_x, tol, area_min):
    """Une as linhas, fecha as regiões e valida. Coordenadas de saída em metros."""
    segs = [[(x * fator, y * fator / exagero) for x, y in it["pts"]] for it in itens]
    desloc = 0.0
    if zerar_x and segs:
        desloc = min(x for s in segs for x, _ in s)
        segs = [[(x - desloc, y) for x, y in s] for s in segs]
    sec = {"nome": nome, "regioes": [], "avisos": [], "dangles": [], "desloc_x": desloc,
           "bbox": None, "area_total": 0.0}
    linhas = [LineString(s) for s in segs if len(s) >= 2]
    linhas = [ln for ln in linhas if ln.length > EPS]
    if not linhas:
        sec["avisos"].append("nenhuma linha/polilinha dentro da janela")
        return sec
    sec["bbox"] = unary_union(linhas).bounds
    linhas = encaixar(linhas, tol)
    uniao = unary_union(linhas)
    partes = list(getattr(uniao, "geoms", [uniao]))
    faces_gc, dangles_gc, cuts_gc, invalidos_gc = polygonize_full(partes)
    faces = list(faces_gc.geoms)
    pequenas = [f for f in faces if f.area < area_min]
    faces = [f for f in faces if f.area >= area_min]
    if pequenas:
        sec["avisos"].append(f"{len(pequenas)} região(ões) minúscula(s) (< {area_min:g} m²) descartada(s)")
    if not faces:
        sec["avisos"].append("nenhuma região fechada: confira se os contornos se fecham (pontas soltas)")
    rps = [(f, f.representative_point()) for f in faces]
    rps.sort(key=lambda t: (-round(t[1].y, 6), round(t[1].x, 6)))  # de cima para baixo, esq. -> dir.
    for k, (f, rp) in enumerate(rps, 1):
        sec["regioes"].append({"id": k, "poly": orient(f, 1.0), "area": f.area, "rp": (rp.x, rp.y)})
    sec["area_total"] = sum(r["area"] for r in sec["regioes"])
    # Linhas que não fecham região: o GEOS as separa em "dangles" e "cuts"; tratamos as duas juntas.
    sobras = [d for d in list(dangles_gc.geoms) + list(cuts_gc.geoms) if d.length > tol]
    sec["dangles"] = sobras
    if sobras:
        contagem = Counter()
        for ln in partes:
            c = list(ln.coords)
            for p in (c[0], c[-1]):
                contagem[(round(p[0], 6), round(p[1], 6))] += 1
        livres = sorted(p for p, n in contagem.items() if n == 1)
        onde = ", ".join(f"({x:.3f}; {y:.3f})" for x, y in livres[:5]) + ("..." if len(livres) > 5 else "")
        sec["avisos"].append(f"{len(sobras)} trecho(s) de linha não fecham região"
                             + (f"; {len(livres)} ponta(s) solta(s) em {onde}" if livres else "")
                             + " (ponta solta, falha no fechamento ou linha auxiliar)")
    if len(list(invalidos_gc.geoms)):
        sec["avisos"].append("há anéis inválidos no desenho; confira os contornos")
    if faces:
        dominio = unary_union(faces)
        if dominio.geom_type != "Polygon":
            sec["avisos"].append(f"a seção tem {len(list(dominio.geoms))} partes desconectadas "
                                 "(janela pegou mais de uma seção ou há vão no desenho)")
        elif dominio.interiors and len(dominio.interiors) > 0:
            sec["avisos"].append(f"{len(dominio.interiors)} vazio(s) sem material dentro da seção")
        buracos = sum(len(list(r["poly"].interiors)) for r in sec["regioes"])
        if buracos:
            sec["avisos"].append(f"{buracos} região(ões) com furo (uma camada contida em outra): "
                                 "o furo aparece como anel 1+ na aba Vertices")
    if len(sec["regioes"]) > MAX_MATERIAIS:
        sec["avisos"].append(f"{len(sec['regioes'])} regiões; o Slide2 aceita até {MAX_MATERIAIS} materiais")
    return sec


def extrair_na(itens, fator, exagero, desloc_x):
    """Linha do NA de uma seção: une os trechos e devolve os pontos da esquerda para a direita."""
    if not itens:
        return [], None
    from shapely.ops import linemerge
    linhas = [LineString([(x * fator - desloc_x, y * fator / exagero) for x, y in it["pts"]]) for it in itens]
    unida = linemerge(unary_union(linhas))
    partes = sorted(getattr(unida, "geoms", [unida]), key=lambda g: -g.length)
    pts = [tuple(p[:2]) for p in partes[0].coords]
    if pts[0][0] > pts[-1][0]:
        pts.reverse()
    aviso = None
    if len(partes) > 1:
        aviso = f"o NA tem {len(partes)} trechos separados; usei o mais longo"
    return pts, aviso


def aneis(poly):
    yield 0, list(poly.exterior.coords)[:-1]
    for k, r in enumerate(poly.interiors, 1):
        yield k, list(r.coords)[:-1]


# ----------------------------------------------------------------------------
# Saídas: prévia PNG e planilha
# ----------------------------------------------------------------------------
def desenhar_previa(sec, caminho):
    from matplotlib.figure import Figure
    from matplotlib.path import Path as MPath
    from matplotlib.patches import PathPatch
    paleta = ["#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2", "#B279A2", "#EECA3B", "#9D755D"]
    x0, y0, x1, y1 = sec["bbox"] or (0, 0, 1, 1)
    dx, dy = max(x1 - x0, 1e-6), max(y1 - y0, 1e-6)
    w = 10.0
    h = min(max(w * dy / dx, 3.0), 8.0) + 1.0
    fig = Figure(figsize=(w, h), dpi=110)
    ax = fig.subplots()
    for r in sec["regioes"]:
        verts, codes = [], []
        for _, anel in aneis(r["poly"]):
            v = anel + [anel[0]]
            verts += v
            codes += [MPath.MOVETO] + [MPath.LINETO] * (len(v) - 2) + [MPath.CLOSEPOLY]
        ax.add_patch(PathPatch(MPath(verts, codes), fc=paleta[(r["id"] - 1) % len(paleta)],
                               ec="black", lw=1.0, alpha=0.5))
        xs, ys = zip(*r["poly"].exterior.coords)
        ax.plot(xs, ys, "k.", ms=3)
        ax.text(r["rp"][0], r["rp"][1], str(r["id"]), ha="center", va="center", fontsize=11, weight="bold",
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="0.3"))
    for d in sec["dangles"]:
        xs, ys = zip(*d.coords)
        ax.plot(xs, ys, "r--", lw=2)
    ax.set_xlim(x0 - 0.05 * dx, x1 + 0.05 * dx)
    ax.set_ylim(y0 - 0.08 * dy, y1 + 0.08 * dy)
    ax.set_aspect("equal")
    ax.grid(alpha=0.3)
    ax.set_xlabel("x (m)")
    ax.set_ylabel("cota (m)")
    ax.set_title(f"{sec['nome']} - {len(sec['regioes'])} região(ões); vermelho tracejado = ponta solta", fontsize=10)
    fig.tight_layout()
    fig.savefig(caminho)


def estilizar_cabecalho(ws, n_cols):
    for c in range(1, n_cols + 1):
        cel = ws.cell(row=1, column=c)
        cel.font = Font(bold=True, color="FFFFFF")
        cel.fill = PatternFill("solid", fgColor="305496")
        cel.alignment = Alignment(wrap_text=True, vertical="center")
    ws.freeze_panes = "A2"


def largura(ws, larguras):
    for i, w in enumerate(larguras, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def gravar_xlsx(caminho, secoes, config, previas):
    wb = openpyxl.Workbook()
    amarelo = PatternFill("solid", fgColor="FFF2CC")

    ws = wb.active
    ws.title = "LEIA-ME"
    linhas = [
        "Planilha gerada por cad_para_planilha.py (v%s) em %s" % (VERSAO, datetime.now().strftime("%d/%m/%Y %H:%M")),
        "",
        "O que fazer:",
        "1) Aba Materiais: preencha um material por linha (máximo %d, limite do modelo-base do Slide2)." % MAX_MATERIAIS,
        "2) Aba Previas (ou os PNG ao lado da planilha): veja o número de cada região da seção.",
        "3) Aba Regioes: escolha o Material de cada região na lista suspensa (coluna F).",
        "4) Aba Secoes: coluna 'Ativa' = n exclui a seção da análise. Leia a coluna Avisos.",
        "   Coluna 'Cota real do ponto mais alto' (opcional): se a seção não está na cota real no desenho",
        "   (ex.: seções empilhadas na prancha), informe a cota verdadeira do ponto mais alto da seção;",
        "   a seção inteira é deslocada em Y para essa cota. Use quando NA, cargas ou relatório estiverem em cota real.",
        "5) Aba NA (opcional): pontos do nível d'água por seção, da esquerda para a direita. Linhas com Origem = CAD",
        "   vieram do desenho e acompanham a seção; linhas digitadas (Origem = planilha ou vazio) estão em cota real.",
        "6) Aba Cargas (opcional): uma linha por carga. Distribuída: X início, X fim e kPa. Linha: X e kN/m.",
        "   O X é o da seção (o mesmo das abas Vertices e Previas); a carga é posta sobre o terreno.",
        "7) Aba Grelha (opcional): grelha de centros por seção (cantos X1,Y1 e X2,Y2 e intervalos), para Grid Search.",
        "8) Não altere as abas Vertices e Origem; o próximo script lê as coordenadas de lá.",
        "",
        "Unidades: coordenadas em metros; cota (Y) mantém o valor do desenho.",
        "Modelo de resistência previsto: Mohr-Coulomb (γ, c', φ').",
    ]
    for i, t in enumerate(linhas, 1):
        ws.cell(row=i, column=1, value=t)
    ws["A1"].font = Font(bold=True)
    ws["A3"].font = Font(bold=True)
    ws.column_dimensions["A"].width = 110

    wm = wb.create_sheet("Materiais")
    wm.append(["Nome", "γ natural (kN/m³)", "γ saturado (kN/m³, opcional)", "c' (kPa)", "φ' (°)",
               "Cor (opcional)", "Observações"])
    estilizar_cabecalho(wm, 7)
    for r in range(2, MAX_MATERIAIS + 2):
        for c in range(1, 8):
            wm.cell(row=r, column=c).fill = amarelo
    wm.cell(row=MAX_MATERIAIS + 3, column=1,
            value="Os nomes desta coluna alimentam a lista suspensa da aba Regioes. Máximo de %d materiais." % MAX_MATERIAIS)
    largura(wm, [28, 18, 24, 12, 10, 16, 40])
    wm.row_dimensions[1].height = 32

    wsec = wb.create_sheet("Secoes")
    wsec.append(["Seção", "Nome", "Ativa (s/n)", "Regiões", "Área total (m²)", "X mín (m)", "X máx (m)",
                 "Cota mín (m)", "Cota máx (m)", "Deslocamento X aplicado (m)",
                 "Cota real do ponto mais alto (m, opcional)", "Avisos",
                 "Janela no CAD (xmin; ymin; xmax; ymax)"])
    estilizar_cabecalho(wsec, 13)
    wreg = wb.create_sheet("Regioes")
    wreg.append(["Seção", "Região", "Área (m²)", "X do rótulo (m)", "Cota do rótulo (m)", "Material", "Observações"])
    estilizar_cabecalho(wreg, 7)
    wver = wb.create_sheet("Vertices")
    wver.append(["Seção", "Região", "Anel (0 = externo; 1+ = furo)", "Ordem", "X (m)", "Y (m)"])
    estilizar_cabecalho(wver, 6)

    for n, sec in enumerate(secoes, 1):
        b = sec["bbox"] or (None,) * 4
        j = sec["janela"]
        wsec.append([n, sec["nome"], "s", len(sec["regioes"]), round(sec["area_total"], 4),
                     None if b[0] is None else round(b[0], 4), None if b[2] is None else round(b[2], 4),
                     None if b[1] is None else round(b[1], 4), None if b[3] is None else round(b[3], 4),
                     round(sec["desloc_x"], 4), None, " | ".join(sec["avisos"]) or "ok",
                     f"{j['xmin']:.4f}; {j['ymin']:.4f}; {j['xmax']:.4f}; {j['ymax']:.4f}"])
        wsec.cell(row=wsec.max_row, column=11).fill = amarelo
        for r in sec["regioes"]:
            wreg.append([n, r["id"], round(r["area"], 4), round(r["rp"][0], 4), round(r["rp"][1], 4), None, None])
            wreg.cell(row=wreg.max_row, column=6).fill = amarelo
            ordem = 0
            for anel, pts in aneis(r["poly"]):
                for x, y in pts:
                    ordem += 1
                    wver.append([n, r["id"], anel, ordem, round(x, 6), round(y, 6)])
    if wreg.max_row >= 2:
        dv = DataValidation(type="list", formula1=f"=Materiais!$A$2:$A${MAX_MATERIAIS + 1}", allow_blank=True)
        dv.error = "Escolha um material cadastrado na aba Materiais."
        dv.errorTitle = "Material inválido"
        wreg.add_data_validation(dv)
        dv.add(f"F2:F{wreg.max_row}")
    largura(wsec, [8, 14, 11, 9, 15, 11, 11, 12, 12, 16, 20, 70, 44])
    largura(wreg, [8, 9, 12, 14, 16, 28, 36])
    largura(wver, [8, 9, 16, 8, 14, 14])
    wsec.row_dimensions[1].height = 45
    wver.row_dimensions[1].height = 32

    wna = wb.create_sheet("NA")
    wna.append(["Seção", "Ordem", "X (m)", "Y (m)", "Origem (CAD/planilha)"])
    estilizar_cabecalho(wna, 5)
    for n, sec in enumerate(secoes, 1):
        for k, (x, y) in enumerate(sec.get("na", []), 1):
            wna.append([n, k, round(x, 6), round(y, 6), "CAD"])
    largura(wna, [8, 8, 14, 14, 22])
    wna.row_dimensions[1].height = 32

    wc = wb.create_sheet("Cargas")
    wc.append(["Seção", "Tipo (distribuida/linha)", "X início (m)", "X fim (m, só distribuída)",
               "Intensidade (kPa ou kN/m)", "Ângulo (°, vazio = 270 = vertical p/ baixo)", "Observações"])
    estilizar_cabecalho(wc, 7)
    for r in range(2, 42):
        for c in range(1, 7):
            wc.cell(row=r, column=c).fill = amarelo
    dvt = DataValidation(type="list", formula1='"distribuida,linha"', allow_blank=True)
    wc.add_data_validation(dvt)
    dvt.add("B2:B1000")
    largura(wc, [8, 22, 13, 22, 24, 36, 36])
    wc.row_dimensions[1].height = 45

    wg = wb.create_sheet("Grelha")
    wg.append(["Seção", "X1 (m)", "Y1 (m)", "X2 (m)", "Y2 (m)", "nx (intervalos)", "ny (intervalos)"])
    estilizar_cabecalho(wg, 7)
    for n, _ in enumerate(secoes, 1):
        wg.append([n, None, None, None, None, 20, 20])
        for c in range(2, 8):
            wg.cell(row=wg.max_row, column=c).fill = amarelo
    largura(wg, [8, 12, 12, 12, 12, 16, 16])
    wg.row_dimensions[1].height = 32

    wp = wb.create_sheet("Previas")
    linha = 1
    for n, (sec, png) in enumerate(zip(secoes, previas), 1):
        wp.cell(row=linha, column=1, value=f"Seção {n} ({sec['nome']})").font = Font(bold=True, size=12)
        img = XlImage(str(png))
        escala = 900 / img.width
        img.width, img.height = int(img.width * escala), int(img.height * escala)
        wp.add_image(img, f"A{linha + 1}")
        linha += int(img.height / 20) + 4

    wo = wb.create_sheet("Origem")
    wo.append(["Parâmetro", "Valor"])
    estilizar_cabecalho(wo, 2)
    for k, v in config.items():
        wo.append([k, json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v])
    largura(wo, [26, 110])
    wb.save(caminho)


def caminho_livre(base: Path) -> Path:
    if not base.exists():
        return base
    k = 2
    while True:
        cand = base.with_name(f"{base.stem}_{k}{base.suffix}")
        if not cand.exists():
            return cand
        k += 1


# ----------------------------------------------------------------------------
# Programa principal
# ----------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="DXF com seções -> planilha-padrão para o Slide2.")
    ap.add_argument("dxf", type=Path, nargs="?", help="Arquivo DXF; se omitido, abre janela para escolher")
    ap.add_argument("--saida", type=Path, help="Caminho do .xlsx (nunca sobrescreve)")
    ap.add_argument("--config", type=Path, help=".json de uma rodada anterior com as respostas")
    ap.add_argument("--unidade", choices=list(UNIDADES), help="Unidade do desenho (m, cm, mm)")
    ap.add_argument("--exagero-vertical", type=float, help="Fator de exagero vertical do desenho (1 = sem exagero)")
    ap.add_argument("--zerar-x", choices=["s", "n"], help="Deslocar cada seção para começar em X = 0 (a cota Y não muda)")
    ap.add_argument("--camadas", help="Camadas CAD a usar, separadas por vírgula")
    ap.add_argument("--camada-na", help="Camada CAD com o nível d'água (vazio = nenhuma)")
    ap.add_argument("--modo", choices=["janela", "coordenadas", "auto"], help="Como delimitar as seções")
    ap.add_argument("--janelas", help='Janelas nas unidades do desenho: "x0,y0,x1,y1;x0,y0,x1,y1"')
    ap.add_argument("--tol", type=float, default=None, help="Tolerância (m) para unir pontas de linha (padrão 0.001)")
    ap.add_argument("--tol-arco", type=float, default=None, help="Flecha máxima (m) ao converter arcos (padrão 0.005)")
    ap.add_argument("--area-min", type=float, default=None, help="Área mínima (m²) de uma região (padrão 0.0001)")
    argv = list(sys.argv[1:] if argv is None else argv)
    for i, a in enumerate(argv[:-1]):  # "--janelas -5,-20,..." seria lido como outra opção
        if a == "--janelas":
            argv[i:i + 2] = ["--janelas=" + argv[i + 1]]
            break
    args = ap.parse_args(argv)

    cfg = {}
    if args.config:
        cfg = json.loads(args.config.read_text(encoding="utf-8"))
    pick = lambda nome, chave=None: getattr(args, nome) if getattr(args, nome) is not None else cfg.get(chave or nome)

    try:
        dxf_path = (args.dxf or (Path(cfg["dxf"]) if cfg.get("dxf") and Path(cfg["dxf"]).is_file() else escolher_dxf()))
        dxf_path = dxf_path.expanduser().resolve()
        if not dxf_path.is_file():
            raise ValueError(f"Arquivo não encontrado: {dxf_path}")
        if dxf_path.stat().st_size == 0:
            raise ValueError("O arquivo DXF tem 0 bytes (cópia incompleta). Salve de novo e tente outra vez.")
        if dxf_path.suffix.lower() == ".dwg":
            raise ValueError("Este script lê DXF, não DWG. No CAD, use Salvar como... DXF.")
        try:
            doc = ezdxf.readfile(dxf_path)
        except (IOError, ezdxf.DXFStructureError) as exc:
            raise ValueError(f"Não consegui ler o DXF: {exc}") from exc
        msp = doc.modelspace()

        # --- unidade: SEMPRE perguntada; o cabeçalho do arquivo é só informação ---
        declarada = INSUNITS_NOME.get(doc.header.get("$INSUNITS", 0))
        print(f"Arquivo: {dxf_path.name}  (o cabeçalho do DXF declara unidade: {declarada or 'não declarada'})")
        unidade = pick("unidade")
        if unidade is None:
            unidade = perguntar("Em que unidade o desenho foi feito? (m, cm ou mm)", None,
                                lambda s: s.lower(), lambda v: v in UNIDADES, "Digite m, cm ou mm.")
        fator = UNIDADES[unidade]
        exagero = pick("exagero_vertical")
        if exagero is None:
            exagero = perguntar("Exagero vertical do desenho (1 = sem exagero)", 1, float, lambda v: v > 0,
                                "Digite um número maior que zero.")
        zerar = pick("zerar_x")
        if zerar is None:
            zerar = perguntar("Deslocar cada seção para começar em X = 0? (s/n)", "n", lambda s: s.lower(),
                              lambda v: v in ("s", "n"), "Digite s ou n.")
        zerar_x = (zerar == "s") if isinstance(zerar, str) else bool(zerar)
        tol = args.tol if args.tol is not None else cfg.get("tolerancia_m", 0.001)
        tol_arco = args.tol_arco if args.tol_arco is not None else cfg.get("tol_arco_m", 0.005)
        area_min = args.area_min if args.area_min is not None else cfg.get("area_min_m2", 1e-4)

        itens, ignorados = coletar(msp, tol_arco / fator)
        if not itens:
            raise ValueError("Não encontrei linhas, polilinhas, arcos ou splines no desenho.")
        contagem = Counter(it["camada"] for it in itens)
        print("\nCamadas CAD com geometria:")
        nomes = sorted(contagem)
        for k, nome in enumerate(nomes, 1):
            print(f"  {k}) {nome}  ({contagem[nome]} segmento(s)/polilinha(s))")
        if ignorados:
            print("  Ignorado (não é geometria de linha): " + ", ".join(f"{t} x{n}" for t, n in ignorados.items()))
        escolha = pick("camadas")
        if isinstance(escolha, str):
            escolha = [s.strip() for s in escolha.split(",") if s.strip()]
        if escolha is None:
            bruto = perguntar("Camadas a usar (números separados por vírgula; Enter = todas)", "todas")
            escolha = nomes if bruto.lower() == "todas" else [nomes[int(s) - 1] for s in bruto.split(",")
                                                               if s.strip().isdigit() and 0 < int(s) <= len(nomes)]
        faltam = [c for c in escolha if c not in contagem]
        if faltam or not escolha:
            raise ValueError(f"Camada(s) inexistente(s) ou nenhuma escolhida: {faltam or escolha}")
        camada_na = pick("camada_na")
        if camada_na is None:
            bruto = perguntar("Camada CAD do nível d'água (número; Enter = nenhuma)", "nenhuma")
            if bruto.lower() == "nenhuma":
                camada_na = ""
            elif bruto.isdigit() and 0 < int(bruto) <= len(nomes):
                camada_na = nomes[int(bruto) - 1]
            else:
                raise ValueError(f"Camada do NA inválida: {bruto}")
        if camada_na and camada_na not in contagem:
            raise ValueError(f"Camada do NA inexistente: {camada_na}")
        itens_na = [it for it in itens if camada_na and it["camada"] == camada_na]
        itens = [it for it in itens if it["camada"] in escolha and it["camada"] != camada_na]

        # --- como delimitar as seções ---
        if args.janelas:
            modo, janelas = "coordenadas", parse_janelas(args.janelas)
        elif cfg.get("janelas") and not args.modo:
            modo, janelas = cfg.get("modo", "coordenadas"), cfg["janelas"]
        else:
            modo = args.modo or perguntar(
                "Como delimitar as seções? [janela = desenhar retângulos na tela | coordenadas = digitar | "
                "auto = sugestão por agrupamento]", "janela", lambda s: s.lower(),
                lambda v: v in ("janela", "coordenadas", "auto"), "Digite janela, coordenadas ou auto.")
            if modo == "janela":
                print("Abrindo a tela do desenho: arraste um retângulo em volta de cada seção e tecle ENTER.")
                janelas = selecionar_janelas(itens)
            elif modo == "coordenadas":
                janelas = parse_janelas(perguntar('Janelas nas unidades do desenho ("x0,y0,x1,y1;x0,y0,x1,y1")'))
            else:
                janelas = detectar_grupos(itens, tol / fator)
                print(f"\nO agrupamento sugeriu {len(janelas)} seção(ões):")
                for j in janelas:
                    print(f"  {j['nome']}: x {j['xmin']:.3f} a {j['xmax']:.3f}, y {j['ymin']:.3f} a {j['ymax']:.3f}")
                png = mostrar_janelas(itens, janelas, caminho_livre(dxf_path.with_name(dxf_path.stem + "_janelas_sugeridas.png")))
                if png:
                    print(f"Sem tela gráfica: desenho com as janelas sugeridas gravado em {png}")
                else:
                    print("Desenho com as janelas sugeridas exibido; ao fechá-lo, responda abaixo.")
                if perguntar("Aceitar estas janelas? (s/n)", "n", lambda s: s.lower(),
                             lambda v: v in ("s", "n"), "Digite s ou n.") != "s":
                    print("Cancelado. Rode de novo com --modo janela para delimitar à mão.")
                    return 1
        if not janelas:
            raise ValueError("Nenhuma seção foi definida.")

        por_secao, cortadas, sem_secao = atribuir(itens, janelas)

        # --- construção das seções ---
        secoes = []
        for j, its, cort in zip(janelas, por_secao, cortadas):
            sec = processar_secao(j["nome"], its, fator, exagero, zerar_x, tol, area_min)
            sec["janela"] = j
            sec["na"] = []
            if cort:
                sec["avisos"].append(f"{cort} entidade(s) cortada(s) pela janela foram ignoradas "
                                     "(alargue a janela)")
            secoes.append(sec)
        if itens_na:
            por_na, _, _ = atribuir(itens_na, janelas)
            for sec, its in zip(secoes, por_na):
                sec["na"], aviso = extrair_na(its, fator, exagero, sec["desloc_x"])
                if aviso:
                    sec["avisos"].append(aviso)
        for a in range(len(janelas)):
            for b in range(a + 1, len(janelas)):
                ja, jb = janelas[a], janelas[b]
                if ja["xmin"] < jb["xmax"] and jb["xmin"] < ja["xmax"] and ja["ymin"] < jb["ymax"] and jb["ymin"] < ja["ymax"]:
                    secoes[a]["avisos"].append(f"janela sobrepõe a de {jb['nome']}")
                    secoes[b]["avisos"].append(f"janela sobrepõe a de {ja['nome']}")

        # --- arquivos de saída ---
        destino = (args.saida.expanduser().resolve() if args.saida
                   else dxf_path.with_name(dxf_path.stem + "_secoes.xlsx"))
        destino = caminho_livre(destino)
        pasta_previas = destino.with_name(destino.stem + "_previas")
        pasta_previas.mkdir(parents=True, exist_ok=True)
        previas = []
        for n, sec in enumerate(secoes, 1):
            png = pasta_previas / f"Secao_{n:02d}.png"
            desenhar_previa(sec, png)
            previas.append(png)
        config = {
            "versao_script": VERSAO, "dxf": str(dxf_path), "unidade": unidade, "exagero_vertical": exagero,
            "zerar_x": zerar_x, "tolerancia_m": tol, "tol_arco_m": tol_arco, "area_min_m2": area_min,
            "camadas": escolha, "camada_na": camada_na, "modo": modo, "janelas": janelas,
        }
        gravar_xlsx(destino, secoes, config, previas)
        destino.with_suffix(".json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"\nPlanilha criada: {destino}")
        print(f"Configuração salva em: {destino.with_suffix('.json')}  (reuse com --config)")
        print(f"Prévias das seções: {pasta_previas}")
        for n, sec in enumerate(secoes, 1):
            print(f"  Seção {n} ({sec['nome']}): {len(sec['regioes'])} região(ões), área {sec['area_total']:.3f} m²"
                  + (f"  AVISOS: {' | '.join(sec['avisos'])}" if sec["avisos"] else "  ok"))
        if sem_secao:
            print(f"  {sem_secao} entidade(s) ficaram fora de todas as janelas (ignoradas).")
        print("Próximo passo: preencha a aba Materiais e associe o material a cada região na aba Regioes.")
        return 0
    except (RuntimeError, ValueError, KeyError, OSError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2
    except (EOFError, KeyboardInterrupt):
        print("\nOperação cancelada.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

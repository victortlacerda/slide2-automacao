#!/usr/bin/env python3
"""Gera um modelo Slide2 (.slim) por seção a partir da planilha-padrão do módulo 02.

Dados (planilha): regiões e coordenadas (Vertices), materiais (Materiais + Regioes),
nível d'água (aba NA), cargas (aba Cargas) e a cota real opcional (aba Secoes).

Decisões de análise (terminal, sempre perguntadas, gravadas em JSON):
    - direção da ruptura, por seção ou a mesma para todas;
    - métodos de equilíbrio limite.

A busca da superfície (grelha, Auto Refine, AutoGrid) ainda não é gravada: defina-a no
Slide2 antes de calcular. Ver docs/roadmap.md (fase 4).

Uso:
    python planilha_para_slim.py                              # interativo
    python planilha_para_slim.py secoes.xlsx --direcao esq-dir --metodos bishop,spencer
    python planilha_para_slim.py --config secoes_modelos.json   # repete uma rodada

Dependências:  pip install shapely openpyxl matplotlib   (shapely >= 2.1)
O formato do .sli não é documentado pela Rocscience. Abra cada modelo no Slide2 e confira.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

try:
    import openpyxl
    import shapely
    from shapely.geometry import LineString, Polygon
    from shapely.geometry.polygon import orient
    from shapely.ops import unary_union
except ImportError as exc:  # pragma: no cover
    sys.exit(f"Falta a biblioteca '{exc.name}'. Instale com:\n  pip install shapely openpyxl matplotlib")

VERSAO = "0.4"
EPS = 1e-6
MAX_MATERIAIS = 20
RAIZ = Path(__file__).resolve().parents[2]
MODELO_BASE = RAIZ / "modulos" / "01_modelo_basico" / "modelo_base" / "vazio.slim"

# Na mesma ordem da janela Project Settings > Methods do Slide2. O terceiro valor é o peso de
# cada método no campo `methods` do .sli (máscara de bits; ver docs/formato_sli.md).
METODOS = [
    ("bishop", "Bishop simplificado", 2),
    ("corps1", "Corps of Engineers #1", 16),
    ("corps2", "Corps of Engineers #2", 32),
    ("gle", "GLE / Morgenstern-Price", 128),
    ("janbu", "Janbu simplificado", 4),
    ("janbu_corrigido", "Janbu corrigido", 256),
    ("lowe", "Lowe-Karafiath", 64),
    ("fellenius", "Ordinary / Fellenius", 1),
    ("spencer", "Spencer", 8),
]
DIRECOES = {"dir-esq": "right to left", "esq-dir": "left to right"}
# Busca da superfície: (chave, nome na janela Surface Options, código no .sli). Ver docs/formato_sli.md.
BUSCAS = {
    "circular": [("grid", "Grid Search (grelha de centros)", 0), ("slope", "Slope Search", 1),
                 ("autorefine", "Auto Refine Search", 2)],
    "nao_circular": [("block", "Block Search", 0), ("path", "Path Search", 1),
                     ("annealing", "Simulated Annealing", 3), ("autorefine", "Auto Refine Search", 4)],
}


class ErroSecao(ValueError):
    """Problema que impede gerar uma seção (as demais continuam)."""


# ----------------------------------------------------------------------------
# Terminal
# ----------------------------------------------------------------------------
def perguntar(texto, padrao=None, converter=str, validar=None, msg_erro="Valor inválido."):
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


def escolher_arquivo(titulo, tipos):
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as exc:
        raise RuntimeError("Não consegui abrir a janela de arquivos; informe o caminho como argumento.") from exc
    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
        escolhido = filedialog.askopenfilename(title=titulo, filetypes=tipos)
    finally:
        root.destroy()
    if not escolhido:
        raise RuntimeError("Nenhum arquivo foi selecionado. Operação cancelada.")
    return Path(escolhido)


def ler_metodos(texto):
    """Aceita números da lista (1-9) ou nomes curtos, separados por vírgula."""
    escolhidos = []
    for parte in str(texto).replace(";", ",").split(","):
        p = parte.strip().lower()
        if not p:
            continue
        if p.isdigit() and 1 <= int(p) <= len(METODOS):
            escolhidos.append(METODOS[int(p) - 1][0])
        elif p in {m[0] for m in METODOS}:
            escolhidos.append(p)
        else:
            raise ValueError(p)
    if not escolhidos:
        raise ValueError("nenhum método")
    return list(dict.fromkeys(escolhidos))


# ----------------------------------------------------------------------------
# Leitura da planilha
# ----------------------------------------------------------------------------
def _num(v, nome, obrigatorio=True):
    if v is None or (isinstance(v, str) and not v.strip()):
        if obrigatorio:
            raise ValueError(f"{nome} vazio")
        return None
    if isinstance(v, str):
        v = v.strip().replace(",", ".")
    return float(v)


def _colunas(ws):
    """Mapa prefixo-do-cabeçalho -> índice (0-based), para não depender da posição exata."""
    return [str(c.value or "").strip() for c in ws[1]]


def _idx(cab, prefixo, obrigatorio=True):
    for i, nome in enumerate(cab):
        if nome.lower().startswith(prefixo.lower()):
            return i
    if obrigatorio:
        raise ValueError(f"coluna '{prefixo}' não encontrada")
    return None


def ler_planilha(caminho):
    wb = openpyxl.load_workbook(caminho, data_only=True)
    for aba in ("Materiais", "Secoes", "Regioes", "Vertices"):
        if aba not in wb.sheetnames:
            raise ValueError(f"A planilha não tem a aba '{aba}'. Ela foi gerada pelo módulo 02?")

    # materiais na ordem da aba (a ordem define soil1, soil2...)
    ws = wb["Materiais"]
    cab = _colunas(ws)
    i_nome, i_g, i_c, i_phi = _idx(cab, "Nome"), _idx(cab, "γ natural"), _idx(cab, "c'"), _idx(cab, "φ'")
    i_gsat, i_cor = _idx(cab, "γ saturado", False), _idx(cab, "Cor", False)
    materiais = {}
    for r, row in enumerate(ws.iter_rows(min_row=2, values_only=True), 2):
        nome = row[i_nome]
        if nome is None or not str(nome).strip() or str(nome).startswith("Os nomes desta coluna"):
            continue
        nome = str(nome).strip()
        try:
            m = {"nome": nome, "gamma": _num(row[i_g], "γ"), "c": _num(row[i_c], "c'"),
                 "phi": _num(row[i_phi], "φ'"), "slot": len(materiais) + 1,
                 "gsat": _num(row[i_gsat], "γsat", False) if i_gsat is not None else None,
                 "cor": str(row[i_cor]).strip() if i_cor is not None and row[i_cor] else None}
        except ValueError as exc:
            raise ValueError(f"Aba Materiais, linha {r} ({nome}): {exc}") from exc
        if m["gamma"] <= 0 or m["c"] < 0 or not 0 <= m["phi"] < 90:
            raise ValueError(f"Aba Materiais, linha {r} ({nome}): use γ > 0, c' >= 0 e 0 <= φ' < 90.")
        if nome in materiais:
            raise ValueError(f"Aba Materiais: material repetido '{nome}'.")
        materiais[nome] = m
    if len(materiais) > MAX_MATERIAIS:
        raise ValueError(f"A aba Materiais tem {len(materiais)} materiais; o modelo aceita até {MAX_MATERIAIS}.")

    ws = wb["Secoes"]
    cab = _colunas(ws)
    i_sec, i_nome, i_ativa = _idx(cab, "Seção"), _idx(cab, "Nome"), _idx(cab, "Ativa")
    i_cmax, i_creal = _idx(cab, "Cota máx"), _idx(cab, "Cota real", False)
    secoes = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[i_sec] is None:
            continue
        n = int(row[i_sec])
        secoes[n] = {"n": n, "nome": str(row[i_nome] or f"Secao_{n:02d}"),
                     "ativa": str(row[i_ativa] or "s").strip().lower() != "n",
                     "cota_max": row[i_cmax], "cota_real": None, "regioes": {}, "na": [], "cargas": [], "grelha": None}
        if i_creal is not None and row[i_creal] not in (None, ""):
            secoes[n]["cota_real"] = _num(row[i_creal], "cota real")

    ws = wb["Regioes"]
    cab = _colunas(ws)
    i_sec, i_reg, i_mat = _idx(cab, "Seção"), _idx(cab, "Região"), _idx(cab, "Material")
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[i_sec] is None:
            continue
        n, k = int(row[i_sec]), int(row[i_reg])
        if n in secoes:
            secoes[n]["regioes"][k] = {"material": (str(row[i_mat]).strip() if row[i_mat] else None), "aneis": defaultdict(list)}

    ws = wb["Vertices"]
    cab = _colunas(ws)
    i_sec, i_reg, i_anel, i_ord, i_x, i_y = (_idx(cab, "Seção"), _idx(cab, "Região"), _idx(cab, "Anel"),
                                             _idx(cab, "Ordem"), _idx(cab, "X"), _idx(cab, "Y"))
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[i_sec] is None:
            continue
        n, k = int(row[i_sec]), int(row[i_reg])
        if n in secoes and k in secoes[n]["regioes"]:
            secoes[n]["regioes"][k]["aneis"][int(row[i_anel])].append((int(row[i_ord]), float(row[i_x]), float(row[i_y])))

    if "NA" in wb.sheetnames:
        ws = wb["NA"]
        cab = _colunas(ws)
        i_sec, i_ord, i_x, i_y = _idx(cab, "Seção"), _idx(cab, "Ordem"), _idx(cab, "X"), _idx(cab, "Y")
        i_org = _idx(cab, "Origem", False)
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[i_sec] is None or row[i_x] is None or row[i_y] is None:
                continue
            n = int(row[i_sec])
            if n in secoes:
                origem = str(row[i_org] or "planilha").strip().lower() if i_org is not None else "planilha"
                secoes[n]["na"].append((float(row[i_ord] or 0), _num(row[i_x], "X do NA"), _num(row[i_y], "Y do NA"),
                                        "cad" if origem.startswith("cad") else "planilha"))

    if "Cargas" in wb.sheetnames:
        ws = wb["Cargas"]
        cab = _colunas(ws)
        i_sec, i_tipo, i_xa = _idx(cab, "Seção"), _idx(cab, "Tipo"), _idx(cab, "X início")
        i_xb, i_q, i_ang = _idx(cab, "X fim"), _idx(cab, "Intensidade"), _idx(cab, "Ângulo")
        for r, row in enumerate(ws.iter_rows(min_row=2, values_only=True), 2):
            if row[i_sec] is None or row[i_tipo] is None:
                continue
            n = int(row[i_sec])
            tipo = str(row[i_tipo]).strip().lower().replace("í", "i")
            if tipo not in ("distribuida", "linha"):
                raise ValueError(f"Aba Cargas, linha {r}: tipo '{row[i_tipo]}' (use distribuida ou linha).")
            try:
                carga = {"linha_planilha": r, "tipo": tipo, "xa": _num(row[i_xa], "X início"),
                         "xb": _num(row[i_xb], "X fim", tipo == "distribuida"),
                         "q": _num(row[i_q], "Intensidade"), "angulo": _num(row[i_ang], "Ângulo", False)}
            except ValueError as exc:
                raise ValueError(f"Aba Cargas, linha {r}: {exc}") from exc
            if n in secoes:
                secoes[n]["cargas"].append(carga)

    if "Grelha" in wb.sheetnames:
        ws = wb["Grelha"]
        cab = _colunas(ws)
        idx = [_idx(cab, c) for c in ("Seção", "X1", "Y1", "X2", "Y2", "nx", "ny")]
        for r, row in enumerate(ws.iter_rows(min_row=2, values_only=True), 2):
            if row[idx[0]] is None or all(row[i] in (None, "") for i in idx[1:5]):
                continue
            n = int(row[idx[0]])
            try:
                x1, y1, x2, y2 = (_num(row[i], c) for i, c in zip(idx[1:5], ("X1", "Y1", "X2", "Y2")))
                nx = int(_num(row[idx[5]], "nx", False) or 20)
                ny = int(_num(row[idx[6]], "ny", False) or 20)
            except ValueError as exc:
                raise ValueError(f"Aba Grelha, linha {r}: {exc}") from exc
            if n in secoes:
                secoes[n]["grelha"] = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2), nx, ny)

    for sec in secoes.values():
        for k, reg in sec["regioes"].items():
            reg["aneis"] = {a: [(x, y) for _, x, y in sorted(pts)] for a, pts in reg["aneis"].items()}
        sec["na"].sort(key=lambda t: t[0])
    return materiais, secoes


# ----------------------------------------------------------------------------
# Geometria da seção
# ----------------------------------------------------------------------------
def chave(p):
    return (round(p[0], 6) + 0.0, round(p[1], 6) + 0.0)


def ponto_no_segmento(p, a, b, tol=EPS):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return False
    t = ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2
    if t <= 0 or t >= 1:
        return False
    return math.hypot(ax + t * dx - p[0], ay + t * dy - p[1]) <= tol


def inserir_ponto_nos_aneis(regioes, p):
    """Insere p no meio das arestas de região onde ele cai (mantém as regiões conformes)."""
    for reg in regioes:
        for a, anel in reg["aneis"].items():
            novo = []
            n = len(anel)
            for i in range(n):
                q0, q1 = anel[i], anel[(i + 1) % n]
                novo.append(q0)
                if ponto_no_segmento(p, q0, q1):
                    novo.append(p)
            reg["aneis"][a] = novo


def area2(pts):
    return sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))


def encadear(arestas):
    """Encadeia arestas não orientadas em polilinhas (abertas) e laços (fechados)."""
    viz = defaultdict(set)
    for a, b in arestas:
        viz[a].add(b)
        viz[b].add(a)
    usadas = set()
    cadeias = []

    def andar(inicio, prox):
        cadeia = [inicio]
        ant, atual = inicio, prox
        usadas.add(frozenset((inicio, prox)))
        while True:
            cadeia.append(atual)
            if len(viz[atual]) != 2 or atual == inicio:
                return cadeia
            seguinte = next(v for v in viz[atual] if v != ant)
            if frozenset((atual, seguinte)) in usadas:
                return cadeia
            usadas.add(frozenset((atual, seguinte)))
            ant, atual = atual, seguinte

    for v in sorted(viz):
        if len(viz[v]) != 2:
            for w in sorted(viz[v]):
                if frozenset((v, w)) not in usadas:
                    cadeias.append(andar(v, w))
    for v in sorted(viz):  # laços sem pontas (ex.: contorno de uma lente)
        for w in sorted(viz[v]):
            if frozenset((v, w)) not in usadas:
                cadeias.append(andar(v, w))
    return cadeias


def triangular(poly):
    """Triângulos (vértices do próprio polígono) que respeitam as bordas, inclusive furos."""
    tris = shapely.constrained_delaunay_triangles(poly)
    saida = []
    for t in tris.geoms:
        if t.area < 1e-10:
            continue
        pts = [tuple(c[:2]) for c in orient(t, 1.0).exterior.coords[:-1]]
        saida.append(pts)
    return saida


def montar_secao(sec, materiais, direcao):
    """Monta todos os blocos geométricos do .sli de uma seção."""
    avisos = []
    regioes = []
    for k, reg in sorted(sec["regioes"].items()):
        if not reg["material"]:
            raise ErroSecao(f"região {k} sem material (aba Regioes)")
        if reg["material"] not in materiais:
            raise ErroSecao(f"região {k}: material '{reg['material']}' não está na aba Materiais")
        if 0 not in reg["aneis"] or len(reg["aneis"][0]) < 3:
            raise ErroSecao(f"região {k} sem coordenadas na aba Vertices")
        regioes.append({"id": k, "material": reg["material"], "aneis": {a: list(p) for a, p in reg["aneis"].items()}})
    if not regioes:
        raise ErroSecao("seção sem regiões")

    # cota real: desloca a seção (e o que veio do CAD) em Y
    dy = 0.0
    if sec["cota_real"] is not None:
        topo = max(y for r in regioes for pts in r["aneis"].values() for _, y in pts)
        dy = sec["cota_real"] - topo
        for r in regioes:
            r["aneis"] = {a: [(x, y + dy) for x, y in pts] for a, pts in r["aneis"].items()}

    dominio = unary_union([Polygon(r["aneis"][0], [r["aneis"][a] for a in r["aneis"] if a]) for r in regioes])
    if dominio.geom_type != "Polygon":
        raise ErroSecao("as regiões não formam um único domínio (partes desconectadas)")
    if len(dominio.interiors):
        raise ErroSecao("há vazio sem material dentro da seção")

    # --- NA: recorta no domínio; as pontas ficam sobre o contorno ---
    na_pts = []
    if sec["na"]:
        pts = [(x, y + dy) if org == "cad" else (x, y) for _, x, y, org in sec["na"]]
        if len(pts) < 2:
            raise ErroSecao("o NA precisa de pelo menos 2 pontos")
        xmin, _, xmax, _ = dominio.bounds
        larg = xmax - xmin
        estendido = [(min(pts[0][0], xmin) - larg, pts[0][1])] + pts + [(max(pts[-1][0], xmax) + larg, pts[-1][1])]
        if pts[0][0] > xmin + EPS or pts[-1][0] < xmax - EPS:
            avisos.append("o NA não cobria a seção inteira; foi prolongado na horizontal até o contorno")
        corte = LineString(estendido).intersection(dominio)
        partes = [g for g in getattr(corte, "geoms", [corte]) if g.geom_type == "LineString" and g.length > EPS]
        if not partes:
            raise ErroSecao("o NA não passa pela seção")
        if len(partes) > 1:
            avisos.append(f"o NA cruza o contorno {len(partes)} vezes; usei o trecho mais longo")
        linha = max(partes, key=lambda g: g.length)
        na_pts = [tuple(c[:2]) for c in linha.coords]
        if na_pts[0][0] > na_pts[-1][0]:
            na_pts.reverse()
        for p in (na_pts[0], na_pts[-1]):
            inserir_ponto_nos_aneis(regioes, p)

    # --- arestas: contadas uma vez = contorno; duas vezes = interface de material ---
    contagem = defaultdict(int)
    for r in regioes:
        for anel in r["aneis"].values():
            ks = [chave(p) for p in anel]
            for i in range(len(ks)):
                a, b = ks[i], ks[(i + 1) % len(ks)]
                if a != b:
                    contagem[frozenset((a, b))] += 1
    if any(n > 2 for n in contagem.values()):
        raise ErroSecao("há regiões sobrepostas (aresta compartilhada por mais de duas regiões)")
    borda = [tuple(e) for e, n in contagem.items() if n == 1]
    interfaces = [tuple(e) for e, n in contagem.items() if n == 2]
    lacos = encadear(borda)
    if len(lacos) != 1 or lacos[0][0] != lacos[0][-1]:
        raise ErroSecao("não consegui fechar um contorno externo único")
    contorno = lacos[0][:-1]
    if area2(contorno) < 0:
        contorno.reverse()
    i0 = min(range(len(contorno)), key=lambda i: (contorno[i][1], contorno[i][0]))  # canto inferior esquerdo
    contorno = contorno[i0:] + contorno[:i0]

    # --- numeração dos vértices: contorno, depois internos, depois os do NA (como o Slide2) ---
    indice = {}
    vertices = []

    def numerar(k):
        if k not in indice:
            vertices.append(k)
            indice[k] = len(vertices)
        return indice[k]

    for k in contorno:
        numerar(k)
    for r in regioes:
        for anel in r["aneis"].values():
            for p in anel:
                numerar(chave(p))
    na_idx = [numerar(chave(p)) for p in na_pts]

    # --- células ---
    celulas = []
    for r in regioes:
        poly = Polygon(r["aneis"][0], [r["aneis"][a] for a in sorted(r["aneis"]) if a])
        for tri in triangular(poly):
            ids = []
            for p in tri:
                k = chave(p)
                if k not in indice:
                    raise ErroSecao("a triangulação criou um vértice novo (geometria inesperada)")
                ids.append(indice[k])
            celulas.append((ids, materiais[r["material"]]["slot"]))
    soma = sum(Polygon([vertices[i - 1] for i in ids]).area for ids, _ in celulas)
    if abs(soma - dominio.area) > 1e-6 * max(1.0, dominio.area):
        raise ErroSecao(f"as células não cobrem a seção (área {soma:.4f} x {dominio.area:.4f})")

    # --- terreno: do ponto mais alto da borda esquerda ao da borda direita, pela parte de cima ---
    xs = [p[0] for p in contorno]
    xmin, xmax = min(xs), max(xs)
    esq = max((i for i, p in enumerate(contorno) if abs(p[0] - xmin) <= EPS), key=lambda i: contorno[i][1])
    dirt = max((i for i, p in enumerate(contorno) if abs(p[0] - xmax) <= EPS), key=lambda i: contorno[i][1])
    # contorno anti-horário: de dirt até esq, andando para frente, passa por cima
    caminho = []
    i = dirt
    while True:
        caminho.append(contorno[i])
        if i == esq:
            break
        i = (i + 1) % len(contorno)
    terreno = list(reversed(caminho))
    if any(terreno[j + 1][0] < terreno[j][0] - EPS for j in range(len(terreno) - 1)):
        avisos.append("o terreno tem reentrância (x volta para trás); confira a superfície no Slide2")

    # --- interfaces de material (geometry info tipo 3) ---
    linhas_mat = [[indice[k] for k in c] for c in encadear(interfaces)]

    # --- cargas sobre o terreno ---
    forcas, grupos, carga_avisos = montar_cargas(sec["cargas"], terreno)
    avisos += carga_avisos

    return {
        "vertices": vertices, "contorno": [indice[k] for k in contorno], "celulas": celulas,
        "terreno": [indice[k] for k in terreno], "interfaces": linhas_mat, "na": na_idx,
        "forcas": forcas, "grupos": grupos, "direcao": direcao, "avisos": avisos, "dy": dy,
        "regioes": regioes, "terreno_pts": terreno, "na_pts": na_pts,
    }


def grelha_do_script(terreno, direcao="right to left"):
    """Grelha automática com REGRA PRÓPRIA (não é o AutoGrid do Slide2, cuja regra não é documentada).

    H = desnível do terreno; face = trechos com inclinação maior que 10 %.
    Centros em X: da face 1,5 H para o lado do pé (para onde a massa escorrega, segundo a direção
    escolhida pelo usuário) até 0,5 H para o lado da crista. Em Y: do topo até topo + 2 H. 20 x 20.
    O módulo 04 avisa se o mínimo cair na borda da grelha.
    (v0.3 usava ±0,5 H e topo + 0,25 H a 1,5 H: no teste no Slide os 4 mínimos caíram na borda.)
    """
    ys = [y for _, y in terreno]
    H = max(max(ys) - min(ys), 1.0)
    face = [p for a, b in zip(terreno, terreno[1:]) if b[0] - a[0] > EPS and abs((b[1] - a[1]) / (b[0] - a[0])) > 0.1
            for p in (a, b)] or terreno
    x0, x1 = min(p[0] for p in face), max(p[0] for p in face)
    topo = max(ys)
    if direcao == "left to right":   # pé à direita
        return (x0 - 0.5 * H, topo, x1 + 1.5 * H, topo + 2.0 * H, 20, 20)
    return (x0 - 1.5 * H, topo, x1 + 0.5 * H, topo + 2.0 * H, 20, 20)


def y_no_terreno(terreno, x):
    for (x0, y0), (x1, y1) in zip(terreno, terreno[1:]):
        if x0 - EPS <= x <= x1 + EPS and x1 - x0 > EPS:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return None


def montar_cargas(cargas, terreno):
    forcas, grupos, avisos = [], [], []
    x_ini, x_fim = terreno[0][0], terreno[-1][0]
    for c in cargas:
        rot = f"carga da linha {c['linha_planilha']} da aba Cargas"
        ang = 270.0 if c["angulo"] is None else c["angulo"] % 360
        if c["tipo"] == "linha":
            y = y_no_terreno(terreno, c["xa"])
            if y is None:
                raise ErroSecao(f"{rot}: X = {c['xa']} fora do terreno ({x_ini:g} a {x_fim:g})")
            forcas.append({"tipo": 1, "x1": c["xa"], "y1": y, "ang": ang, "q": c["q"]})
            continue
        if abs(ang - 270) > 1e-9:
            raise ErroSecao(f"{rot}: carga distribuída só vertical (270°) nesta versão")
        xa, xb = sorted((c["xa"], c["xb"]))
        if xb - xa <= EPS:
            raise ErroSecao(f"{rot}: X início e X fim iguais")
        if xa < x_ini - EPS or xb > x_fim + EPS:
            raise ErroSecao(f"{rot}: trecho {xa:g} a {xb:g} sai do terreno ({x_ini:g} a {x_fim:g})")
        cortes = [xa] + [x for x, _ in terreno if xa + EPS < x < xb - EPS] + [xb]
        inicio = len(forcas)
        for x0, x1 in zip(cortes, cortes[1:]):
            forcas.append({"tipo": 0, "x1": x0, "y1": y_no_terreno(terreno, x0), "x2": x1,
                           "y2": y_no_terreno(terreno, x1), "ang": 270.0, "q": c["q"]})
        if len(cortes) > 2:
            avisos.append(f"{rot}: atravessa {len(cortes) - 2} quebra(s) do terreno e foi dividida em trechos; "
                          "confira no Slide2")
        grupos.append({"ini": inicio, "fim": len(forcas) - 1, "q": c["q"]})
    return forcas, grupos, avisos


# ----------------------------------------------------------------------------
# Escrita do .sli
# ----------------------------------------------------------------------------
def fmt(v):
    """Número como o Slide2 grava em `vertices` (%.15g, expoente com 3 dígitos)."""
    v = 0.0 if abs(v) < 1e-12 else v
    s = f"{v:.15g}"
    m = re.match(r"^(.*e[+-])(\d+)$", s)
    return f"{m.group(1)}{int(m.group(2)):03d}" if m else s


def fmt_geo(v):
    """Número como o Slide2 grava em `geometry info` (15 algarismos significativos)."""
    if abs(v) < 1e-12:
        return "0.000000000000000"
    d = int(math.floor(math.log10(abs(v)))) + 1
    if d <= -3:
        return fmt(v)
    return f"{v:.{max(15 - max(d, 1), 0)}f}" if d >= 1 else f"{v:.15f}"


def trocar_secao(texto, nome, novo, proxima):
    padrao = rf"(?ms)^{re.escape(nome)}:\n.*?(?=^{re.escape(proxima)}:)"
    saida, n = re.subn(padrao, lambda m: novo.rstrip("\n") + "\n\n", texto, count=1)
    if n != 1:
        raise ValueError(f"Não encontrei a seção '{nome}' (antes de '{proxima}') no modelo-base.")
    return saida


def gerar_sli(base, geo, materiais, metodos, busca=None):
    t = base
    if busca:
        codigo = dict((k, c) for k, _, c in BUSCAS[busca["tipo"]])[busca["metodo"]]
        campos = {"mode": 0 if busca["tipo"] == "circular" else 1}
        campos["circularsearch" if busca["tipo"] == "circular" else "search"] = codigo
        for chave, valor in campos.items():
            t, n = re.subn(rf"(?m)^(\s*{chave}:).*$", lambda m, v=valor: f"{m.group(1)} {v}", t, count=1)
            if n != 1:
                raise ValueError(f"Modelo-base sem '{chave}'.")
        g = geo.get("grelha")
        t = trocar_secao(t, "grids", "grids:\n" + (
            f"  1: x1: {fmt(g[0])} y1: {fmt(g[1])}  x2: {fmt(g[2])} y2: {fmt(g[3])}  nx: {g[4]} ny: {g[5]}" if g else ""),
            "centers")
    # parâmetros globais
    t, n = re.subn(r"(?m)^(\s*direction:).*$", lambda m: f"{m.group(1)} {geo['direcao']}", t, count=1)
    mask = sum(v for k, _, v in METODOS if k in metodos)
    t, n2 = re.subn(r"(?m)^(\s*methods:).*$", lambda m: f"{m.group(1)} {mask}", t, count=1)
    if n != 1 or n2 != 1:
        raise ValueError("Modelo-base sem 'direction' ou 'methods'.")
    t = re.sub(r"(?ms)^side force function:\n.*?\n\n", "", t)
    if "gle" in metodos:
        t = t.replace("\n\nmaterial types:\n", "\n\nside force function:\n  type: half_sine\n\nmaterial types:\n", 1)

    # materiais (todos os slots usam o NA quando há NA, como o Slide2 grava)
    wt = 1 if geo["na"] else 0
    por_slot = {m["slot"]: m for m in materiais.values()}

    def linha_mat(m):
        k = int(m.group(1))
        resto = m.group(0)
        resto = re.sub(r"wtable:\s*\S+", f"wtable: {wt}", resto)
        if k in por_slot:
            mt = por_slot[k]
            resto = re.sub(r"c:\s*\S+", f"c: {fmt(mt['c'])}", resto, count=1)
            resto = re.sub(r"phi:\s*\S+", f"phi: {fmt(mt['phi'])}", resto, count=1)
            resto = re.sub(r"uw:\s*\S+", f"uw: {fmt(mt['gamma'])}", resto, count=1)
        return resto

    t = re.sub(r"(?m)^\s*soil(\d+) = type:.*$", linha_mat, t)

    def cor(m):
        k = int(m.group(1))
        mt = por_slot.get(k)
        if not mt or not mt.get("cor"):
            return m.group(0)
        h = mt["cor"].lstrip("#")
        if not re.fullmatch(r"[0-9a-fA-F]{6}", h):
            return m.group(0)
        r_, g_, b_ = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        return f"  Material {k}    red: {r_}  green: {g_}  blue: {b_} hatch: {m.group(2)}"

    t = re.sub(r"(?m)^  Material (\d+)    red: \d+  green: \d+  blue: \d+ hatch: (\S+)$", cor, t)

    v = geo["vertices"]
    t = trocar_secao(t, "vertices", "vertices:\n" + "\n".join(
        f"  {i} x: {fmt(x)}  y: {fmt(y)}" for i, (x, y) in enumerate(v, 1)), "cells")
    t = trocar_secao(t, "cells", "cells:\n" + "\n".join(
        f"  {i}  vertices: [{a},{b},{c}] material: soil{s}" for i, ((a, b, c), s) in enumerate(geo["celulas"], 1)),
        "anchors")
    t = trocar_secao(t, "water table", "water table:\n" + (
        "  vertices: [" + ",".join(map(str, geo["na"])) + "]" if geo["na"] else ""), "drawdown line")
    t = trocar_secao(t, "slope", "slope:\n  1  vertices: [" + ",".join(map(str, geo["terreno"])) + "]", "exterior")
    t = trocar_secao(t, "exterior", "exterior:\n  1  vertices: [" + ",".join(map(str, geo["contorno"])) + "]", "forces")

    linhas = ["forces:"]
    for i, f in enumerate(geo["forcas"], 1):
        if f["tipo"] == 0:
            linhas.append(f"  {i} type: 0 x1: {fmt(f['x1'])} y1: {fmt(f['y1'])} x2: {fmt(f['x2'])} y2: {fmt(f['y2'])} "
                          f"angle: {fmt(f['ang'])} load: {fmt(f['q'])} load2: {fmt(f['q'])} stage2: 0 design_standard_option: 0")
        else:
            linhas.append(f"  {i} type: 1 x1: {fmt(f['x1'])} y1: {fmt(f['y1'])} angle: {fmt(f['ang'])} "
                          f"load: {fmt(f['q'])} stage2: 0 design_standard_option: 0")
    if geo["grupos"]:
        linhas += ["", "dist load group:", f"  num: {len(geo['grupos'])}"]
        for g in geo["grupos"]:
            linhas += [f"  begin: {g['ini']}   end: {g['fim']}", "  orient: 4   angle: 0   flip: 0",
                       "  type: 0   params: 1", f"    {fmt(g['q'])}"]
    if geo["forcas"]:
        linhas += ["", "stats params loads:", f"  num_loads: {len(geo['forcas'])}"]
        for i in range(len(geo["forcas"])):
            linhas += [f"  begin: {i}   end: {i}   num: 1", "    2 0 0 0  is_on: 0"]
    t = trocar_secao(t, "forces", "\n".join(linhas), "noncircular analysis")

    x1, y1 = v[geo["terreno"][0] - 1]
    x2, y2 = v[geo["terreno"][-1] - 1]
    t, n = re.subn(r"(?m)^(\s*x1:)\s*\S+(\s+y1:)\s*\S+(\s+x2:)\s*\S+(\s+y2:)\s*\S+",
                   lambda m: f"{m.group(1)} {fmt(x1)}{m.group(2)} {fmt(y1)}{m.group(3)} {fmt(x2)}{m.group(4)} {fmt(y2)}",
                   t, count=1)
    if n != 1:
        raise ValueError("Modelo-base sem 'slope limits'.")

    def linha_geo(tipo, fim, i):
        x, y = v[i - 1]
        return f"         {tipo}                {fim}        {fmt_geo(x)},{fmt_geo(y)}           0              0          1"

    rows = [linha_geo(0, 1 if j == len(geo["contorno"]) - 1 else 0, i) for j, i in enumerate(geo["contorno"])]
    for cadeia in geo["interfaces"]:
        rows += [linha_geo(3, 1 if j == len(cadeia) - 1 else 0, i) for j, i in enumerate(cadeia)]
    geom = ("geometry info:\n#0:External boundary  1:Excavation  2:Joint  3:Material  4:Stage\n"
            "#  Material Type    End Flag        Vertex (x,y)        Disc (x,y)       A.B.I    Visible\n"
            "# ----------------------------------------------------------------------------------------------\n"
            + "\n".join(rows) + "\n")
    t, n = re.subn(r"(?ms)^geometry info:\n.*\Z", lambda m: geom, t, count=1)
    if n != 1:
        raise ValueError("Modelo-base sem 'geometry info'.")
    return t


def gravar_slim(base_slim, destino, sli_texto):
    with zipfile.ZipFile(base_slim) as zin:
        membros = [(info, zin.read(info.filename)) for info in zin.infolist()]
    idx = [i for i, (info, _) in enumerate(membros) if info.filename.lower().endswith(".sli")]
    if len(idx) != 1:
        raise ValueError("O modelo-base deve ter exatamente um .sli.")
    original = membros[idx[0]][1]
    nl = "\r\n" if b"\r\n" in original else "\n"
    membros[idx[0]] = (membros[idx[0]][0], sli_texto.replace("\n", nl).encode("utf-8"))
    destino.parent.mkdir(parents=True, exist_ok=True)
    # Cabeçalhos ZIP NOVOS: copiar os ZipInfo do molde (campos extra, flags) gera arquivos que o
    # Slide recusa com "Parâmetro incorreto" (testado no Slide 6.0).
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zout:
        for info, dados in membros:
            p = Path(info.filename)
            nome = destino.stem + p.suffix if p.suffix.lower() in {".sli", ".slv", ".sltm"} else info.filename
            zout.writestr(nome, dados)


def desenhar_previa(sec, geo, materiais, caminho):
    import matplotlib
    from matplotlib.figure import Figure
    from matplotlib.patches import Polygon as MPoly
    paleta = ["#C8E6C9", "#FFF59D", "#FFCC80", "#B3E5FC", "#F8BBD0", "#D1C4E9", "#DCEDC8", "#FFE0B2"]
    fig = Figure(figsize=(11, 5.2), dpi=110)
    ax = fig.subplots()
    nomes_usados = []
    for r in geo["regioes"]:
        m = materiais[r["material"]]
        cor = ("#" + m["cor"].lstrip("#")) if m.get("cor") and re.fullmatch(r"#?[0-9a-fA-F]{6}", m["cor"]) \
            else paleta[(m["slot"] - 1) % len(paleta)]
        ax.add_patch(MPoly(r["aneis"][0], closed=True, fc=cor, ec="0.45", lw=0.8))
        for a in r["aneis"]:
            if a:
                ax.add_patch(MPoly(r["aneis"][a], closed=True, fc="none", ec="0.45", lw=0.8))
        if r["material"] not in nomes_usados:
            nomes_usados.append(r["material"])
        c = Polygon(r["aneis"][0], [r["aneis"][a] for a in r["aneis"] if a]).representative_point()
        ax.text(c.x, c.y, f"{r['material']}\nsoil{m['slot']}", ha="center", va="center", fontsize=8)
    xs, ys = zip(*geo["terreno_pts"])
    ax.plot(xs, ys, color="0.15", lw=2)
    if geo.get("grelha"):
        from matplotlib.patches import Rectangle
        g = geo["grelha"]
        ax.add_patch(Rectangle((g[0], g[1]), g[2] - g[0], g[3] - g[1], fill=False, ec="#6A1B9A", lw=1, ls="--"))
        ax.text(g[0], g[3], f" grelha {g[4]}x{g[5]}", color="#6A1B9A", fontsize=8, va="bottom")
    if geo["na_pts"]:
        xs, ys = zip(*geo["na_pts"])
        ax.plot(xs, ys, color="#1565C0", lw=1.6)
        ax.plot([xs[len(xs) // 2]], [ys[len(ys) // 2] + 0.4], marker="v", color="#1565C0", ms=8)
    for f in geo["forcas"]:
        ang = math.radians(f["ang"])
        dx, dy = math.cos(ang), math.sin(ang)
        alt = 0.06 * (max(geo["vertices"])[0] - min(geo["vertices"])[0])
        pts = [(f["x1"], f["y1"])] + ([(f["x2"], f["y2"])] if f["tipo"] == 0 else [])
        if f["tipo"] == 0:
            ax.plot([f["x1"], f["x2"]], [f["y1"] - dy * alt, f["y2"] - dy * alt], color="#C62828", lw=1)
        for (px, py) in pts:
            ax.annotate("", xy=(px, py), xytext=(px - dx * alt, py - dy * alt),
                        arrowprops=dict(arrowstyle="->", color="#C62828", lw=1.2))
        lx, ly = pts[0] if f["tipo"] == 1 else ((f["x1"] + f["x2"]) / 2, (f["y1"] + f["y2"]) / 2)
        ax.text(lx - dx * alt, ly - dy * alt, f"{f['q']:g} {'kN/m' if f['tipo'] == 1 else 'kPa'}",
                color="#C62828", fontsize=8, ha="center", va="bottom")
    seta = "→" if geo["direcao"] == "left to right" else "←"
    metodos_txt = ""
    ax.set_title(f"{sec['nome']}  |  ruptura {seta} ({geo['direcao']})" + metodos_txt, fontsize=10)
    ax.set_aspect("equal")
    ax.autoscale_view()
    ax.margins(0.06)
    ax.grid(alpha=0.3)
    ax.set_xlabel("x (m)")
    ax.set_ylabel("cota (m)")
    fig.tight_layout()
    fig.savefig(caminho)


def pasta_livre(base: Path) -> Path:
    if not base.exists():
        return base
    k = 2
    while (base.parent / f"{base.name}_{k}").exists():
        k += 1
    return base.parent / f"{base.name}_{k}"


# ----------------------------------------------------------------------------
# Programa principal
# ----------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Planilha do módulo 02 -> um .slim por seção.")
    ap.add_argument("planilha", type=Path, nargs="?", help="Planilha .xlsx; se omitida, abre janela para escolher")
    ap.add_argument("--modelo-base", type=Path, help=f"Molde .slim (padrão: {MODELO_BASE.relative_to(RAIZ)})")
    ap.add_argument("--saida", type=Path, help="Pasta dos modelos (padrão: <planilha>_modelos, nunca sobrescreve)")
    ap.add_argument("--config", type=Path, help=".json de uma rodada anterior")
    ap.add_argument("--direcao", choices=list(DIRECOES), help="Mesma direção para todas as seções")
    ap.add_argument("--superficie", choices=list(BUSCAS), help="Tipo de superfície")
    ap.add_argument("--busca", help="Busca: grid, slope, autorefine (circular); block, path, annealing, autorefine (não circular)")
    ap.add_argument("--grelha", choices=["planilha", "auto"], help="Grid Search: grelha da aba Grelha ou automática do script")
    ap.add_argument("--metodos", help="Métodos: números 1-9 ou nomes (" + ", ".join(m[0] for m in METODOS) + ")")
    args = ap.parse_args(argv)
    cfg = json.loads(args.config.read_text(encoding="utf-8")) if args.config else {}

    try:
        planilha = args.planilha or (Path(cfg["planilha"]) if cfg.get("planilha") else None) or \
            escolher_arquivo("Selecione a planilha de seções (.xlsx)", [("Planilha Excel", "*.xlsx")])
        planilha = planilha.expanduser().resolve()
        base = (args.modelo_base or Path(cfg.get("modelo_base", MODELO_BASE))).expanduser().resolve()
        if not planilha.is_file():
            raise ValueError(f"Planilha não encontrada: {planilha}")
        if not base.is_file():
            raise ValueError(f"Modelo-base não encontrado: {base}")
        with zipfile.ZipFile(base) as z:
            nome_sli = [n for n in z.namelist() if n.lower().endswith(".sli")]
            base_txt = z.read(nome_sli[0]).decode("utf-8").replace("\r\n", "\n")

        materiais, secoes = ler_planilha(planilha)
        ativas = [s for s in sorted(secoes.values(), key=lambda s: s["n"]) if s["ativa"]]
        print(f"Planilha: {planilha.name}  |  {len(materiais)} material(is)  |  {len(ativas)} seção(ões) ativa(s)")
        for s in ativas:
            extras = []
            if s["na"]:
                extras.append(f"NA com {len(s['na'])} pontos")
            if s["cargas"]:
                extras.append(f"{len(s['cargas'])} carga(s)")
            if s["cota_real"] is not None:
                extras.append(f"cota real do topo {s['cota_real']:g}")
            print(f"  {s['n']}) {s['nome']}: {len(s['regioes'])} região(ões)" + (f"; {', '.join(extras)}" if extras else ""))
        if not ativas:
            raise ValueError("Nenhuma seção ativa na aba Secoes.")
        if not materiais:
            raise ValueError("A aba Materiais está vazia.")

        # --- direção da ruptura: sempre decisão do usuário ---
        direcoes = {}
        if args.direcao:
            direcoes = {s["n"]: args.direcao for s in ativas}
        elif cfg.get("direcoes"):
            direcoes = {int(k): v for k, v in cfg["direcoes"].items()}
        faltam = [s for s in ativas if s["n"] not in direcoes]
        if faltam:
            print("\nDireção da ruptura (veja as prévias da planilha):  1 = direita → esquerda   2 = esquerda → direita")
            conv = lambda t: {"1": "dir-esq", "2": "esq-dir"}[t]
            mesma = perguntar("A mesma direção para todas as seções? (s/n)", None, lambda t: t.lower(),
                              lambda v: v in ("s", "n"), "Digite s ou n.")
            if mesma == "s":
                d = perguntar("Direção para todas (1 ou 2)", None, conv, msg_erro="Digite 1 ou 2.")
                for s in faltam:
                    direcoes[s["n"]] = d
            else:
                for s in faltam:
                    direcoes[s["n"]] = perguntar(f"  Seção {s['n']} ({s['nome']}) (1 ou 2)", None, conv,
                                                 msg_erro="Digite 1 ou 2.")

        # --- métodos: sempre decisão do usuário ---
        metodos = ler_metodos(args.metodos) if args.metodos else cfg.get("metodos")
        if not metodos:
            print("\nMétodos de equilíbrio limite:")
            for k, (_, nome, _) in enumerate(METODOS, 1):
                print(f"  {k}) {nome}")
            metodos = perguntar("Quais métodos? (números separados por vírgula, ex.: 1,9 = Bishop e Spencer)", None, ler_metodos,
                                msg_erro="Use números de 1 a 9 separados por vírgula.")

        # --- busca da superfície: sempre decisão do usuário ---
        busca = dict(cfg.get("busca") or {})
        if args.superficie:
            busca["tipo"] = args.superficie
        if args.busca:
            busca["metodo"] = args.busca
        if args.grelha:
            busca["grelha"] = args.grelha
        if "tipo" not in busca:
            busca["tipo"] = perguntar("\nTipo de superfície: 1 = circular, 2 = não circular", None,
                                      lambda t: {"1": "circular", "2": "nao_circular"}[t], msg_erro="Digite 1 ou 2.")
        opcoes = BUSCAS[busca["tipo"]]
        if busca.get("metodo") not in {k for k, _, _ in opcoes}:
            if "metodo" in busca:
                raise ValueError(f"Busca '{busca['metodo']}' não existe para superfície {busca['tipo']}.")
            print("Método de busca:")
            for k, (_, nome, _) in enumerate(opcoes, 1):
                print(f"  {k}) {nome}")
            busca["metodo"] = perguntar("Qual?", None, lambda t: opcoes[int(t) - 1][0],
                                        msg_erro=f"Digite um número de 1 a {len(opcoes)}.")
        if busca["tipo"] == "circular" and busca["metodo"] == "grid" and busca.get("grelha") not in ("planilha", "auto"):
            busca["grelha"] = perguntar("Grelha: 1 = da aba Grelha (coordenadas por seção), 2 = automática "
                                        "(regra do script, não o AutoGrid do Slide)", None,
                                        lambda t: {"1": "planilha", "2": "auto"}[t], msg_erro="Digite 1 ou 2.")
        if busca["metodo"] == "block":
            print("  Aviso: Block Search precisa de janelas/linhas de busca, que o script ainda não grava; "
                  "defina-as no Slide2 antes de calcular.")

        gsat = [m["nome"] for m in materiais.values() if m["gsat"] is not None]
        destino = pasta_livre((args.saida or planilha.with_name(planilha.stem + "_modelos")).expanduser().resolve())
        destino.mkdir(parents=True)
        print(f"\nGerando em {destino}")
        resultado = []
        for s in ativas:
            try:
                geo = montar_secao(s, materiais, DIRECOES[direcoes[s["n"]]])
                geo["grelha"] = None
                if busca["tipo"] == "circular" and busca["metodo"] == "grid":
                    if busca["grelha"] == "planilha":
                        if not s["grelha"]:
                            raise ErroSecao("Grid Search com grelha da planilha, mas a seção não tem linha na aba Grelha")
                        geo["grelha"] = s["grelha"]
                    else:
                        geo["grelha"] = grelha_do_script(geo["terreno_pts"], geo["direcao"])
                sli = gerar_sli(base_txt, geo, materiais, metodos, busca)
                arq = destino / f"{s['nome']}.slim"
                gravar_slim(base, arq, sli)
                desenhar_previa(s, geo, materiais, destino / f"{s['nome']}.png")
                resultado.append({"secao": s["n"], "arquivo": arq.name, "avisos": geo["avisos"]})
                print(f"  ok  {arq.name}: {len(geo['vertices'])} vértices, {len(geo['celulas'])} células, "
                      f"{len(geo['forcas'])} carga(s)" + (f", NA com {len(geo['na'])} pontos" if geo["na"] else "")
                      + (f"  AVISOS: {' | '.join(geo['avisos'])}" if geo["avisos"] else ""))
            except ErroSecao as exc:
                resultado.append({"secao": s["n"], "erro": str(exc)})
                print(f"  ERRO seção {s['n']} ({s['nome']}): {exc}")
        if gsat:
            print(f"  Aviso: γ saturado ainda não é gravado no modelo ({', '.join(gsat)}).")
        config = {"versao_script": VERSAO, "data": datetime.now().isoformat(timespec="seconds"),
                  "planilha": str(planilha), "modelo_base": str(base),
                  "direcoes": {str(k): v for k, v in direcoes.items()}, "metodos": metodos,
                  "busca": busca, "resultado": resultado}
        (destino / "respostas.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Respostas gravadas em {destino / 'respostas.json'} (reuse com --config).")
        print("Antes de calcular: abra os modelos no Slide2 e confira a geometria. Para calcular em lote, use o módulo 04.")
        return 0 if all("erro" not in r for r in resultado) else 1
    except (RuntimeError, ValueError, OSError, zipfile.BadZipFile) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2
    except (EOFError, KeyboardInterrupt):
        print("\nOperação cancelada.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

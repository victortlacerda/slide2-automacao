"""Geradores de DXF sintéticos para os testes do módulo 02.

Todos usam o perfil do guia da aula: terreno (0,0)-(20,0)-(23,6)-(43,6), base em -15,
largura 43 m -> área total 774 m².
"""
import ezdxf

TERRENO = [(0, 0), (20, 0), (23, 6), (43, 6)]


def y_interface2(x):
    """Interface inclinada de (0,-8) a (43,-10)."""
    return -8 - 2 * (x / 43)


def tres_camadas(caminho):
    """Seção 1 em LINEs soltas (x = 0), seção 2 em polilinhas fechadas com vértice em T (x = 100),
    seção 3 com polilinha aberta fechada pela camada de cima (x = 200)."""
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6
    msp = doc.modelspace()
    L = {"dxfattribs": {"layer": "SEC_LINHAS"}}
    P = {"dxfattribs": {"layer": "SEC_POLI"}}
    for a, b in zip(TERRENO, TERRENO[1:]):
        msp.add_line(a, b, **L)
    for a, b in [((0, 0), (0, -15)), ((43, 6), (43, -15)), ((0, -15), (43, -15)),
                 ((0, -3), (43, -3)), ((0, -8), (43, y_interface2(43)))]:
        msp.add_line(a, b, **L)
    msp.add_text("SECAO 1", dxfattribs={"layer": "SEC_LINHAS", "height": 1.0}).set_placement((0, 9))
    dx = 100
    msp.add_lwpolyline([(x + dx, y) for x, y in TERRENO] + [(43 + dx, -3), (dx, -3)], close=True, **P)
    msp.add_lwpolyline([(dx, -3), (43 + dx, -3), (43 + dx, y_interface2(43)), (20 + dx, y_interface2(20)), (dx, -8)],
                       close=True, **P)
    msp.add_lwpolyline([(dx, -8), (43 + dx, y_interface2(43)), (43 + dx, -15), (dx, -15)], close=True, **P)
    dx = 200
    msp.add_lwpolyline([(x + dx, y) for x, y in TERRENO] + [(43 + dx, -3), (dx, -3)], close=True, **P)
    msp.add_lwpolyline([(dx, -3), (dx, -15), (43 + dx, -15), (43 + dx, -3)], **P)
    doc.saveas(caminho)


def casos_de_desenho(caminho):
    """A: falha de 0,4 mm (x=0); B: falha de 10 cm (x=100); C: lente/furo (x=200); D: fundo em arco (x=300)."""
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6
    msp = doc.modelspace()
    for dx, ponta in ((0, -3.0004), (100, -3.1)):
        msp.add_lwpolyline([(x + dx, y) for x, y in TERRENO] + [(43 + dx, -3), (dx, -3)], close=True)
        msp.add_line((dx, -3), (dx, -15))
        msp.add_line((dx, -15), (43 + dx, -15))
        msp.add_line((43 + dx, -15), (43 + dx, ponta))
    dx = 200
    msp.add_lwpolyline([(x + dx, y) for x, y in TERRENO] + [(43 + dx, -15), (dx, -15)], close=True)
    msp.add_lwpolyline([(10 + dx, -8), (30 + dx, -8), (30 + dx, -5), (10 + dx, -5)], close=True)
    dx = 300
    pts = [(x + dx, y, 0, 0, 0) for x, y in TERRENO] + [(43 + dx, -15, 0, 0, 0.2), (dx, -15, 0, 0, 0)]
    msp.add_lwpolyline(pts, format="xyseb", close=True)
    doc.saveas(caminho)



def quatro_secoes_em_grade(caminho):
    """Quatro seções numa prancha 2 x 2 (exemplo das imagens do README).

    Variações: camadas em LINEs soltas, em polilinhas, talude 1:1 com berma e duas camadas.
    """
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6
    msp = doc.modelspace()
    for nome in ("SECOES", "TEXTOS"):
        doc.layers.add(nome)
    S = {"dxfattribs": {"layer": "SECOES"}}

    def texto(t, x, y):
        msp.add_text(t, dxfattribs={"layer": "TEXTOS", "height": 1.6}).set_placement((x, y))

    # (0, 0): três camadas em linhas soltas
    ox, oy = 0, 0
    pts = [(0, 0), (20, 0), (23, 6), (43, 6)]
    for a, b in zip(pts, pts[1:]):
        msp.add_line((a[0] + ox, a[1] + oy), (b[0] + ox, b[1] + oy), **S)
    for a, b in [((0, 0), (0, -15)), ((43, 6), (43, -15)), ((0, -15), (43, -15)), ((0, -3), (43, -3)),
                 ((0, -8), (43, -10))]:
        msp.add_line((a[0] + ox, a[1] + oy), (b[0] + ox, b[1] + oy), **S)
    texto("SECAO A-A", ox, oy + 9)

    # (60, 0): três camadas em polilinhas fechadas
    ox, oy = 60, 0
    sh = lambda p: [(x + ox, y + oy) for x, y in p]
    msp.add_lwpolyline(sh([(0, 0), (18, 0), (24, 8), (43, 8), (43, -4), (0, -2)]), close=True, **S)
    msp.add_lwpolyline(sh([(0, -2), (43, -4), (43, -9), (0, -9)]), close=True, **S)
    msp.add_lwpolyline(sh([(0, -9), (43, -9), (43, -16), (0, -16)]), close=True, **S)
    texto("SECAO B-B", ox, oy + 11)

    # (0, -40): talude 1:1 com berma, duas camadas
    ox, oy = 0, -40
    msp.add_lwpolyline(sh([(0, 0), (15, 0), (19, 4), (23, 4), (27, 8), (43, 8), (43, -5), (0, -5)]), close=True, **S)
    msp.add_lwpolyline(sh([(0, -5), (43, -5), (43, -15), (0, -15)]), close=True, **S)
    texto("SECAO C-C", ox, oy + 11)

    # (60, -40): talude baixo com lente de argila
    ox, oy = 60, -40
    msp.add_lwpolyline(sh([(0, 0), (22, 0), (26, 5), (43, 5), (43, -14), (0, -14)]), close=True, **S)
    msp.add_lwpolyline(sh([(8, -6), (30, -5), (30, -8), (8, -9)]), close=True, **S)
    texto("SECAO D-D", ox, oy + 8)
    doc.saveas(caminho)


if __name__ == "__main__":
    import sys
    tres_camadas(sys.argv[1] if len(sys.argv) > 1 else "tres_camadas.dxf")
    casos_de_desenho(sys.argv[2] if len(sys.argv) > 2 else "casos_de_desenho.dxf")
    quatro_secoes_em_grade(sys.argv[3] if len(sys.argv) > 3 else "quatro_secoes_em_grade.dxf")

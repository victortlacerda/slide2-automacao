# Registro de mudanças

## Módulo 02: cad_para_planilha

### v0.4
- Aba Secoes: coluna opcional "Cota real do ponto mais alto" para seções que não estão na cota
  real no desenho (ex.: empilhadas na prancha). O módulo 03 desloca a seção em Y para essa cota.

### v0.3
- Modo `auto`: grupos contidos no retângulo de outro (lentes, bolsões) passam a pertencer a ele,
  em vez de virarem uma seção à parte.
- Modo `auto`: numeração em ordem de leitura da prancha (linhas de cima para baixo, esquerda → direita).
- Tela de seleção com folga fixa de 15% da maior dimensão em todas as bordas, para haver espaço
  de clicar fora da seção e arrastar o retângulo (antes as seções ficavam coladas na borda).

### v0.2
- Modo `auto` mostra as janelas sugeridas no desenho (cada seção numa cor) antes de "Aceitar?";
  sem tela gráfica, grava `<dxf>_janelas_sugeridas.png`.

### v0.1
- Leitura de DXF (linhas, polilinhas, arcos, splines, blocos); DWG e arquivo vazio recusados.
- Unidade do desenho sempre perguntada; exagero vertical; deslocamento opcional para X = 0.
- Seções por janela desenhada na tela, por coordenadas ou por agrupamento (auto).
- Regiões fechadas por geometria; encaixe de pontas e vértices a menos de 1 mm.
- Avisos: pontas soltas com coordenadas, partes desconectadas, vazios, furos, janelas sobrepostas,
  entidades cortadas, mais de 20 regiões.
- Planilha com Materiais, Secoes, Regioes (lista suspensa de material), Vertices, Previas e Origem;
  respostas gravadas em JSON (`--config`).

## Módulo 01: slide2_editar_modelo

### v0.1
- Modelo `.slim` com contorno externo e um material a partir do molde `vazio.slim`.

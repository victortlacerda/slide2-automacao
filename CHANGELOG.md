# Registro de mudanças

## Módulo 03: planilha_para_slim

### v0.1
- Um `.slim` por seção ativa a partir da planilha do módulo 02 e do molde `vazio.slim`.
- Várias camadas (células triangulares por região), interfaces de material, contorno, terreno e
  limites de busca montados automaticamente.
- NA da aba NA, recortado no contorno; cargas distribuídas verticais e em linha com ângulo.
- Direção da ruptura e métodos perguntados no terminal (ordem da janela do Slide2), gravados em JSON.
- Cota real opcional por seção; cor do material; prévia PNG de cada modelo.
- Validado reconstruindo a amostra a02 do Slide2 bloco a bloco.

## Módulo 02: cad_para_planilha

### v0.5
- Pergunta a camada CAD do nível d'água e grava os pontos de cada seção na nova aba NA (origem CAD).
- Nova aba Cargas, preenchida pelo usuário (lista suspensa distribuida/linha).

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

# Registro de mudanças

## Módulo 04: calcular_lote

### v0.1
- Calcula uma pasta de `.slim` com o `aslidew.exe` do Slide2 (resultado gravado dentro do `.slim`).
- Lê o FS mínimo global por método, a superfície crítica e os contadores de superfícies.
- Avisos: centro na borda da grelha, superfície no limite de busca ou no fundo, FS inválido, FS-alvo.
- `resultados.xlsx` (Resumo, Figuras, Origem) e uma figura por seção.
- Caminho do `aslidew.exe` salvo em `~/.slide2_automacao.json`. Testado no Slide 6.0 do usuário.

## Módulo 03: planilha_para_slim

### v0.4
- Grelha automática nova: estende 1,5 H para o lado do pé (segundo a direção escolhida), 0,5 H para
  o lado da crista, do topo a topo + 2 H. Com a regra da v0.3, os 4 mínimos do teste no Slide caíram
  na borda da grelha; com a nova, nenhum.

### v0.3
- Tipo de superfície e busca perguntados no terminal (`--superficie`, `--busca`): circular (Grid,
  Slope, Auto Refine) e não circular (Block, Path, Simulated Annealing, Auto Refine).
- Grid Search: grelha da aba Grelha ou automática (regra própria; o AutoGrid do Slide não é imitado).
- Prévia mostra a grelha. Aviso para Block Search (objetos de busca não gravados).

### v0.2
- **Correção:** o `.slim` passa a ser gravado com cabeçalhos ZIP novos. Os herdados do molde faziam o
  Slide recusar o arquivo ("Parâmetro incorreto").
- Conferido no Slide 6.0 do usuário: camadas, lente, NA, cargas (inclusive atravessando o talude),
  métodos e direção abrem como esperado.

### v0.1
- Um `.slim` por seção ativa a partir da planilha do módulo 02 e do molde `vazio.slim`.
- Várias camadas (células triangulares por região), interfaces de material, contorno, terreno e
  limites de busca montados automaticamente.
- NA da aba NA, recortado no contorno; cargas distribuídas verticais e em linha com ângulo.
- Direção da ruptura e métodos perguntados no terminal (ordem da janela do Slide2), gravados em JSON.
- Cota real opcional por seção; cor do material; prévia PNG de cada modelo.
- Validado reconstruindo a amostra a02 do Slide2 bloco a bloco.

## Módulo 02: cad_para_planilha

### v0.6
- Nova aba Grelha (Seção, X1, Y1, X2, Y2, nx, ny) para Grid Search com grelha definida pelo usuário.

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

### v0.2
- **Correção:** mesma correção do empacotamento ZIP do módulo 03.

### v0.1
- Modelo `.slim` com contorno externo e um material a partir do molde `vazio.slim`.

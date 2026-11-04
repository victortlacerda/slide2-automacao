# Roadmap

## Fase 1: modelo básico (concluída)
- [x] Gerar `.slim` com boundary e um material a partir de um molde (módulo 01).

## Fase 2: CAD para planilha (concluída, v0.6)
- [x] Ler DXF, delimitar seções por janela, fechar regiões, gerar planilha e prévias (módulo 02).
- [x] Modo auto mostrando as janelas sugeridas no desenho antes de aceitar.
- [x] Modo auto: lentes ficam na seção envolvente; numeração em ordem de leitura da prancha.
- [x] Seções empilhadas na prancha: coluna opcional de cota real na aba Secoes.
- [ ] Testar com DXF real com camadas de solo desenhadas.
- [x] Confirmar a tela de seleção (modo `janela`) no computador do usuário.

## Fase 3: planilha para `.slim` (concluída)
Precisa das amostras do Slide2, cada uma salva a partir do `vazio.slim` com **uma única mudança**
(anotar os valores digitados):
- [x] Duas camadas: fronteira interna + 2 materiais com valores diferentes (amostra a01).
- [x] Um arquivo por método e um com todos: `methods` é máscara de bits (amostras em `docs/amostras_slide2/metodos`).
- [x] Direção da ruptura esquerda → direita (amostra a01).
- [x] Primeira versão já com nível d'água e sobrecarga (decisão #8).
- [x] NA que não coincide com vértices (amostra a02).
- [x] Orientação da carga distribuída: `orient: 4` = vertical (amostra a02).
- [x] Origem dos dados: NA do CAD ou da planilha; cargas só da planilha.

Entregas:
- [x] Várias camadas por seção, materiais da planilha.
- [x] NA (CAD ou planilha) e cargas (planilha).
- [x] Perguntas no terminal: direção por seção e métodos; respostas em JSON.
- [x] Abrir os modelos gerados no Slide2 do usuário e conferir (camadas, lente, NA, cargas, métodos, direção).
- [x] Tipo de superfície e busca (v0.3, fase 4).

## Fase 4: busca da superfície e cálculo (concluída)
- [x] Amostras de busca salvas no Slide: grelha, Slope, Auto Refine, AutoGrid, Block, Path, Annealing (`docs/amostras_slide2/busca`).
- [x] AutoGrid grava só coordenadas, sem marcador: não é imitado; grelha automática com regra própria.
- [x] Modelo salvo depois do Compute: formato do `.s01` (`docs/amostras_slide2/resultados`).
- [x] `aslidew.exe "modelo.slim"` calcula pela linha de comando (código de saída 2 mesmo dando certo).
- [x] Cálculo em lote e tabela de FS por seção e método (módulo 04), testado no Slide 6.0.
- [ ] Caso de validação: exemplo do guia da aula (FS ≈ 1,287 Bishop; 1,407 talude 1:1; 1,305 com 20 kPa).

## Fase 5: cenários e verificações
- [x] Nível d'água e sobrecarga (módulo 03).
- [ ] Cenários: a mesma seção com NA/cargas diferentes, num único lote.
- [x] Checagens: mínimo na borda da grelha, superfície no limite de busca ou no fundo (módulo 04).
- [ ] Checagem: mesmo método entre cenários.
- [x] FS-alvo opcional e relatório (tabela + figuras), módulo 04.
- [ ] FS-alvo por seção/cenário.

## Fase 6: extrair e exibir resultados (proposta, a decidir com o usuário)

O `.s01` traz bem mais do que o FS mínimo. Já confirmado na amostra r01:
todas as superfícies de cada centro da grelha com o FS de cada método; a superfície crítica em fatias;
e 16 grandezas por fatia (resistência friccional e coesiva, força normal na base, ângulo de atrito da
base, forças normal e cisalhante entre fatias, peso, poropressão, M-alfa, linha de empuxo, sismo,
coesão e material da base).

Extração (base para todos os gráficos):
- [ ] Ler todas as superfícies e os dados por fatia do `.s01` (hoje o módulo 04 lê só o mínimo).
- [ ] Gravar tabelas "limpas" (uma linha por seção × método, por superfície, por fatia) em xlsx/CSV,
      para o usuário fazer os próprios gráficos.

Gráficos por seção:
- [ ] **Mapa de FS na grelha** (curvas de nível sobre os centros), como o Slide: mostra se o mínimo é bem definido.
- [ ] **Faixa de superfícies críticas**: todas com FS até X % acima do mínimo, coloridas pelo FS.
- [ ] **Gráficos ao longo da superfície** (eixo x): tensão normal na base, poropressão, resistência
      mobilizada × disponível, forças entre fatias, linha de empuxo.

Gráficos do lote:
- [ ] **FS por seção e método** (barras) com a linha do FS-alvo.
- [ ] **Comparação entre métodos** (ex.: Bishop × Spencer, dispersão com a reta 1:1).
- [ ] **Superfícies críticas de volta ao CAD**: DXF com a superfície e o FS de cada seção, na posição da prancha.
- [ ] Contagem de superfícies válidas/inválidas por seção (sinal de grelha ou limites ruins).

Cenários (depende da fase 5):
- [ ] FS × nível d'água, FS × sobrecarga, FS × parâmetro do solo (sensibilidade, gráfico tornado).

Formato de entrega (decidir):
- PNG + planilha (como hoje) · relatório HTML interativo (zoom, passar o mouse) · memorial PDF/Word por seção.

## Ideias futuras
- Solo grampeado: inserir grampos e otimizar comprimentos (Crisp & Davies, 2022).
- Retroanálise de parâmetros (FS = 1), sensibilidade e análise probabilística.
- Memorial de cálculo automático.

## Decisões tomadas
- Resultados: FS mínimo por método **e** superfície crítica (centro, raio, entrada, saída, fatias).
- FS-alvo: opcional (`--fs-alvo`); sem ele, só reporta.

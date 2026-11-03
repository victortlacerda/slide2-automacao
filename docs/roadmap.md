# Roadmap

## Fase 1: modelo básico (concluída)
- [x] Gerar `.slim` com boundary e um material a partir de um molde (módulo 01).

## Fase 2: CAD para planilha (concluída, v0.4)
- [x] Ler DXF, delimitar seções por janela, fechar regiões, gerar planilha e prévias (módulo 02).
- [x] Modo auto mostrando as janelas sugeridas no desenho antes de aceitar.
- [x] Modo auto: lentes ficam na seção envolvente; numeração em ordem de leitura da prancha.
- [x] Seções empilhadas na prancha: coluna opcional de cota real na aba Secoes.
- [ ] Testar com DXF real com camadas de solo desenhadas.
- [x] Confirmar a tela de seleção (modo `janela`) no computador do usuário.

## Fase 3: planilha para `.slim` (módulo 03)
Precisa das amostras do Slide2, cada uma salva a partir do `vazio.slim` com **uma única mudança**
(anotar os valores digitados):
- [x] Duas camadas: fronteira interna + 2 materiais com valores diferentes (amostra a01).
- [ ] Só Bishop; só Fellenius; Bishop + Fellenius (e outros métodos que forem usados).
- [x] Direção da ruptura esquerda → direita (amostra a01).
- [x] Primeira versão já com nível d'água e sobrecarga (decisão #8).
- [x] NA que não coincide com vértices (amostra a02).
- [x] Orientação da carga distribuída: `orient: 4` = vertical (amostra a02).
- [x] Origem dos dados: NA do CAD ou da planilha; cargas só da planilha.

Entregas:
- [ ] Várias camadas por seção, materiais da planilha.
- [ ] Perguntas no terminal: direção por seção, métodos, tipo de superfície, busca; respostas em JSON.

## Fase 4: busca da superfície e cálculo
- [ ] Amostra com grelha circular manual (anotar limites e nº de centros) e limites de entrada/saída.
- [ ] Amostra com Auto Refine.
- [ ] Amostra com AutoGrid (ver se o arquivo guarda marcador ou coordenadas).
- [ ] Tipo de superfície não circular a usar (Path Search, Block, Auto Slope...).
- [ ] Modelo salvo depois do Compute.
- [ ] Caminho do `aslidew.exe`, versão do Slide2 e resultado de `aslidew.exe "modelo.slim"`.
- [ ] Rodar o cálculo em lote e ler o FS de cada seção para uma tabela.
- [ ] Caso de validação: exemplo do guia da aula (FS ≈ 1,287 Bishop; 1,407 talude 1:1; 1,305 com 20 kPa).

## Fase 5: cenários e verificações
- [ ] Nível d'água e sobrecarga (amostras do Slide2).
- [ ] Checagens automáticas: mínimo na borda da grelha, superfície tocando o contorno, mesmo método entre cenários.
- [ ] FS-alvo por seção/cenário e relatório (tabela + figuras).

## Ideias futuras
- Solo grampeado: inserir grampos e otimizar comprimentos (Crisp & Davies, 2022).
- Retroanálise de parâmetros (FS = 1), sensibilidade e análise probabilística.
- Memorial de cálculo automático.

## Decisões em aberto
- O que ler dos resultados: só o FS mínimo por método, ou também a superfície crítica?
- FS-alvo: por seção, por cenário, ou só reportar?

# 02 - CAD para planilha

`cad_para_planilha.py` lê um desenho **DXF** com uma ou várias seções, delimita cada seção,
fecha as regiões (camadas de solo) e gera a **planilha-padrão** usada pelos próximos módulos.

O usuário só precisa preencher a aba **Materiais** e escolher, na aba **Regioes**, o material
de cada região (lista suspensa).

## Uso

```bash
python cad_para_planilha.py                         # interativo
python cad_para_planilha.py desenho.dxf --unidade m --modo coordenadas \
    --janelas="0,-12,50,14;95,-12,145,14"           # sem perguntas
python cad_para_planilha.py --config desenho_secoes.json   # repete uma rodada
```

Use `--janelas=...` com sinal de igual: coordenadas negativas no início seriam lidas como opção.
O DWG não é lido; no CAD, use *Salvar como → DXF*.

## Perguntas no terminal

| Pergunta | O que significa |
|---|---|
| **Unidade do desenho** (obrigatória, sem padrão) | m, cm ou mm. O cabeçalho do DXF aparece só como informação. |
| **Exagero vertical** `[1]` | Se a escala vertical do desenho foi ampliada (ex.: H 1:500, V 1:100 → 5), o Y é dividido por esse fator. Desenho 1:1 → 1. |
| **Deslocar para X = 0?** `[n]` | `s` desloca cada seção para começar em x = 0 (a cota não muda; o deslocamento fica na aba Secoes). Não altera o FS. |
| **Camadas a usar** `[todas]` | Camadas (layers) do CAD com geometria e quantas peças cada uma tem. Escolha só as que contêm as seções para deixar de fora cotas, eixos e molduras. |
| **Como delimitar as seções** `[janela]` | `janela`: você desenha um retângulo por seção na tela (ENTER salva, BACKSPACE desfaz). `coordenadas`: digita as janelas. `auto`: sugestão por agrupamento, mostrada no desenho antes de aceitar. |

**Entidade** é cada peça desenhada: cada `LINE`, cada polilinha, arco ou spline. Uma polilinha
com 6 vértices conta como 1. Textos, cotas e hachuras são ignorados.

## Como as seções e regiões são definidas

**Seções.** Só entram numa seção as entidades **inteiras** dentro da janela; as cortadas são
avisadas. No modo `auto`, peças que se tocam (ou ficam a menos de 1 mm) formam um grupo, e cada
grupo vira uma seção. O desenho com as janelas sugeridas é exibido (ou gravado em PNG, sem tela)
antes da pergunta "Aceitar?". O auto erra quando duas seções compartilham uma linha (moldura,
eixo, linha de base): elas viram uma só. Nesse caso, use o modo `janela`.

**Regiões.** Dentro de cada seção, as linhas são cortadas em todo cruzamento, pontas e vértices
a menos de 1 mm de outra linha são encaixados, e cada área inteiramente cercada vira uma região.
O critério é geométrico, não "uma polilinha fechada = uma camada". Numeração: de cima para
baixo, e da esquerda para a direita na mesma altura.

## Saídas

- `<dxf>_secoes.xlsx`: abas LEIA-ME, **Materiais**, **Secoes**, **Regioes**, Vertices, Previas, Origem.
- `<dxf>_secoes_previas/`: um PNG por seção com as regiões numeradas.
- `<dxf>_secoes.json`: respostas e janelas da rodada (reuse com `--config`).

Nenhuma saída sobrescreve arquivos existentes.

## Validações

- **Pontas soltas:** avisa as coordenadas e desenha em vermelho tracejado na prévia.
- **Falhas de até 1 mm** (`--tol`): corrigidas automaticamente.
- **Vértice sobre linha inclinada** (T): encaixado, em vez de gerar uma região-lasca.
- **Camada contida em outra:** vira furo (anel 1+ na aba Vertices) e é avisada.
- **Partes desconectadas, vazios sem material, janelas sobrepostas, entidades cortadas, mais de 20 regiões.**
- **DXF vazio (0 bytes) e DWG:** recusados com mensagem.

## Limitações

- As janelas são dadas nos números do próprio desenho (se o desenho está em mm, a janela também).
- Não identifica o terreno nem a direção da ruptura; isso fica para o módulo 03, com o usuário.
- A tela de seleção usa o matplotlib; se a barra de zoom/pan estiver ativa, o retângulo não aparece.

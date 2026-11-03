# slide2-automacao

Automação do **Rocscience Slide2** (estabilidade de taludes por equilíbrio limite) com Python.

A ideia é automatizar as tarefas repetitivas do fluxo de projeto, sem tirar as decisões de
engenharia do usuário. O usuário continua escolhendo seções, materiais, métodos, direção de
ruptura e tipo de busca, e os scripts cuidam de transcrever, validar e montar os modelos.

> **Atenção.** O formato `.sli`/`.slim` do Slide2 não é uma API documentada; foi lido a partir de
> arquivos salvos pelo próprio programa. Abra sempre no Slide2 os modelos gerados e confira a
> geometria antes de usar qualquer resultado. Nada aqui substitui a verificação do projetista.

## Fluxo

```
 Desenho no CAD (.dxf)
        │
        ▼
 [02] cad_para_planilha.py ──► planilha-padrão (.xlsx) + prévias (.png) + respostas (.json)
        │                         └─ o usuário preenche Materiais e associa cada região
        ▼
 [03] planilha → .slim   (em desenvolvimento)
        │                         └─ perguntas no terminal: direção, métodos, superfície, busca
        ▼
 Slide2 (Compute) ──► leitura do FS por seção   (planejado)
```

## Módulos

| Pasta | O que faz | Situação |
|---|---|---|
| [`modulos/01_modelo_basico`](modulos/01_modelo_basico) | Cria um modelo `.slim` com contorno externo (boundary) e **um** material, a partir de um modelo-base | Funciona; primeiro teste |
| [`modulos/02_cad_para_planilha`](modulos/02_cad_para_planilha) | Lê um DXF, delimita as seções, fecha as regiões (camadas de solo) e gera a planilha-padrão | v0.2, testado |
| [`modulos/03_planilha_para_slim`](modulos/03_planilha_para_slim) | Lê a planilha e gera um `.slim` por seção, com várias camadas | Planejado; aguarda amostras do Slide2 |

O que vem depois está em [`docs/roadmap.md`](docs/roadmap.md). O que já se sabe do formato do
arquivo do Slide2 está em [`docs/formato_sli.md`](docs/formato_sli.md).

## Instalação

Requer Python 3.9 ou mais novo (Windows, com o Slide2 instalado para as etapas de cálculo).

```bash
git clone https://github.com/victortlacerda/slide2-automacao.git
cd slide2-automacao
pip install -r requirements.txt
```

O módulo 01 não usa bibliotecas externas.

## Uso rápido

```bash
# 01 - modelo com boundary e um material
python modulos/01_modelo_basico/slide2_editar_modelo.py

# 02 - DXF -> planilha (abre janela para escolher o arquivo e pergunta o resto no terminal)
python modulos/02_cad_para_planilha/cad_para_planilha.py
```

Cada pasta tem um README com as perguntas, opções e limitações do script.

## Testes

```bash
python testes/test_cad_para_planilha.py      # ou: pytest testes
```

Os testes geram DXFs sintéticos (seções em linhas soltas, em polilinhas, com falhas de
desenho, furos e arcos) e conferem regiões, áreas e avisos.

## Estrutura

```
modulos/            um script por etapa, cada um com README
  01_modelo_basico/   + modelo_base/vazio.slim (molde mínimo do Slide2)
  02_cad_para_planilha/
  03_planilha_para_slim/
docs/               formato do arquivo, roadmap, referências
exemplos/           arquivos de entrada para experimentar
testes/             testes automáticos e geradores de DXF de teste
```

## Referência

A abordagem de editar o arquivo texto do modelo e rodar o motor de cálculo segue
Crisp & Davies (2022), *A tool for soil nail wall design optimisation using Slide2 and Python*
(ver [`docs/referencias.md`](docs/referencias.md)).

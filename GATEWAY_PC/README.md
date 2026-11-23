# ECOTAM — Sprint 13 | Qualidade dos Dados

**Estado:** pronto para teste local. Implementação incremental sobre os Sprints 11–12: preserva simulador, gateway Windows, gravação em CSV, escrita no InfluxDB 2.x, painel em tempo real e histórico.

## Começar no Windows — sem editar código

1. **Extraia** o ZIP inteiro numa pasta nova (não copie os arquivos por cima do Sprint 12).
2. **Mantenha o servidor InfluxDB aberto** (`influxd.exe`), como você já fez nos sprints anteriores.
3. **Feche o Sprint 12 antigo**, se estiver aberto, para liberar a porta 8765.
4. Dê dois cliques em **`INICIAR_ECOTAM.bat`** nesta pasta. O navegador abrirá a tela de telemetria.
5. Na aba **Tempo real**, reconecte seu InfluxDB usando:
   - URL `http://127.0.0.1:8086`
   - Organização: a sua (anteriormente **Ecotam**)
   - Bucket: o bucket que você criou (exemplo `ecotam_telemetry`)
   - Token de API com permissão **Read e Write** para esse bucket; nunca envie o token ao chat.
6. Clique na nova aba **Qualidade** ou abra **http://127.0.0.1:8765/qualidade**.
7. Deixe o período em **Última 1 hora** e clique em **Analisar qualidade**. Para ver os dados do Sprint 11, ajuste o período para incluir as datas correspondentes.

**O InfluxDB original não é apagado, alterado nem migrado.** As telas antigas continuam disponíveis em `/` e `/historico`. O modo simulado funciona sem conectar nenhum ESP32.

## Novidades

- **Auditoria histórica:** verifica lacunas de tempo, saltos/duplicação/retrocesso de sequência, campos ausentes e valores não numéricos ou fora de limites básicos.
- **Resumo por sessão:** total de amostras, amostras com alertas, lacunas e ausências estimadas em cada sessão.
- **Índice estimado:** indicador orientativo para comparar sessões; **não** é a porcentagem de entrega do rádio.
- **Saúde do gateway:** contadores ao vivo de gravações confirmadas, falhas e descarte de fila, usando `/api/status`.
- **Exportação:** CSV da **prévia** de até 150 alertas; os contadores completos são preservados na tela.
- **Compatibilidade:** o histórico do Sprint 12 permanece intacto, incluindo comparação e exportação CSV de amostras.

## Como interpretar o resultado

- **Sem dados:** não havia registros no período selecionado, o que é normal se o gateway esteve desligado.
- **Sem dados recentes:** a última amostra é antiga. Para uma sessão já terminada, isso **não** é necessariamente uma falha.
- **Lacuna temporal:** passaram mais de 2,5 s entre registros consecutivos de uma sessão (referência do **simulador atual = 1 amostra/s**).
- **Salto de sequência:** há valores de sequência pulados. Pode indicar perda ou ausência em algum estágio; não informa sozinho qual estágio falhou.
- **Campo ausente:** valor não retornou ou não pôde ser interpretado. A análise não preenche valores ausentes inventando dados.
- **Faixa básica:** valor numericamente suspeito por critério amplo, que **não** substitui especificações ou calibração de sensores.

As consultas da aba Qualidade **não usam médias**: verificar dados já agregados mascararia lacunas e repetições. O banco pode combinar gravações com a mesma chave/timestamp, então nem toda duplicata pode ser identificada. Sessões antigas (Sprint 11) são inferidas por heurística e podem ser separadas imprecisamente. Na consulta, eventos anteriores à primeira amostra não são detectáveis.

Para consultas extensas, poderá aparecer **“Dados demais... selecione um período menor”**. Isso é proposital para não apresentar diagnósticos incorretos a partir de dados reduzidos sem aviso.

## Pastas e arquivos

| Caminho | Uso |
|---|---|
| `INICIAR_ECOTAM.bat` | Inicializa o mesmo gateway local |
| `ecotam_gateway.py` | Gateway, simulador, gravação Influx/CSV, rotas `/api/quality` |
| `ecotam_history.py` | Histórico existente, sem modificações |
| `ecotam_quality.py` | Nova auditoria dos registros brutos |
| `qualidade.html` / `qualidade.js` | Nova interface de qualidade |
| `dashboard.html` / `historico.html` | Dashboards anteriores preservados |
| `dashboard.css` | Estilos compartilhados (design system CANIDÉ, tema claro) |
| `assets/brand/` | Cópias sem edição do kit oficial CANIDÉ (logos, ícones, grafismos, fontes e licenças), servidas em `/assets/brand/` |
| `tests/test_quality.py` | Testes de qualidade e endpoints |
| `docs/software/DataQuality.md` | Documentação de projeto no padrão ECOTAM |

## Testes offline

Na pasta extraída, abra PowerShell e rode (opcional):

```powershell
& "$env:USERPROFILE\.platformio\penv\Scripts\python.exe" -m unittest discover -s tests -v
```

Ou com Python no PATH: `python -m unittest discover -s tests -v`.

Foram validados **25 testes automatizados** no ambiente de desenvolvimento, incluindo testes anteriores e o módulo novo. A consulta com o **seu** InfluxDB e a exibição no navegador Windows precisam ser validadas na sua máquina. O Sprint 13 não altera o firmware nem repara a instabilidade do ESP-NOW.

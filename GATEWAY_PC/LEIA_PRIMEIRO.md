# ECOTAM — Sprint 17.1 | Gateway com gráficos completos BME280 + GPS

**Escopo:** somente o gateway do PC. Não modifica TX, RX, firmware de rádio nem o banco de dados existente.

## Instalação no Windows

1. Feche o gateway antigo (ele usa `127.0.0.1:8765`) e o monitor serial COM3. Faça backup do diretório antigo.
2. Extraia este pacote numa pasta **nova**. Abra `GATEWAY_PC`.
3. Execute `python -m unittest discover -s tests -v` para validar o backend e `python -m pip install pyserial` se ainda não instalou pyserial neste Python.
4. Execute `INICIAR_ECOTAM.bat` ou `python ecotam_gateway.py`. Abra `http://127.0.0.1:8765`.
5. Em **Fonte de dados**, selecione **ESP32 RX por USB (COM3)** e clique **Aplicar fonte**.
6. Em **InfluxDB 2.x**, use seu endereço `http://127.0.0.1:8086`, organização, bucket e token. Não envie o token em mensagens ou prints.
7. Confirme o recebimento de pacotes V3 (84 bytes) no RX. Os gráficos evoluem automaticamente.

## O que aparece no dashboard

- **BME280:** gráficos separados de temperatura (`temperature_c`), pressão convertida Pa→hPa (`pressure_pa`), umidade (`humidity_pct`) e altitude barométrica (`altitude_m`).
- **GPS:** gráficos separados de latitude, longitude, altitude GPS, satélites, disponibilidade do fix, além de trajetória XY local (sem acesso a mapas externos).
- **Histórico:** as seis variáveis novas também podem ser selecionadas na aba **Histórico**, consultando registros antigos do InfluxDB.
- **Gateway:** contadores de amostras, RX e gravações InfluxDB; consulta Flux copiable.
- **Velocidade GPS:** não está contida no protocolo V3 atual. O painel explica a ausência; **nenhum valor é inventado**.
- **IMU e bateria:** estão nos campos legados mas não representam sensores instalados atualmente. Não são mostrados como medição física validada.

## Diagnóstico de dados ausentes

- Gráficos de umidade e localização vazios com V2 (64 bytes) são **esperados**, pois esses campos não existem no V2.
- Os dados de localização e umidade só chegam quando TX e RX estão efetivamente usando **V3 / 84 bytes**.
- Sem posição GPS (`gps_fix=false`), latitude, longitude e altitude GPS são omitidas do armazenamento. O gráfico de fix pode mostrar zero sem criar coordenadas falsas.
- O dashboard mostra até 240 amostras em memória, sem substituir o histórico no InfluxDB. Ao reiniciar o gateway os gráficos ao vivo reiniciam, mas os dados históricos no banco permanecem.
- Pressão é exibida em hPa (mas continua gravada em Pa no InfluxDB). Altitude barométrica depende da pressão de referência.

## Privacidade

O gateway só escuta em `127.0.0.1`; latitude/longitude exatas são dados sensíveis. Não exponha o dashboard, arquivos CSV ou screenshots com coordenadas publicamente.

## Testes automatizados

`python -m unittest discover -s tests -v`

Além dos testes antigos, há verificação de novos campos no endpoint `/api/status`, da inclusão das opções históricas, de estrutura do dashboard e da persistência no InfluxDB.

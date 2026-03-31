HVAC_SUPERVISOR - Entrega para maquina final

Conteudo esperado da entrega:
- HVAC_SUPERVISOR\
- HVAC_WATCHDOG\

Instalacao na maquina final:
1. Copiar as pastas HVAC_SUPERVISOR e HVAC_WATCHDOG para a maquina final, mantendo ambas no mesmo diretorio.
2. Instalar o Google Chrome, se ainda nao estiver instalado.
3. Instalar o Tesseract OCR.
4. Confirmar que o arquivo abaixo existe:
   C:\Program Files\Tesseract-OCR\tesseract.exe
5. Abrir HVAC_SUPERVISOR\HVAC_SUPERVISOR.exe
6. Abrir a pagina local de configuracao:
   http://127.0.0.1:8787
   Observacao: se a porta tiver sido alterada no config.json, usar a porta configurada.
7. Ajustar URL do dashboard, caminho do Tesseract e posicoes.
8. Testar:
   - Capturar Dashboard
   - Capturar Data/Hora
   - Salvar print Data/Hora
9. Ativar a opcao "Automacao ativa".

Comportamento operacional:
- Ao ativar a automacao, o supervisor tenta iniciar o HVAC_WATCHDOG automaticamente.
- O watchdog monitora se o HVAC_SUPERVISOR continua aberto.
- O supervisor verifica a hora do dashboard a cada ciclo.
- O supervisor salva uma imagem horaria do dashboard em saida_imagens.

Tesseract OCR:
- Site oficial: https://github.com/tesseract-ocr/tesseract
- No Windows, usar um instalador confiavel do Tesseract e manter o caminho configurado no painel.

Estrutura recomendada:
Entrega\
  HVAC_SUPERVISOR\
    HVAC_SUPERVISOR.exe
    config.json
    _internal\...
  HVAC_WATCHDOG\
    HVAC_WATCHDOG.exe
    _internal\...
  ENTREGA_README.txt

# Agendador de Desligamento (Windows)

Aplicativo simples em Python com GUI (customtkinter) para agendar o desligamento do Windows.

Funcionalidades:
- Agendar por segundos, minutos, horas.
- Agendar para um horário específico (HH:MM). Converte automaticamente para segundos.
- Cancelar agendamento (executa `shutdown -a`).
- Mostra uma contagem regressiva local (apenas visual).

Requisitos
- Windows
- Python 3.8+
- customtkinter (instalar via pip)

Instalação rápida (PowerShell):

```powershell
pip install -r requirements.txt
```

Como usar

1. Execute:

```powershell
python .\shutdown_scheduler.py
```

2. Escolha o modo (Segundos/Minutos/Horas/Horário), informe o valor e clique em "Agendar Desligamento".
3. Para cancelar um desligamento agendado, clique em "Cancelar Desligamento".

-Notas importantes
- O comando `shutdown` do Windows pode exigir privilégios de administrador para alguns cenários. Se o agendamento não funcionar, execute o terminal como Administrador.
- O app apenas chama `shutdown -s -t <segundos>` — a contagem que aparece no app é local e serve apenas como referência visual; o sistema operacional controla o desligamento.
- Este projeto é minimalista — feel free para estender (confirmação, som, agendamento recorrente etc.).

Recursos adicionais
- Você pode marcar "Agendar diariamente" quando selecionar um horário no formato HH:MM e salvar a configuração; o app registra o horário em `config.json` e, enquanto o app estiver aberto, agendará automaticamente o desligamento para a próxima ocorrência daquele horário.

- Se preferir não instalar dependências, solicite que eu adicione um fallback para `tkinter` puro (UI mais simples).

Licença
- Uso pessoal.

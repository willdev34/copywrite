# CopyWrite

Aplicação para Windows que digita um texto por você, caractere por caractere, em ritmo humano. Você cola o texto, clica em "Escreva agora" e, depois de uma contagem, o CopyWrite digita no campo que estiver ativo, em qualquer app.

Não usa copiar e colar nem a área de transferência. Cada caractere é enviado como evento real de teclado.

## Como funciona

1. Cole o texto na janela do CopyWrite.
2. Escolha a velocidade e clique em "Escreva agora".
3. A janela minimiza e uma contagem de 5 a 1 aparece no topo da tela.
4. Durante a contagem, clique no campo de destino (navegador, Word, formulário etc.).
5. Ao chegar em 1, o texto é digitado. Pressione Esc a qualquer momento para parar.

## Recursos

- Digitação via `SendInput` com `KEYEVENTF_UNICODE`: acentos, ç, símbolos e emojis.
- Keydown e keyup reais para cada caractere.
- Intervalo variável entre teclas, com pausas maiores após espaço, vírgula, ponto, interrogação e quebra de linha.
- Pausa longa ocasional, com probabilidade configurável.
- Três velocidades: lenta, normal e rápida.
- Quebra de linha com Enter ou Shift+Enter.
- Tecla de parada global (Esc por padrão), mesmo com o foco em outro app.
- Se a janela ativa mudar durante a digitação, o CopyWrite pausa e avisa. Ele continua quando você volta à janela de destino.
- Contador de caracteres e barra de progresso.

## Tecnologias

- Python 3.11+
- Tkinter
- ctypes (`user32.dll`)
- keyboard (hotkey global)
- PyInstaller

## Rodando em desenvolvimento

```bat
git clone https://github.com/willdev34/copywrite.git
cd copywrite
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Gerando o executável

```bat
build.bat
```

O arquivo sai em `dist/CopyWrite.exe`. O `config.json` fica na mesma pasta do executável e é criado na primeira execução.

## Configuração

O arquivo `config.json` aceita:

| Chave | Descrição |
|---|---|
| `speed` | `lenta`, `normal` ou `rapida` |
| `stop_key` | tecla de parada global |
| `countdown_seconds` | segundos da contagem |
| `shift_enter` | usar Shift+Enter na quebra de linha |
| `long_pause_probability` | chance de pausa longa por caractere (0 a 1) |
| `window_check_every` | caracteres entre checagens da janela ativa |
| `profiles` | intervalo base em ms de cada velocidade |

## Estrutura de pastas

```
copywrite/
  main.py          interface e fluxo geral
  typer.py         digitação com SendInput
  countdown.py     overlay da contagem
  config.py        leitura e gravação do config
  config.json      configurações
  requirements.txt
  build.bat
  README.md
  LICENSE
```

## Roadmap

- [x] Primeira versão funcional
- [x] Velocidade configurável
- [x] Tecla de parada global
- [ ] Erros de digitação com correção
- [x] Detecção de troca de janela
- [ ] Build do .exe

## Licença

MIT. Veja o arquivo [LICENSE](LICENSE).

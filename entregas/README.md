# VENDRA — pacote de acompanhamento STAGING

O download pelo GitHub foi verificado: HTTP 200 e SHA-256 idêntico ao ZIP preparado. A instalação principal permanece inalterada.

## Links

- [Baixar o pacote ZIP](https://github.com/geanprofcd/Projetos/raw/refs/heads/entregas/staging-20261014/entregas/VENDRA_STAGING_ACOMPANHAMENTO_20261014.zip)
- [Página do arquivo no GitHub](https://github.com/geanprofcd/Projetos/blob/entregas/staging-20261014/entregas/VENDRA_STAGING_ACOMPANHAMENTO_20261014.zip)
- [Estas instruções](https://github.com/geanprofcd/Projetos/blob/entregas/staging-20261014/entregas/README.md)

Todas as próximas entregas devem incluir links completos e clicáveis de download e instruções, conforme solicitado pelo usuário.

## Aplicação na cópia de testes

1. Baixe e extraia o ZIP em uma pasta separada.
2. Pare somente o servidor STAGING 8011.
3. Abra PowerShell na pasta extraída e execute:

```powershell
powershell.exe -NoProfile -File .\ATUALIZAR_COPIA_TESTES.ps1 -Aplicar
```

Siga também `LEIA_PRIMEIRO.txt`. O script limita o destino à pasta Windows `VENDRA_v0.0.4_Windows - Copia\vendra_starter`, faz backup e preserva configurações/dados. Não executa SQL nem ativa Make/WhatsApp. Os fontes passaram em 157 testes na nuvem; execução PowerShell/Windows e homologação funcional ainda pendentes. O conjunto só será promovido ao principal após homologação.

SHA-256 do ZIP: `47e037257cceed7b31652705d184c75e33e59e5ed852bfcb3516df92761fc11a`.

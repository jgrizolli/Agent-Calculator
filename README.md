# 🧮 Calculadora de Créditos & Tokens — IA da Microsoft

Calculadora estática (1 arquivo HTML) para estimar o custo **diário, semanal, mensal e anual** de:

- **Microsoft 365 Copilot** (licença por usuário)
- **Copilot Cowork** (licença + créditos por uso)
- **Copilot Studio** (agentes por Copilot Credits)
- **Microsoft Foundry** (custo por tokens, vários modelos)
- **Azure SRE Agent** (Azure Agent Units — AAUs)

Tudo em **US$ ou R$**, com preços **editáveis** e **atualização automática mensal** via GitHub Actions.

---

## 📁 Estrutura do repositório

```
.
├─ index.html                          # a calculadora (é a página do site)
├─ prices.json                         # preços atuais (gerado/atualizado pelo robô)
├─ README.md                           # este guia
├─ scripts/
│  ├─ update_prices.py                 # busca os preços e regenera o prices.json
│  └─ requirements.txt                 # dependências do script
└─ .github/workflows/
   └─ update-prices.yml                # agenda a atualização (1x por mês)
```

---

## 🧭 Como funciona (visão geral)

```
                ┌──────────────────────────────────────────┐
   1x por mês   │  GitHub Action (servidor do GitHub)        │
   (automático) │  • API de Preços do Azure  → tokens        │
                │  • Páginas da Microsoft    → AAU, créditos  │
                │  → grava o prices.json e dá commit          │
                └───────────────────┬──────────────────────┘
                                    │ (mesmo repositório)
                                    ▼
                ┌──────────────────────────────────────────┐
   Quando você  │  GitHub Pages (site estático)              │
   abre o site  │  index.html lê o prices.json (mesma pasta) │
                │  → mostra os valores já atualizados         │
                └──────────────────────────────────────────┘
```

> **Por que um robô e não a página chamando a API direto?** O navegador bloqueia (CORS)
> a leitura de APIs de outros domínios. O GitHub Action roda num **servidor**, onde não
> existe essa trava — ele busca os preços e grava num arquivo que a página lê localmente
> (mesmo domínio = sem CORS).

### O que é automático e o que não é

| Item | Fonte automática | Confiabilidade |
|------|------------------|----------------|
| Preços de **token** (GPT, o-series…) | API de Preços do Azure (JSON) | ✅ Alta |
| Taxas **AAU** (SRE Agent) | Página Microsoft Learn (raspagem) | 🟡 Boa (com fallback) |
| **Créditos** do Copilot Studio | Página Microsoft Learn (raspagem) | 🟡 Boa (com fallback) |
| Licença **M365 Copilot** / **Cowork** | Sem feed estável | ⚙️ Valor oficial fixo (edite se mudar) |

**Fallback = nunca quebra:** se uma fonte estiver fora do ar ou mudar de layout, o script
mantém o último valor oficial conhecido e marca o status em `prices.json → meta`.

---

## 💻 1) Rodar localmente

Você tem **duas formas**. As duas funcionam — escolha pela sua necessidade.

### A) Só abrir o arquivo (mais rápido)
Dê **duplo-clique** no `index.html`. Abre no navegador na hora.

> Nesse modo (`file://`), o navegador **não lê** o `prices.json` por segurança. Sem
> problemas: a calculadora usa os **valores embutidos** e você **edita Token e AAU
> manualmente** na aba **“Tabela de preços”** (as edições ficam salvas no seu navegador).
> Esse é exatamente o "campo para configurar manualmente" para uso local.

### B) Rodar um mini-servidor local (lê o prices.json)
Na pasta do projeto:

```bash
python -m http.server 8000
```

Abra **http://localhost:8000**. Agora a calculadora carrega o `prices.json` automaticamente
ao abrir (igual ao site publicado).

---

## ☁️ 2) Publicar no GitHub Pages (passo a passo)

### Passo 2.1 — Criar o repositório
1. Acesse <https://github.com/new>.
2. **Repository name:** ex. `calculadora-ia-microsoft`.
3. Visibilidade: **Public** (necessário p/ Pages no plano gratuito).
4. Clique em **Create repository**.

### Passo 2.2 — Subir os arquivos
**Opção fácil (pelo navegador):** na página do repo → **Add file → Upload files** →
arraste **todo o conteúdo desta pasta** (incluindo a pasta `.github/`) → **Commit changes**.

> ⚠️ A pasta `.github` começa com ponto e às vezes some no explorador de arquivos.
> Se ela não subir pelo navegador, use o Git (abaixo).

**Opção via Git (recomendada, garante o `.github`):**
```bash
git init
git add .
git commit -m "calculadora de IA da Microsoft"
git branch -M main
git remote add origin https://github.com/<SEU-USUARIO>/<SEU-REPO>.git
git push -u origin main
```

### Passo 2.3 — Ligar o GitHub Pages
1. No repo → **Settings → Pages**.
2. Em **Source**, escolha **Deploy from a branch**.
3. **Branch:** `main` · **Folder:** `/ (root)` → **Save**.
4. Aguarde ~1 minuto. O endereço aparece no topo:
   `https://<SEU-USUARIO>.github.io/<SEU-REPO>/`

Pronto — a calculadora está no ar, gratuita e aberta a quem você quiser compartilhar. 🎉

---

## 🤖 3) Ligar a atualização automática (1x por mês)

O arquivo `.github/workflows/update-prices.yml` já faz isso. Só falta **dar permissão de
escrita** ao robô (para ele commitar o `prices.json` novo).

### Passo 3.1 — Permitir que o Action faça commit
1. No repo → **Settings → Actions → General**.
2. Role até **Workflow permissions**.
3. Marque **Read and write permissions** → **Save**.

### Passo 3.2 — (Opcional) Testar agora, sem esperar o mês virar
1. No repo → aba **Actions**.
2. Se aparecer um aviso para habilitar workflows, clique em **I understand… enable**.
3. Clique no workflow **“Atualizar precos (mensal)”** → botão **Run workflow** → **Run**.
4. Em ~1 min ele roda, atualiza o `prices.json` e faz commit. Veja o log clicando na execução.

### Passo 3.3 — Conferir
- Abra o `prices.json` no repo: o campo `asOf` deve mostrar a data de hoje e
  `generatedBy` deve ser `github-action`.
- O bloco `meta` mostra, por fonte, se veio `live` (raspado/da API) ou `fallback` (valor oficial mantido).

> **Quando roda sozinho?** Todo **dia 1, às 03:00 (horário de Brasília)**. Para mudar a
> frequência, edite a linha `cron` no `.yml` (formato: minuto hora dia mês dia-da-semana, em UTC).
> Exemplos: `0 6 * * 1` = toda segunda; `0 6 1,15 * *` = dias 1 e 15.

---

## ✏️ Como editar valores manualmente

- **Na calculadora** (aba *Tabela de preços*): mude Token e AAU; fica salvo no seu navegador.
  Bom para “e se?” e para uso local. *(No site publicado, o `prices.json` tem prioridade ao recarregar.)*
- **No `prices.json`** (fonte da verdade do site): edite o número, dê commit. O site reflete na hora.
- **Licença M365 / Cowork:** como não há API, ajuste em `prices.json → m365` (e no `FALLBACK`
  do `scripts/update_prices.py`, para o robô não sobrescrever de volta).

---

## ❓ Solução de problemas

| Sintoma | Causa provável | Solução |
|--------|----------------|---------|
| Site abre, mas preços não atualizam | Pages ainda usando cache | Aguarde 1–2 min; force refresh (Ctrl+F5) |
| `prices.json` não muda após o Action | Permissão de escrita desligada | Settings → Actions → **Read and write permissions** |
| Action falha no `git push` | Mesmo motivo acima | idem |
| Abri local e os preços não vêm do arquivo | Aberto via `file://` | Use `python -m http.server` **ou** edite à mão |
| `meta` mostra muitos `fallback` | Página da Microsoft mudou de layout | Os valores oficiais seguem válidos; ajuste o parser em `update_prices.py` quando puder |
| Página do Pages dá 404 | Pages não publicou ainda / branch errada | Settings → Pages → branch `main`, pasta `/root` |

---

## ⚠️ Aviso

Os valores são **estimativas de referência** coletadas em jun/2026. Preços oficiais mudam —
sempre confirme nas páginas oficiais da Microsoft/Azure antes de decisões de orçamento.
Os links das fontes estão dentro da própria calculadora e no `prices.json → meta`.

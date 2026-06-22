#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera o arquivo prices.json consumido pela calculadora.

Fontes:
  1) Tokens (Azure OpenAI / Foundry) -> API pública de Preços de Varejo do Azure (JSON, confiável)
  2) Taxas AAU (SRE Agent)           -> página Microsoft Learn (HTML, raspagem)
  3) Créditos (Copilot Studio)       -> página Microsoft Learn (HTML, raspagem)
  4) Preço do crédito / licenças M365 -> melhor esforço; fallback nos valores oficiais

Filosofia: nunca quebrar. Cada fonte roda em try/except; se falhar,
mantém o valor oficial de referência (FALLBACK) e registra o status em meta[].

Uso:  python scripts/update_prices.py
Saída: prices.json (na raiz do repositório)
"""

import datetime
import json
import os
import re
import sys
import urllib.parse

import requests
from bs4 import BeautifulSoup

TODAY = datetime.date.today().isoformat()
UA = {"User-Agent": "Mozilla/5.0 (compatible; ms-ai-cost-calc/1.0; +github-actions)"}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(ROOT, "prices.json")

SRC_TOKENS = "https://azure.microsoft.com/en-us/pricing/details/ai-foundry-models/microsoft/"
SRC_AAU = "https://learn.microsoft.com/en-us/azure/sre-agent/pricing-billing"
SRC_CREDITS = "https://learn.microsoft.com/en-us/microsoft-copilot-studio/requirements-messages-management"
SRC_CREDITPRICE = "https://azure.microsoft.com/en-us/pricing/details/copilot-studio/"
SRC_M365 = "https://www.microsoft.com/en-us/microsoft-365-copilot/pricing"

# ---------------------------------------------------------------------------
# Valores OFICIAIS de referência (jun/2026) — usados como fallback seguro
# ---------------------------------------------------------------------------
FALLBACK = {
    "creditPrice": 0.01,
    "capacityPack": {"usd": 200, "credits": 25000},
    "sreAlwaysOn": 4,
    "m365": {"enterprise": 30, "business": 18},
    "models": [
        {"id": "gpt55",   "name": "GPT-5.5",          "in": 5.00,  "cached": 0.50,  "out": 30.00},
        {"id": "gpt54",   "name": "GPT-5.4",          "in": 2.50,  "cached": 0.25,  "out": 15.00},
        {"id": "gpt54m",  "name": "GPT-5.4 mini",     "in": 0.75,  "cached": 0.08,  "out": 4.50},
        {"id": "gpt54n",  "name": "GPT-5.4 nano",     "in": 0.20,  "cached": 0.02,  "out": 1.25},
        {"id": "gpt5",    "name": "GPT-5",            "in": 1.25,  "cached": 0.125, "out": 10.00},
        {"id": "gpt5m",   "name": "GPT-5 mini",       "in": 0.25,  "cached": 0.025, "out": 2.00},
        {"id": "gpt5n",   "name": "GPT-5 nano",       "in": 0.05,  "cached": 0.005, "out": 0.40},
        {"id": "gpt41",   "name": "GPT-4.1",          "in": 2.00,  "cached": 0.50,  "out": 8.00},
        {"id": "gpt41m",  "name": "GPT-4.1 mini",     "in": 0.40,  "cached": 0.10,  "out": 1.60},
        {"id": "gpt41n",  "name": "GPT-4.1 nano",     "in": 0.10,  "cached": 0.025, "out": 0.40},
        {"id": "gpt4o",   "name": "GPT-4o",           "in": 2.50,  "cached": 1.25,  "out": 10.00},
        {"id": "gpt4om",  "name": "GPT-4o mini",      "in": 0.15,  "cached": 0.075, "out": 0.60},
        {"id": "o3",      "name": "o3",               "in": 2.00,  "cached": 0.50,  "out": 8.00},
        {"id": "o4m",     "name": "o4-mini",          "in": 1.10,  "cached": 0.275, "out": 4.40},
        {"id": "o3m",     "name": "o3-mini",          "in": 1.10,  "cached": 0.55,  "out": 4.40},
        {"id": "o1",      "name": "o1",               "in": 15.00, "cached": 7.50,  "out": 60.00},
        {"id": "maidsr1", "name": "MAI-DS-R1",        "in": 1.35,  "cached": 0.135, "out": 5.40},
        {"id": "dsv32",   "name": "DeepSeek V3.2",    "in": 0.27,  "cached": 0.027, "out": 1.10},
        {"id": "dsr1",    "name": "DeepSeek R1",      "in": 0.55,  "cached": 0.14,  "out": 2.19},
        {"id": "llama8b", "name": "Llama 3.1 8B",     "in": 0.02,  "cached": 0.02,  "out": 0.05},
        {"id": "mists",   "name": "Mistral Small 3.1","in": 0.10,  "cached": 0.10,  "out": 0.30},
        {"id": "phi4",    "name": "Phi-4",            "in": 0.125, "cached": 0.125, "out": 0.50},
        {"id": "phi4m",   "name": "Phi-4 mini",       "in": 0.075, "cached": 0.075, "out": 0.30},
    ],
    "aauRates": {
        "opus46": {"in": 100, "out": 500, "cr": 10,  "cw": 125},
        "gpt53":  {"in": 35,  "out": 280, "cr": 3.5, "cw": 0},
        "gpt52":  {"in": 35,  "out": 280, "cr": 3.5, "cw": 0},
    },
    "studioFeatures": [
        {"id": "classic",   "credit": 1},
        {"id": "genative",  "credit": 2},
        {"id": "action",    "credit": 5},
        {"id": "grounding", "credit": 10},
        {"id": "flow",      "credit": 13},
        {"id": "toolb",     "credit": 1},
        {"id": "tools",     "credit": 15},
        {"id": "toolp",     "credit": 100},
        {"id": "content",   "credit": 8},
    ],
}

# Mapeia o nome do medidor do Azure -> id do modelo na calculadora.
# Ordem importa: os mais específicos (mini/nano) vêm antes dos genéricos.
TOKEN_PATTERNS = [
    ("gpt55",  r"gpt[\s-]?5\.5"),
    ("gpt54m", r"gpt[\s-]?5\.4.*mini"),
    ("gpt54n", r"gpt[\s-]?5\.4.*nano"),
    ("gpt54",  r"gpt[\s-]?5\.4"),
    ("gpt5m",  r"gpt[\s-]?5(?![.\d]).*mini"),
    ("gpt5n",  r"gpt[\s-]?5(?![.\d]).*nano"),
    ("gpt5",   r"gpt[\s-]?5(?![.\d])"),
    ("gpt41m", r"gpt[\s-]?4\.1.*mini"),
    ("gpt41n", r"gpt[\s-]?4\.1.*nano"),
    ("gpt41",  r"gpt[\s-]?4\.1"),
    ("gpt4om", r"gpt[\s-]?4o.*mini"),
    ("gpt4o",  r"gpt[\s-]?4o"),
    ("o4m",    r"\bo4[\s-]?mini"),
    ("o3m",    r"\bo3[\s-]?mini"),
    ("o3",     r"\bo3\b"),
    ("o1",     r"\bo1\b"),
]


def http_get(url, **kw):
    r = requests.get(url, headers=UA, timeout=40, **kw)
    r.raise_for_status()
    return r


# ---------------------------------------------------------------------------
# 1) Tokens — API de Preços de Varejo do Azure
# ---------------------------------------------------------------------------
def _per_million(price, uom):
    u = (uom or "").lower()
    if "1k" in u or "1,000" in u or "1000" in u:
        return price * 1000.0
    return price


def _component(meter):
    m = meter.lower()
    if "cache" in m:
        return "cached"
    if "output" in m or re.search(r"\boutp", m):
        return "out"
    if "input" in m or re.search(r"\binp", m):
        return "in"
    return "in"


def _match_model_id(meter):
    m = meter.lower()
    for mid, pat in TOKEN_PATTERNS:
        if re.search(pat, m):
            return mid
    return None


# Nomes de servico candidatos onde os precos de token podem estar.
# A Microsoft ja hospedou os medidores do Azure OpenAI sob nomes diferentes,
# entao tentamos varios e usamos o primeiro que retornar medidores de token.
SERVICE_CANDIDATES = ["Azure OpenAI", "Cognitive Services", "Azure AI Foundry"]


def _scope_rank(meter):
    """Prioriza precos 'Global' sobre 'Regional'/'Data Zone'."""
    m = meter.lower()
    if "glbl" in m or "global" in m:
        return 2
    if "regional" in m or "data zone" in m or "-dz" in m or " dz" in m:
        return 0
    return 1


def _fetch_service(sname):
    base = "https://prices.azure.com/api/retail/prices"
    flt = "serviceName eq '{}' and priceType eq 'Consumption'".format(sname.replace("'", "''"))
    url = base + "?" + urllib.parse.urlencode({
        "api-version": "2023-01-01-preview",
        "currencyCode": "USD",
        "$filter": flt,
    })
    items, pages = [], 0
    while url and pages < 60:
        data = http_get(url).json()
        items.extend(data.get("Items", []))
        url = data.get("NextPageLink")
        pages += 1
    return items


def _is_token_meter(it):
    """Reconhece medidores de token (unidade '1K', '1M', 'Tokens'...),
    excluindo cobranças por hora/imagem."""
    uom = (it.get("unitOfMeasure") or "").lower()
    if "hour" in uom or "image" in uom or "/hr" in uom:
        return False
    return ("token" in uom or "1k" in uom or "1m" in uom
            or "1,000" in uom or "1000" in uom)


def fetch_tokens():
    chosen, used, total = [], [], 0
    for sname in SERVICE_CANDIDATES:
        try:
            got = _fetch_service(sname)
        except Exception as exc:
            used.append("{}: erro {}".format(sname, exc))
            continue
        toks = [it for it in got
                if _is_token_meter(it) and _match_model_id(it.get("meterName") or "")]
        used.append("{}: {} itens, {} token-modelo".format(sname, len(got), len(toks)))
        if toks:
            chosen, total = toks, len(got)
            break  # achamos onde estao os tokens

    # mid -> comp -> (rank, price): mantem o de maior prioridade (global)
    ranked = {}
    for it in chosen:
        meter = it.get("meterName") or ""
        mid = _match_model_id(meter)
        if not mid:
            continue
        comp = _component(meter)
        per1m = round(_per_million(it.get("retailPrice") or 0, it.get("unitOfMeasure")), 4)
        rank = _scope_rank(meter)
        cur = ranked.setdefault(mid, {}).get(comp)
        if cur is None or rank > cur[0]:
            ranked[mid][comp] = (rank, per1m)

    found = {mid: {c: v[1] for c, v in comps.items()} for mid, comps in ranked.items()}
    return found, total, used


# ---------------------------------------------------------------------------
# 2) Taxas AAU — página do SRE Agent
# ---------------------------------------------------------------------------
def _num(text):
    m = re.search(r"(\d+(?:\.\d+)?)", text or "")
    return float(m.group(1)) if m else None


def fetch_aau():
    html = http_get(SRC_AAU).text
    soup = BeautifulSoup(html, "html.parser")
    rates = {}
    always_on = None

    for table in soup.find_all("table"):
        header = " ".join(th.get_text(" ", strip=True).lower()
                          for th in table.find_all("th"))
        if "cache read" in header and "cache write" in header:
            for tr in table.find_all("tr"):
                cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
                if len(cells) < 5:
                    continue
                name = cells[0].lower()
                if "opus" in name:
                    key = "opus46"
                elif "5.3" in name or "codex" in name:
                    key = "gpt53"
                elif "5.2" in name:
                    key = "gpt52"
                else:
                    continue
                vals = [_num(c) for c in cells[1:5]]
                if None in vals:
                    continue
                rates[key] = {"in": vals[0], "out": vals[1], "cr": vals[2], "cw": vals[3]}
            break

    m = re.search(r"(\d+(?:\.\d+)?)\s*AAUs?\s*per\s*agent-hour", html, re.I)
    if m:
        always_on = float(m.group(1))

    return rates, always_on


# ---------------------------------------------------------------------------
# 3) Créditos — página de billing do Copilot Studio
# ---------------------------------------------------------------------------
CREDIT_PATTERNS = {
    "classic":   r"classic answer[\s\S]{0,40}?(\d+(?:\.\d+)?)\s*copilot credit",
    "genative":  r"generative answer[\s\S]{0,40}?(\d+(?:\.\d+)?)\s*copilot credit",
    "action":    r"agent action[\s\S]{0,40}?(\d+(?:\.\d+)?)\s*copilot credit",
    "grounding": r"grounding[\s\S]{0,60}?(\d+(?:\.\d+)?)\s*copilot credit",
    "content":   r"content processing tools per page[\s\S]{0,40}?(\d+(?:\.\d+)?)\s*copilot credit",
}


def fetch_credits():
    text = http_get(SRC_CREDITS).text
    soup = BeautifulSoup(text, "html.parser")
    flat = soup.get_text(" ", strip=True).lower()
    out = {}
    for fid, pat in CREDIT_PATTERNS.items():
        m = re.search(pat, flat)
        if m:
            out[fid] = float(m.group(1))
    return out


# ---------------------------------------------------------------------------
# 4) Preço do crédito (melhor esforço)
# ---------------------------------------------------------------------------
def fetch_credit_price():
    text = http_get(SRC_CREDITPRICE).text.lower()
    if re.search(r"\$\s*0\.01", text) or "0.01" in text:
        return 0.01
    return None


# ---------------------------------------------------------------------------
# Orquestra tudo
# ---------------------------------------------------------------------------
def main():
    out = json.loads(json.dumps(FALLBACK))  # cópia profunda
    meta = {}

    # 1) tokens
    try:
        found, meters, used = fetch_tokens()
        applied = 0
        for m in out["models"]:
            f = found.get(m["id"])
            if not f:
                continue
            for k in ("in", "cached", "out"):
                if f.get(k) is not None:
                    m[k] = f[k]
            applied += 1
        meta["tokens"] = {
            "status": "live" if applied else "fallback",
            "matched": applied, "meters": meters, "services": used,
            "source": SRC_TOKENS, "asOf": TODAY,
        }
    except Exception as exc:
        meta["tokens"] = {"status": "fallback", "error": str(exc), "source": SRC_TOKENS, "asOf": TODAY}

    # 2) AAU
    try:
        rates, always_on = fetch_aau()
        if rates:
            for k, v in rates.items():
                out["aauRates"].setdefault(k, {}).update(v)
        if always_on:
            out["sreAlwaysOn"] = always_on
        meta["aau"] = {
            "status": "live" if rates else "fallback",
            "models": list(rates.keys()), "source": SRC_AAU, "asOf": TODAY,
        }
    except Exception as exc:
        meta["aau"] = {"status": "fallback", "error": str(exc), "source": SRC_AAU, "asOf": TODAY}

    # 3) créditos (Studio)
    try:
        credits = fetch_credits()
        if credits:
            for f in out["studioFeatures"]:
                if f["id"] in credits:
                    f["credit"] = credits[f["id"]]
        meta["credits"] = {
            "status": "live" if credits else "fallback",
            "fields": list(credits.keys()), "source": SRC_CREDITS, "asOf": TODAY,
        }
    except Exception as exc:
        meta["credits"] = {"status": "fallback", "error": str(exc), "source": SRC_CREDITS, "asOf": TODAY}

    # 4) preço do crédito
    try:
        cp = fetch_credit_price()
        if cp:
            out["creditPrice"] = cp
            meta["creditPrice"] = {"status": "live", "value": cp, "source": SRC_CREDITPRICE, "asOf": TODAY}
        else:
            meta["creditPrice"] = {"status": "fallback", "source": SRC_CREDITPRICE, "asOf": TODAY}
    except Exception as exc:
        meta["creditPrice"] = {"status": "fallback", "error": str(exc), "source": SRC_CREDITPRICE, "asOf": TODAY}

    # M365: sem feed programático estável -> mantém fallback oficial
    meta["m365"] = {"status": "fallback", "source": SRC_M365, "asOf": TODAY,
                    "note": "Pagina de marketing (JS); valores oficiais mantidos. Edite aqui se a Microsoft alterar."}

    out["asOf"] = TODAY
    out["generatedBy"] = "github-action"
    out["currency"] = "USD"
    out["meta"] = meta

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("prices.json gerado em", OUT_PATH)
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # nunca derruba o workflow
        print("ERRO geral:", exc, file=sys.stderr)
        sys.exit(0)

"""Comparação de duas buscas lexicais sobre documentos fictícios."""

import json
import re
import unicodedata
from pathlib import Path

DADOS = Path(__file__).resolve().parent / "dados"
COMUNS = {"qual", "quais", "e", "o", "a", "de", "do", "da", "em", "com", "quando", "como"}
EQUIVALENCIAS = {"comeca": "inicio", "cancelar": "rescisao", "pagar": "pagamento"}


def carregar(nome):
    return json.loads((DADOS / nome).read_text(encoding="utf-8"))


def termos(texto, expandir=False):
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    encontrados = set(re.findall(r"[a-z0-9]+", texto)) - COMUNS
    return {EQUIVALENCIAS.get(t, t) if expandir else t for t in encontrados}


def buscar(pergunta, expandir=False, documentos=None):
    documentos = carregar("documentos.json") if documentos is None else documentos
    consulta = termos(pergunta, expandir)
    pontuados = [(len(consulta & termos(doc["texto"], expandir)), doc)
                  for doc in documentos]
    pontuados.sort(key=lambda item: (-item[0], item[1]["id"]))
    return pontuados[0][1] if pontuados and pontuados[0][0] else None


def avaliar(perguntas=None):
    perguntas = carregar("perguntas.json") if perguntas is None else perguntas
    return {metodo: [
        {"pergunta": p["pergunta"], "esperado": p["esperado"],
         "obtido": (resultado or {}).get("id"),
         "acertou": (resultado or {}).get("id") == p["esperado"]}
        for p in perguntas
        for resultado in [buscar(p["pergunta"], expandir=expandir)]
    ] for metodo, expandir in (("literal", False), ("equivalencias", True))}


if __name__ == "__main__":
    for metodo, resultados in avaliar().items():
        acertos = sum(item["acertou"] for item in resultados)
        print(f"{metodo}: {acertos}/{len(resultados)}")
        for item in resultados:
            print(f"  {item['pergunta']}: {item['obtido'] or 'sem resultado'} (esperado: {item['esperado']})")

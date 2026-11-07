"""Demonstração: cria um ERP fictício, faz a carga inicial no DW e roda o espelho minuto a minuto (acelerado),
com o ERP mudando entre as rodadas. No fim, simula o ERP devolvendo a consulta vazia para mostrar a trava.

Uso: python -m espelho [--rodadas 6] [--intervalo 1.5] [--pasta saida]
"""
import argparse
import os
import random
import sqlite3
import time
from pathlib import Path

from demo import erp_ficticio

from .digital import TravaAcionada
from .motor import Tabela, rodada

TITULOS = Tabela(origem="titulos_pagar", destino="dw_titulos_pagar", chave="id",
                 colunas=("id", "fornecedor", "documento", "valor", "vencimento", "status"))
VERDE, AMARELO, VERMELHO, CINZA, FIM = "\033[32m", "\033[33m", "\033[31m", "\033[90m", "\033[0m"


def main():
    if os.name == "nt":
        os.system("")  # liga as cores ANSI no console do Windows
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rodadas", type=int, default=6)
    ap.add_argument("--intervalo", type=float, default=1.5, help="segundos entre rodadas (na vida real, 60)")
    ap.add_argument("--pasta", default="saida")
    args = ap.parse_args()

    pasta = Path(args.pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    for banco in ("erp.db", "dw.db"):
        (pasta / banco).unlink(missing_ok=True)
    erp = erp_ficticio.criar(pasta / "erp.db")
    dw = sqlite3.connect(pasta / "dw.db")
    rnd = random.Random(7)

    print(f"{CINZA}ERP fictício: {erp.execute('SELECT COUNT(*) FROM titulos_pagar').fetchone()[0]} títulos a pagar{FIM}")
    for n in range(1, args.rodadas + 1):
        if n > 1:
            feito = erp_ficticio.mexer(erp, rnd)
            print(f"{CINZA}  ERP: {feito['novos']} lançados, {feito['baixas']} baixados, "
                  f"{feito['exclusoes']} excluídos{FIM}")
        t0 = time.perf_counter()
        dif = rodada(erp, dw, TITULOS)
        ms = (time.perf_counter() - t0) * 1000
        cor = VERDE if dif.total else CINZA
        texto = dif.resumo() if dif.total else "nada mudou (não grava log)"
        print(f"{cor}rodada {n}: {texto} em {ms:.0f} ms{FIM}")
        time.sleep(args.intervalo)

    print(f"\n{AMARELO}Simulando o ERP fora do ar: a view volta vazia...{FIM}")
    erp.execute("ALTER TABLE titulos_pagar RENAME TO titulos_pagar_real")
    erp.execute("CREATE TABLE titulos_pagar AS SELECT * FROM titulos_pagar_real WHERE 0")
    try:
        rodada(erp, dw, TITULOS)
    except TravaAcionada as erro:
        print(f"{VERMELHO}trava acionada: {erro}{FIM}")
    total = dw.execute(f"SELECT COUNT(*) FROM {TITULOS.destino}").fetchone()[0]
    print(f"{VERDE}o DW continua com {total} títulos; o painel não ficou zerado{FIM}")
    print(f"{CINZA}log das cargas em {pasta / 'dw.db'} (tabela carga_log){FIM}")


if __name__ == "__main__":
    main()

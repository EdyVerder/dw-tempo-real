"""Uma rodada do espelho: lê as impressões digitais da origem e do destino, aplica só a diferença numa transação
e registra no log apenas quando algo mudou."""
import datetime as dt
import time
from dataclasses import dataclass

from .digital import comparar, conferir_travas, digital, em_lotes


@dataclass(frozen=True)
class Tabela:
    origem: str          # tabela ou view no ERP
    destino: str         # tabela espelho no DW
    chave: str
    colunas: tuple       # colunas copiadas (a chave incluída)

    @property
    def colunas_digital(self):
        return [c for c in self.colunas if c != self.chave]


def preparar_destino(dw, t):
    cols = ", ".join(f'"{c}"' for c in t.colunas)
    dw.execute(f'CREATE TABLE IF NOT EXISTS "{t.destino}" ({cols}, _digital TEXT NOT NULL, '
               f'_atualizado_em TEXT NOT NULL, PRIMARY KEY ("{t.chave}"))')
    dw.execute("CREATE TABLE IF NOT EXISTS carga_log (id INTEGER PRIMARY KEY, tabela TEXT, inicio TEXT, "
               "duracao_ms INTEGER, novas INTEGER, alteradas INTEGER, removidas INTEGER, situacao TEXT, detalhe TEXT)")


def digitais_origem(erp, t):
    cols = ", ".join(f'"{c}"' for c in t.colunas)
    cur = erp.execute(f'SELECT {cols} FROM "{t.origem}"')
    nomes = [d[0] for d in cur.description]
    linhas = {}
    for valores in cur:
        linha = dict(zip(nomes, valores))
        linhas[linha[t.chave]] = linha
    return {k: digital(v, t.colunas_digital) for k, v in linhas.items()}, linhas


def digitais_destino(dw, t):
    return dict(dw.execute(f'SELECT "{t.chave}", _digital FROM "{t.destino}"'))


def registrar(dw, t, inicio, ms, dif, situacao, detalhe=""):
    dw.execute("INSERT INTO carga_log (tabela, inicio, duracao_ms, novas, alteradas, removidas, situacao, detalhe) "
               "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
               (t.destino, inicio, ms, len(dif.novas), len(dif.alteradas), len(dif.removidas), situacao, detalhe))


def rodada(erp, dw, t, agora=None):
    """Executa uma rodada e devolve as diferenças aplicadas. Levanta TravaAcionada sem gravar nada."""
    inicio = (agora or dt.datetime.now()).isoformat(timespec="seconds")
    t0 = time.perf_counter()
    preparar_destino(dw, t)
    origem, linhas = digitais_origem(erp, t)
    destino = digitais_destino(dw, t)
    dif = comparar(origem, destino)
    try:
        conferir_travas(len(origem), len(destino), dif)
    except Exception as erro:
        with dw:
            registrar(dw, t, inicio, int((time.perf_counter() - t0) * 1000), dif, "PARADO", str(erro))
        raise
    if not dif.total:
        return dif
    cols = ", ".join(f'"{c}"' for c in t.colunas)
    marcas = ", ".join("?" for _ in t.colunas)
    with dw:  # tudo ou nada: o Excel/BI nunca lê o espelho pela metade
        for lote in em_lotes(dif.removidas):
            dw.execute(f'DELETE FROM "{t.destino}" WHERE "{t.chave}" IN ({", ".join("?" for _ in lote)})', lote)
        for chave in dif.novas + dif.alteradas:
            linha = linhas[chave]
            dw.execute(f'INSERT OR REPLACE INTO "{t.destino}" ({cols}, _digital, _atualizado_em) '
                       f'VALUES ({marcas}, ?, ?)', [linha[c] for c in t.colunas] + [origem[chave], inicio])
        registrar(dw, t, inicio, int((time.perf_counter() - t0) * 1000), dif, "OK")
    return dif

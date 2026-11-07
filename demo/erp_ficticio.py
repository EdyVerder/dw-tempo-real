"""ERP de mentira para a demonstração: títulos a pagar de fornecedores fictícios e um simulador que, a cada
rodada, faz o que o financeiro faria (lança, baixa, corrige e exclui títulos)."""
import datetime as dt
import random
import sqlite3

FORNECEDORES = [f"Fornecedor Demonstração {i:03d}" for i in range(1, 41)]
STATUS = ["EM ABERTO", "EM ABERTO", "EM ABERTO", "BAIXADO", "CANCELADO"]


def criar(caminho, linhas=5000, semente=42):
    rnd = random.Random(semente)
    con = sqlite3.connect(caminho)
    con.execute("DROP TABLE IF EXISTS titulos_pagar")
    con.execute("CREATE TABLE titulos_pagar (id INTEGER PRIMARY KEY, fornecedor TEXT, documento TEXT, "
                "valor REAL, vencimento TEXT, status TEXT)")
    base = dt.date(2026, 1, 1)
    con.executemany("INSERT INTO titulos_pagar VALUES (?, ?, ?, ?, ?, ?)", [
        (i, rnd.choice(FORNECEDORES), f"NF {rnd.randint(1000, 99999)}", round(rnd.uniform(150, 48000), 2),
         (base + dt.timedelta(days=rnd.randint(0, 330))).isoformat(), rnd.choice(STATUS))
        for i in range(1, linhas + 1)])
    con.commit()
    return con


def mexer(con, rnd):
    """Simula um minuto de uso do ERP. Devolve o que foi feito, para conferir com o espelho."""
    proximo = con.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM titulos_pagar").fetchone()[0]
    ids = [r[0] for r in con.execute("SELECT id FROM titulos_pagar WHERE status = 'EM ABERTO'")]
    novos = rnd.randint(0, 6)
    baixas = rnd.sample(ids, min(len(ids), rnd.randint(0, 8)))
    exclusoes = rnd.sample([i for i in ids if i not in baixas], min(len(ids), rnd.randint(0, 2)))
    with con:
        for i in range(novos):
            con.execute("INSERT INTO titulos_pagar VALUES (?, ?, ?, ?, ?, 'EM ABERTO')",
                        (proximo + i, rnd.choice(FORNECEDORES), f"NF {rnd.randint(1000, 99999)}",
                         round(rnd.uniform(150, 48000), 2), dt.date(2026, 12, rnd.randint(1, 28)).isoformat()))
        con.executemany("UPDATE titulos_pagar SET status = 'BAIXADO' WHERE id = ?", [(i,) for i in baixas])
        con.executemany("DELETE FROM titulos_pagar WHERE id = ?", [(i,) for i in exclusoes])
    return {"novos": novos, "baixas": len(baixas), "exclusoes": len(exclusoes)}

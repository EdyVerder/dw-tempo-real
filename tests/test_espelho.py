import random
import sqlite3

import pytest

from demo import erp_ficticio
from espelho import Diferencas, Tabela, TravaAcionada, comparar, conferir_travas, digital, rodada

T = Tabela(origem="titulos_pagar", destino="dw_titulos_pagar", chave="id",
           colunas=("id", "fornecedor", "documento", "valor", "vencimento", "status"))


def test_digital_muda_quando_uma_coluna_muda():
    linha = {"id": 1, "valor": 10.0, "status": "EM ABERTO"}
    outra = dict(linha, status="BAIXADO")
    assert digital(linha, ["valor", "status"]) != digital(outra, ["valor", "status"])
    assert digital(linha, ["valor", "status"]) == digital(dict(linha), ["valor", "status"])


def test_digital_diferencia_nulo_de_texto_vazio_entre_colunas():
    assert digital({"a": "x", "b": None}, ["a", "b"]) != digital({"a": None, "b": "x"}, ["a", "b"])


def test_comparar():
    dif = comparar({1: "a", 2: "b", 3: "c"}, {2: "b", 3: "x", 4: "d"})
    assert (dif.novas, dif.alteradas, dif.removidas) == ([1], [3], [4])
    assert dif.total == 3


def test_trava_origem_encolhida():
    with pytest.raises(TravaAcionada):
        conferir_travas(10, 100, Diferencas())


def test_trava_remocoes_demais():
    with pytest.raises(TravaAcionada):
        conferir_travas(95, 100, Diferencas(removidas=list(range(40))))


def test_destino_vazio_nao_trava():
    conferir_travas(5000, 0, Diferencas(novas=list(range(5000))))


def test_espelho_fica_igual_ao_erp_rodada_apos_rodada(tmp_path):
    erp = erp_ficticio.criar(tmp_path / "erp.db", linhas=800)
    dw = sqlite3.connect(tmp_path / "dw.db")
    assert len(rodada(erp, dw, T).novas) == 800
    rnd = random.Random(1)
    for _ in range(10):
        erp_ficticio.mexer(erp, rnd)
        rodada(erp, dw, T)
        origem = sorted(erp.execute("SELECT * FROM titulos_pagar"))
        espelho = sorted(dw.execute(f"SELECT {', '.join(T.colunas)} FROM dw_titulos_pagar"))
        assert origem == espelho
    assert rodada(erp, dw, T).total == 0


def test_log_so_quando_muda(tmp_path):
    erp = erp_ficticio.criar(tmp_path / "erp.db", linhas=50)
    dw = sqlite3.connect(tmp_path / "dw.db")
    rodada(erp, dw, T)
    rodada(erp, dw, T)
    assert dw.execute("SELECT COUNT(*) FROM carga_log").fetchone()[0] == 1


def test_trava_nao_mexe_no_destino(tmp_path):
    erp = erp_ficticio.criar(tmp_path / "erp.db", linhas=300)
    dw = sqlite3.connect(tmp_path / "dw.db")
    rodada(erp, dw, T)
    erp.execute("DELETE FROM titulos_pagar")
    erp.commit()
    with pytest.raises(TravaAcionada):
        rodada(erp, dw, T)
    assert dw.execute("SELECT COUNT(*) FROM dw_titulos_pagar").fetchone()[0] == 300
    assert dw.execute("SELECT situacao FROM carga_log ORDER BY id DESC").fetchone()[0] == "PARADO"

"""Funções puras do espelho: impressão digital das linhas, diferenças entre origem e destino e as travas.

Nada aqui toca banco, então tudo é testado sem conexão.
"""
import hashlib
from dataclasses import dataclass, field


def digital(linha, colunas):
    """Impressão digital de uma linha: hash curto das colunas que importam (muda se qualquer uma mudar)."""
    texto = "\x1f".join("" if linha[c] is None else str(linha[c]) for c in colunas)
    return hashlib.blake2b(texto.encode("utf-8"), digest_size=8).hexdigest()


@dataclass
class Diferencas:
    novas: list = field(default_factory=list)
    alteradas: list = field(default_factory=list)
    removidas: list = field(default_factory=list)

    @property
    def total(self):
        return len(self.novas) + len(self.alteradas) + len(self.removidas)

    def resumo(self):
        return f"{len(self.novas)} novas, {len(self.alteradas)} alteradas, {len(self.removidas)} removidas"


def comparar(origem, destino):
    """Compara {chave: digital} da origem com o do destino e diz o que inserir, atualizar e apagar."""
    dif = Diferencas()
    for chave, dig in origem.items():
        atual = destino.get(chave)
        if atual is None:
            dif.novas.append(chave)
        elif atual != dig:
            dif.alteradas.append(chave)
    dif.removidas = [chave for chave in destino if chave not in origem]
    return dif


class TravaAcionada(Exception):
    """A rodada foi interrompida antes de gravar: o destino continua como estava."""


def conferir_travas(qtd_origem, qtd_destino, dif, proporcao_minima=0.7, limite_remocoes=0.3):
    """Protege o DW contra leituras ruins da origem (ERP fora do ar, consulta vazia, filtro errado).

    - a origem não pode ter encolhido abaixo de `proporcao_minima` do que o destino tem;
    - uma única rodada não pode apagar mais que `limite_remocoes` do destino.
    """
    if qtd_destino == 0:
        return
    if qtd_origem < qtd_destino * proporcao_minima:
        raise TravaAcionada(f"origem com {qtd_origem} linhas contra {qtd_destino} no destino "
                            f"(abaixo de {proporcao_minima:.0%}); nada foi gravado")
    if len(dif.removidas) > qtd_destino * limite_remocoes:
        raise TravaAcionada(f"{len(dif.removidas)} remoções numa rodada (limite {limite_remocoes:.0%} de "
                            f"{qtd_destino}); nada foi gravado")


def em_lotes(itens, tamanho=500):
    """Divide a lista em lotes (o IN do SQL tem limite de parâmetros)."""
    for i in range(0, len(itens), tamanho):
        yield itens[i:i + tamanho]

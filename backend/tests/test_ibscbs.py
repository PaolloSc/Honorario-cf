"""Bloco IBS/CBS conforme a orientacao do contador (12/11/2026): regime, data e tomador."""
from datetime import date, datetime, timedelta, timezone

import pytest
from lxml import etree

from app.services.emissao import _bloco_ibscbs
from app.services.ibscbs import resolver
from tests.test_nfse_dps_smoke import NS_DPS, _params, schema  # noqa: F401  (schema e' fixture)
from workers.nfse_dps_smoke.dps import montar_dps

FIM_2026, INICIO_2027 = date(2026, 12, 31), date(2027, 1, 1)


@pytest.mark.parametrize("regime", ["2", "3"])
def test_simples_em_2026_sai_sem_bloco_mesmo_com_servico_configurado(regime):
    b = resolver(regime, FIM_2026, incluir_config=True, c_ind_op="100301", cst="000", c_class_trib="000001")
    assert b.incluir is False


@pytest.mark.parametrize("regime", ["2", "3"])
def test_simples_a_partir_de_2027_sai_200_200052_ignorando_a_config_do_servico(regime):
    b = resolver(regime, INICIO_2027, incluir_config=False, cst="000", c_class_trib="000001")
    assert (b.incluir, b.c_ind_op, b.cst, b.c_class_trib) == (True, "100301", "200", "200052")


def test_tomador_no_exterior_em_2027_e_410_410004_e_antes_de_2027_sem_bloco():
    b = resolver("3", INICIO_2027, exterior=True)
    assert (b.incluir, b.cst, b.c_class_trib) == (True, "410", "410004")
    assert resolver("3", FIM_2026, exterior=True).incluir is False


def test_regime_nao_orientado_segue_a_configuracao_do_servico():
    assert resolver("1", FIM_2026, incluir_config=False).incluir is False
    b = resolver("1", FIM_2026, incluir_config=True)
    assert (b.cst, b.c_class_trib, b.c_ind_op) == ("000", "000001", "100301")
    b = resolver("1", INICIO_2027, incluir_config=True, cst="200", c_class_trib="200052", c_ind_op="100301")
    assert (b.cst, b.c_class_trib) == ("200", "200052")


def test_a_data_e_a_de_brasilia_na_virada_do_ano():
    srv = {"emissor": {"op_simp_nac": "3"}, "incluir_ibscbs": False, "c_ind_op": None, "cst_ibscbs": None,
           "c_class_trib": None}
    utc = timezone.utc
    assert _bloco_ibscbs({}, srv, datetime(2027, 1, 1, 1, 0, tzinfo=utc)).incluir is False  # 31/12 22h em Brasilia
    assert _bloco_ibscbs({}, srv, datetime(2027, 1, 1, 4, 0, tzinfo=utc)).incluir is True   # 01/01 01h em Brasilia


@pytest.mark.parametrize("cst,cc", [("200", "200052"), ("410", "410004")])
def test_blocos_de_2027_validam_no_xsd_oficial(schema, cst, cc):  # noqa: F811
    brt = timezone(timedelta(hours=-3))
    raiz = etree.fromstring(montar_dps(_params(
        cst=cst, c_class_trib=cc, c_ind_op="100301", ibscbs=True, nbs="113019000",
        tomador_end={"cMun": "3106200", "CEP": "30130000", "xLgr": "Av X", "nro": "1", "xBairro": "Centro"},
        agora=datetime(2027, 1, 5, 10, 0, tzinfo=brt))))
    schema.assertValid(raiz)
    trib = raiz.find(f".//{{{NS_DPS}}}IBSCBS/{{{NS_DPS}}}valores/{{{NS_DPS}}}trib")
    assert (trib.findtext(f"{{{NS_DPS}}}CST"), trib.findtext(f"{{{NS_DPS}}}cClassTrib")) == (cst, cc)


def test_dps_de_2026_sem_bloco_valida_no_xsd(schema):  # noqa: F811
    raiz = etree.fromstring(montar_dps(_params(ibscbs=False, nbs="113019000")))
    schema.assertValid(raiz)
    assert raiz.find(f".//{{{NS_DPS}}}IBSCBS") is None

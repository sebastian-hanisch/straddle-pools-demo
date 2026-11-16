"""SplitMix64: Referenzwerte der Veröffentlichung, Bereiche, Wiederholbarkeit."""

import pytest

from stp_rng import SplitMix64


def test_referenzwerte_seed_null():
    """Die ersten drei Ausgaben für den Zufalls-Seed 0 stehen in der Literatur (Steele, Lea, Flood; Referenzimplementierung von Vigna)."""
    r = SplitMix64(0)
    assert [r.next_u64() for _ in range(3)] == [0xE220A8397B1DCDAF, 0x6E789E6AA1B965F4, 0x06C45D188009454F]


def test_gleicher_seed_gleiche_folge_anderer_seed_andere_folge():
    a = [SplitMix64(5).next_u64() for _ in range(1)]
    b = [SplitMix64(5).next_u64() for _ in range(1)]
    c = [SplitMix64(6).next_u64() for _ in range(1)]
    assert a == b and a != c


def test_below_bleibt_im_bereich_und_trifft_alle_werte():
    r = SplitMix64(1)
    werte = [r.below(7) for _ in range(500)]
    assert min(werte) == 0 and max(werte) == 6 and set(werte) == set(range(7))


def test_below_eins_ist_immer_null():
    r = SplitMix64(2)
    assert all(r.below(1) == 0 for _ in range(20))


def test_below_null_ist_ein_fehler():
    with pytest.raises(ValueError):
        SplitMix64(3).below(0)


def test_random_liegt_in_null_bis_eins():
    r = SplitMix64(4)
    zahlen = [r.random() for _ in range(200)]
    assert all(0.0 <= x < 1.0 for x in zahlen)


def test_shuffle_ist_eine_permutation():
    r = SplitMix64(9)
    xs = list(range(20))
    r.shuffle(xs)
    assert sorted(xs) == list(range(20)) and xs != list(range(20))

"""Colour science against published reference values."""

import numpy as np
import pytest

from app.services.color import (
    chroma,
    delta_e_2000,
    hex_to_lab,
    hue_angle,
    ita_degrees,
    lab_to_hex,
    lab_to_linear,
    linear_to_lab,
    linear_to_srgb,
    srgb8_to_lab,
    srgb_to_linear,
)


@pytest.mark.parametrize(
    ("rgb", "lab"),
    [
        ((255, 255, 255), (100.0, 0.0, 0.0)),
        ((0, 0, 0), (0.0, 0.0, 0.0)),
        ((255, 0, 0), (53.24, 80.09, 67.20)),
        ((0, 255, 0), (87.73, -86.18, 83.18)),
        ((0, 0, 255), (32.30, 79.19, -107.86)),
        ((128, 128, 128), (53.59, 0.0, 0.0)),
    ],
)
def test_srgb_to_lab_reference_values(rgb, lab):
    np.testing.assert_allclose(srgb8_to_lab(rgb), lab, atol=0.01)


# Sharma, Wu & Dalal (2005), "The CIEDE2000 color-difference formula", Table 1.
@pytest.mark.parametrize(
    ("lab1", "lab2", "expected"),
    [
        ((50, 2.6772, -79.7751), (50, 0, -82.7485), 2.0425),
        ((50, 3.1571, -77.2803), (50, 0, -82.7485), 2.8615),
        ((50, 0, 0), (50, -1, 2), 2.3669),
        ((50, 2.49, -0.001), (50, -2.49, 0.0009), 7.1792),
        ((50, 2.49, -0.001), (50, -2.49, 0.0011), 7.2195),
        ((50, 2.5, 0), (73, 25, -18), 27.1492),
        ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
        ((22.7233, 20.0904, -46.694), (23.0331, 14.973, -42.5619), 2.0373),
        ((90.8027, -2.0831, 1.441), (91.1528, -1.6435, 0.0447), 1.4441),
    ],
)
def test_ciede2000_reference_pairs(lab1, lab2, expected):
    assert float(delta_e_2000(lab1, lab2)) == pytest.approx(expected, abs=1e-4)
    assert float(delta_e_2000(lab2, lab1)) == pytest.approx(expected, abs=1e-4)  # symmetric


def test_round_trips():
    rng = np.random.default_rng(1)
    srgb = rng.random((200, 3))
    np.testing.assert_allclose(linear_to_srgb(srgb_to_linear(srgb)), srgb, atol=1e-9)
    linear = srgb_to_linear(srgb)
    np.testing.assert_allclose(lab_to_linear(linear_to_lab(linear)), linear, atol=1e-9)
    for value in ("#C99A82", "#292420", "#F6EDE4", "#000000", "#FFFFFF"):
        assert lab_to_hex(hex_to_lab(value)) == value


def test_hue_chroma_and_ita():
    assert float(hue_angle([60, 10, 0])) == pytest.approx(0)
    assert float(hue_angle([60, 0, 10])) == pytest.approx(90)
    assert float(hue_angle([60, 10, -10])) == pytest.approx(315)
    assert float(chroma([60, 3, 4])) == pytest.approx(5)
    assert float(ita_degrees([50, 0, 20])) == pytest.approx(0)  # ITA = atan((L - 50) / b)
    assert float(ita_degrees([70, 0, 20])) == pytest.approx(45)
    assert float(ita_degrees([30, 0, 20])) == pytest.approx(-45)

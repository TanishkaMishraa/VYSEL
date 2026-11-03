"""Colour science helpers: sRGB <-> CIELAB (D65) and CIEDE2000 colour difference.

Formulas follow IEC 61966-2-1 (sRGB), CIE 15 (L*a*b*) and Sharma, Wu & Dalal (2005) for
CIEDE2000. Arrays are float64; the last axis holds the three channels.
"""

from __future__ import annotations

import numpy as np

# sRGB (linear) -> CIE XYZ, D65 white (IEC 61966-2-1).
_RGB_TO_XYZ = np.array(
    [
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041],
    ]
)
_XYZ_TO_RGB = np.linalg.inv(_RGB_TO_XYZ)
_D65_WHITE = _RGB_TO_XYZ @ np.ones(3)
_EPSILON, _KAPPA = 216 / 24389, 24389 / 27


def srgb_to_linear(srgb: np.ndarray) -> np.ndarray:
    """sRGB values in [0, 1] -> linear light."""
    srgb = np.asarray(srgb, dtype=np.float64)
    return np.where(srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4)


_SRGB8_TO_LINEAR = srgb_to_linear(np.arange(256) / 255)


def srgb8_to_linear(rgb8: np.ndarray) -> np.ndarray:
    """uint8 sRGB -> linear light via an exact 256-entry lookup table (fast for whole images)."""
    return _SRGB8_TO_LINEAR[np.asarray(rgb8, dtype=np.uint8)]


def linear_to_srgb(linear: np.ndarray) -> np.ndarray:
    linear = np.clip(np.asarray(linear, dtype=np.float64), 0, 1)
    return np.where(linear <= 0.0031308, linear * 12.92, 1.055 * linear ** (1 / 2.4) - 0.055)


def linear_to_lab(linear: np.ndarray) -> np.ndarray:
    xyz = np.asarray(linear, dtype=np.float64) @ _RGB_TO_XYZ.T / _D65_WHITE
    f = np.where(xyz > _EPSILON, np.cbrt(xyz), (_KAPPA * xyz + 16) / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], axis=-1)


def lab_to_linear(lab: np.ndarray) -> np.ndarray:
    lab = np.asarray(lab, dtype=np.float64)
    fy = (lab[..., 0] + 16) / 116
    f = np.stack([fy + lab[..., 1] / 500, fy, fy - lab[..., 2] / 200], axis=-1)
    xyz = np.where(f**3 > _EPSILON, f**3, (116 * f - 16) / _KAPPA)
    xyz[..., 1] = np.where(lab[..., 0] > _KAPPA * _EPSILON, fy**3, lab[..., 0] / _KAPPA)
    return (xyz * _D65_WHITE) @ _XYZ_TO_RGB.T


def srgb8_to_lab(rgb8: np.ndarray) -> np.ndarray:
    return linear_to_lab(srgb_to_linear(np.asarray(rgb8, dtype=np.float64) / 255))


def lab_to_hex(lab: np.ndarray) -> str:
    rgb = np.round(linear_to_srgb(lab_to_linear(np.asarray(lab, dtype=np.float64))) * 255).astype(int)
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def hex_to_lab(value: str) -> np.ndarray:
    value = value.lstrip("#")
    return srgb8_to_lab(np.array([int(value[i : i + 2], 16) for i in (0, 2, 4)]))


def chroma(lab: np.ndarray) -> np.ndarray:
    lab = np.asarray(lab, dtype=np.float64)
    return np.hypot(lab[..., 1], lab[..., 2])


def hue_angle(lab: np.ndarray) -> np.ndarray:
    """CIELAB hue angle h_ab in degrees, [0, 360). 0 = red/magenta axis (+a*), 90 = yellow (+b*)."""
    lab = np.asarray(lab, dtype=np.float64)
    return np.degrees(np.arctan2(lab[..., 2], lab[..., 1])) % 360


def ita_degrees(lab: np.ndarray) -> np.ndarray:
    """Individual Typology Angle, a dermatology measure of constitutive skin colour (Chardon et al., 1991)."""
    lab = np.asarray(lab, dtype=np.float64)
    return np.degrees(np.arctan2(lab[..., 0] - 50, lab[..., 2]))


def delta_e_2000(lab1: np.ndarray, lab2: np.ndarray) -> np.ndarray:
    """CIEDE2000 colour difference (kL = kC = kH = 1)."""
    lab1, lab2 = np.broadcast_arrays(np.asarray(lab1, dtype=np.float64), np.asarray(lab2, dtype=np.float64))
    l1, a1, b1 = lab1[..., 0], lab1[..., 1], lab1[..., 2]
    l2, a2, b2 = lab2[..., 0], lab2[..., 1], lab2[..., 2]
    c_bar = (np.hypot(a1, b1) + np.hypot(a2, b2)) / 2
    g = 0.5 * (1 - np.sqrt(c_bar**7 / (c_bar**7 + 25**7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360

    dl = l2 - l1
    dc = c2p - c1p
    dh = h2p - h1p
    dh = np.where(dh > 180, dh - 360, np.where(dh < -180, dh + 360, dh))
    dh = np.where(c1p * c2p == 0, 0, dh)
    d_h = 2 * np.sqrt(c1p * c2p) * np.sin(np.radians(dh / 2))

    l_bar = (l1 + l2) / 2
    c_bar_p = (c1p + c2p) / 2
    h_sum = h1p + h2p
    h_bar = np.where(
        c1p * c2p == 0,
        h_sum,
        np.where(np.abs(h1p - h2p) <= 180, h_sum / 2, np.where(h_sum < 360, (h_sum + 360) / 2, (h_sum - 360) / 2)),
    )
    t = (
        1
        - 0.17 * np.cos(np.radians(h_bar - 30))
        + 0.24 * np.cos(np.radians(2 * h_bar))
        + 0.32 * np.cos(np.radians(3 * h_bar + 6))
        - 0.20 * np.cos(np.radians(4 * h_bar - 63))
    )
    d_theta = 30 * np.exp(-(((h_bar - 275) / 25) ** 2))
    r_c = 2 * np.sqrt(c_bar_p**7 / (c_bar_p**7 + 25**7))
    s_l = 1 + 0.015 * (l_bar - 50) ** 2 / np.sqrt(20 + (l_bar - 50) ** 2)
    s_c = 1 + 0.045 * c_bar_p
    s_h = 1 + 0.015 * c_bar_p * t
    r_t = -np.sin(np.radians(2 * d_theta)) * r_c
    return np.sqrt((dl / s_l) ** 2 + (dc / s_c) ** 2 + (d_h / s_h) ** 2 + r_t * (dc / s_c) * (d_h / s_h))

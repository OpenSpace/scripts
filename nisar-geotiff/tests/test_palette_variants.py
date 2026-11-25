import tempfile
import unittest
from pathlib import Path
import shutil

import numpy as np
import rasterio
from rasterio.enums import ColorInterp
from rasterio.transform import from_origin

from create_palette_variants import (
    PALETTE_PRESETS,
    PORTAL_HUE_ROTATION,
    PORTAL_SATURATION,
    _apply_palette,
    _palette_lookup,
    _rgb_codes,
    _rotate_hue,
    create_palette_variants,
)


class PaletteVariantTests(unittest.TestCase):
    def test_hue_rotation_maps_yellow_to_mint_and_blue_to_magenta(self) -> None:
        rgb = np.array([[[255, 0]], [[255, 0]], [[0, 255]]], dtype=np.uint8)
        shifted = _rotate_hue(rgb, PORTAL_HUE_ROTATION, PORTAL_SATURATION)
        self.assertGreater(shifted[1, 0, 0], shifted[0, 0, 0])
        self.assertEqual(shifted[0, 0, 0], shifted[2, 0, 0])
        self.assertGreater(shifted[0, 0, 1], shifted[1, 0, 1])
        self.assertEqual(shifted[0, 0, 1], shifted[2, 0, 1])

    def test_palette_variants_preserve_mapping_mask_and_overviews(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            input_path = directory / (
                "NISAR_L2_PR_GCOV_031_170_D_067_4005_DHDH_A_"
                "20260930T000009_20260930T000044_P05023_N_F_J_001_rgb_5pct.tif"
            )
            data = np.zeros((4, 8, 8), dtype=np.uint8)
            ramp = np.arange(64, dtype=np.uint8).reshape(8, 8) * 4
            data[0] = ramp
            data[1] = ramp[::-1, :]
            data[2] = ramp[:, ::-1]
            data[3] = 255
            data[3, 0, 0] = 0
            with rasterio.open(
                input_path,
                "w",
                driver="GTiff",
                width=8,
                height=8,
                count=4,
                dtype="uint8",
                crs="EPSG:4326",
                transform=from_origin(-75, 44, 0.1, 0.1),
            ) as source:
                source.colorinterp = (
                    ColorInterp.red,
                    ColorInterp.green,
                    ColorInterp.blue,
                    ColorInterp.alpha,
                )
                source.write(data)

            outputs = create_palette_variants(input_path, directory / "palette")
            self.assertEqual(len(outputs), 10)
            for output, (preset_name, _, _, gamma) in zip(
                outputs, PALETTE_PRESETS
            ):
                with rasterio.open(output) as result:
                    self.assertEqual(result.colorinterp[3], ColorInterp.alpha)
                    self.assertEqual(result.read(4)[0, 0], 0)
                    self.assertEqual(result.overviews(1), [2, 4])
                    bounds = [
                        tuple(map(int, value.split("-")))
                        for value in result.tags()["stretch_bounds_rgb"].split(";")
                    ]
                    source_values = data[:3, 1, 1]
                    expected = []
                    for value, (low, high), exponent in zip(
                        source_values, bounds, gamma
                    ):
                        normalized = (
                            np.clip((int(value) - low) / (high - low), 0.0, 1.0)
                            if high > low
                            else 0.0
                        )
                        expected.append(round(normalized**exponent * 255))
                    stretched = _apply_palette(
                        data[:3, 1:2, 1:2], tuple(bounds), gamma
                    )
                    shifted = _rotate_hue(
                        stretched, PORTAL_HUE_ROTATION, PORTAL_SATURATION
                    )
                    self.assertEqual(
                        result.read()[:3, 1, 1].tolist(),
                        shifted[:, 0, 0].tolist(),
                    )
                    self.assertEqual(result.tags()["palette_preset"], preset_name)
                    self.assertEqual(
                        float(result.tags()["hue_rotation_degrees"]),
                        PORTAL_HUE_ROTATION,
                    )
                info = output.with_suffix(".info").read_text(encoding="utf-8")
                self.assertIn("NISAR 2026-09-30 (5%)", info)
                self.assertIn(preset_name, info)
                with rasterio.open(output.with_suffix(".vrt")) as vrt:
                    self.assertEqual(vrt.count, 4)
                    self.assertEqual(vrt.crs.to_epsg(), 4326)

            full_resolution_input = directory / (
                "NISAR_L2_PR_GCOV_031_170_D_067_4005_DHDH_A_"
                "20260930T000009_20260930T000044_P05023_N_F_J_001_rgb.tif"
            )
            shutil.copyfile(input_path, full_resolution_input)
            selected_outputs = create_palette_variants(
                full_resolution_input,
                directory / "selected",
                preset_names=["portal-detail"],
            )
            self.assertEqual(
                [path.name for path in selected_outputs],
                ["nisar_031_170_D_20260930T000009_portal-detail_100pct.tif"],
            )
            info = selected_outputs[0].with_suffix(".info").read_text(
                encoding="utf-8"
            )
            self.assertIn("NISAR 2026-09-30 (100%)", info)
            september_identifier = next(
                line for line in info.splitlines() if line.startswith("Identifier")
            )

            july_input = directory / (
                "NISAR_L2_PR_GCOV_025_133_A_023_4005_DHDH_A_"
                "20260717T095915_20260717T095948_P05023_N_F_J_001_rgb.tif"
            )
            shutil.copyfile(input_path, july_input)
            july_outputs = create_palette_variants(
                july_input,
                directory / "july",
                preset_names=["portal-detail"],
            )
            july_info = july_outputs[0].with_suffix(".info").read_text(
                encoding="utf-8"
            )
            self.assertIn("NISAR 2026-07-17 (100%)", july_info)
            july_identifier = next(
                line
                for line in july_info.splitlines()
                if line.startswith("Identifier")
            )
            self.assertNotEqual(september_identifier, july_identifier)

    def test_palette_lookup_matches_direct_computation(self) -> None:
        bounds = ((10, 240), (5, 230), (0, 200))
        gamma = (0.5, 0.6, 0.7)
        rng = np.random.default_rng(0)
        rgb = rng.integers(0, 256, size=(3, 64, 64), dtype=np.uint8)
        expected = _rotate_hue(
            _apply_palette(rgb, bounds, gamma),
            PORTAL_HUE_ROTATION,
            PORTAL_SATURATION,
        )
        lookup = _palette_lookup(bounds, gamma)
        np.testing.assert_array_equal(lookup[:, _rgb_codes(rgb)], expected)

    def test_stretch_from_gives_scenes_matching_bounds(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            ramp = np.arange(64, dtype=np.uint8).reshape(8, 8)
            inputs = []
            for date, offset in (("20260623", 0), ("20261021", 120)):
                path = directory / (
                    f"NISAR_L2_PR_GCOV_023_134_A_022_4005_DHDH_A_"
                    f"{date}T113834_{date}T113909_P05023_N_F_J_001_rgb.tif"
                )
                data = np.zeros((4, 8, 8), dtype=np.uint8)
                data[:3] = ramp + offset
                data[3] = 255
                with rasterio.open(
                    path,
                    "w",
                    driver="GTiff",
                    width=8,
                    height=8,
                    count=4,
                    dtype="uint8",
                    crs="EPSG:4326",
                    transform=from_origin(-75, 44, 0.1, 0.1),
                ) as source:
                    source.colorinterp = (
                        ColorInterp.red,
                        ColorInterp.green,
                        ColorInterp.blue,
                        ColorInterp.alpha,
                    )
                    source.write(data)
                inputs.append(path)

            def bounds(output: Path) -> str:
                with rasterio.open(output) as result:
                    return result.tags()["stretch_bounds_rgb"]

            separate = [
                create_palette_variants(
                    path, directory / f"separate{index}", preset_names=["portal-detail"]
                )[0]
                for index, path in enumerate(inputs)
            ]
            self.assertNotEqual(bounds(separate[0]), bounds(separate[1]))

            shared = [
                create_palette_variants(
                    path,
                    directory / f"shared{index}",
                    preset_names=["portal-detail"],
                    stretch_sources=inputs,
                )[0]
                for index, path in enumerate(inputs)
            ]
            self.assertEqual(bounds(shared[0]), bounds(shared[1]))
            self.assertEqual(
                shared[1].name,
                "nisar_023_134_A_20261021T113834_portal-detail_shared-stretch_100pct.tif",
            )
            low, high = map(int, bounds(shared[0]).split(";")[0].split("-"))
            self.assertLess(low, 64)
            self.assertGreaterEqual(high, 120)
            info = shared[0].with_suffix(".info").read_text(encoding="utf-8")
            self.assertIn("combined stretch sources", info)
            self.assertIn("portal-detail, shared stretch", info)


if __name__ == "__main__":
    unittest.main()

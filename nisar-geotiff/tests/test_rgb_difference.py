import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import ColorInterp
from rasterio.transform import from_origin

from create_rgb_difference import create_differences


def _write_rgba(path: Path, transform, data: np.ndarray) -> None:
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=data.shape[2],
        height=data.shape[1],
        count=4,
        dtype="uint8",
        crs="EPSG:4326",
        transform=transform,
    ) as dataset:
        dataset.colorinterp = (
            ColorInterp.red,
            ColorInterp.green,
            ColorInterp.blue,
            ColorInterp.alpha,
        )
        dataset.write(data)


class RgbDifferenceTests(unittest.TestCase):
    def test_differences_are_cropped_to_scene_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            earlier_data = np.zeros((4, 8, 12), dtype=np.uint8)
            earlier_data[0] = 10
            earlier_data[1] = 100
            earlier_data[2] = 150
            earlier_data[3] = 255
            later_data = np.zeros((4, 8, 8), dtype=np.uint8)
            later_data[0] = 20
            later_data[1] = 80
            later_data[2] = 150
            later_data[3] = 255
            earlier_data[3, 2, 6] = 0
            later_data[3, 2, 2] = 0

            earlier_path = directory / (
                "NISAR_L2_PR_GCOV_025_133_A_023_4005_DHDH_A_"
                "20260717T095915_20260717T095948_P05023_N_F_J_001_rgb_5pct.tif"
            )
            later_path = directory / (
                "NISAR_L2_PR_GCOV_031_170_D_067_4005_DHDH_A_"
                "20260930T000009_20260930T000044_P05023_N_F_J_001_rgb_5pct.tif"
            )
            _write_rgba(
                earlier_path,
                from_origin(0, 1, 0.1, 0.1),
                earlier_data,
            )
            _write_rgba(
                later_path,
                from_origin(0.4, 1, 0.1, 0.1),
                later_data,
            )

            outputs = create_differences(
                earlier_path,
                later_path,
                directory / "difference",
                overwrite=False,
                threshold=10,
            )

            self.assertEqual(len(outputs), 2)
            with rasterio.open(outputs[0]) as absolute:
                self.assertEqual((absolute.width, absolute.height), (8, 8))
                self.assertAlmostEqual(absolute.bounds.left, 0.4)
                self.assertAlmostEqual(absolute.bounds.right, 1.2)
                np.testing.assert_array_equal(
                    absolute.read(window=((0, 1), (0, 1)))[:, 0, 0],
                    [10, 20, 0, 255],
                )
                self.assertEqual(
                    absolute.read(window=((2, 3), (2, 3)))[3, 0, 0], 0
                )
                info = outputs[0].with_suffix(".info").read_text(encoding="utf-8")
                self.assertIn(
                    "2026-07-17 to 2026-09-30 (5%, threshold 10/255)", info
                )

            with rasterio.open(outputs[1]) as signed:
                np.testing.assert_array_equal(
                    signed.read(window=((0, 1), (0, 1)))[:, 0, 0],
                    [133, 118, 128, 255],
                )
                self.assertTrue(outputs[0].with_suffix(".vrt").exists())
                self.assertTrue(outputs[0].with_suffix(".info").exists())
                self.assertTrue(outputs[1].with_suffix(".vrt").exists())
                self.assertTrue(outputs[1].with_suffix(".info").exists())

    def test_threshold_makes_subthreshold_pixels_transparent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            earlier = np.zeros((4, 2, 2), dtype=np.uint8)
            earlier[3] = 255
            later = earlier.copy()
            later[0, 0, 0] = 20
            later[1, 0, 0] = 39
            later[2, 0, 0] = 40
            later[0, 0, 1] = 20
            later[1, 0, 1] = 39
            earlier_path = directory / "earlier.tif"
            later_path = directory / "later.tif"
            _write_rgba(earlier_path, from_origin(0, 1, 0.1, 0.1), earlier)
            _write_rgba(later_path, from_origin(0, 1, 0.1, 0.1), later)

            outputs = create_differences(
                earlier_path,
                later_path,
                directory / "thresholded",
                overwrite=False,
                threshold=40,
            )

            with rasterio.open(outputs[0]) as absolute:
                self.assertEqual(
                    absolute.read(window=((0, 1), (0, 1)))[3, 0, 0], 255
                )
                self.assertEqual(
                    absolute.read(window=((0, 1), (1, 2)))[3, 0, 0], 0
                )
                self.assertIn("_threshold40_absolute", outputs[0].name)
            with rasterio.open(outputs[1]) as signed:
                self.assertEqual(
                    signed.read(window=((0, 1), (1, 2)))[3, 0, 0], 0
                )


if __name__ == "__main__":
    unittest.main()

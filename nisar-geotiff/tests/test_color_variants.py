import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import ColorInterp
from rasterio.transform import from_origin

from create_color_variants import VARIANTS, create_color_variants


class ColorVariantTests(unittest.TestCase):
    def test_creates_ten_mapped_rgba_previews_and_sidecars(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            input_path = directory / (
                "NISAR_L2_PR_GCOV_031_170_D_067_4005_DHDH_A_"
                "20260930T000009_20260930T000044_P05023_N_F_J_001_rgb_5pct.tif"
            )
            data = np.zeros((4, 2, 3), dtype=np.uint8)
            data[0] = 20
            data[1] = 80
            data[2] = 140
            data[3] = 255
            data[3, 0, 0] = 0
            with rasterio.open(
                input_path,
                "w",
                driver="GTiff",
                width=3,
                height=2,
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

            output_directory = directory / "variants"
            outputs = create_color_variants(input_path, output_directory)
            self.assertEqual(len(outputs), 10)
            self.assertEqual(len(VARIANTS), 10)

            for output, (slug, variant, indices) in zip(outputs, VARIANTS):
                with rasterio.open(output) as raster:
                    self.assertEqual((raster.width, raster.height), (3, 2))
                    self.assertEqual(raster.count, 4)
                    self.assertEqual(raster.crs.to_epsg(), 4326)
                    self.assertEqual(raster.colorinterp[3], ColorInterp.alpha)
                    pixel = raster.read(window=((1, 2), (1, 2)))[:, 0, 0]
                    if indices is None:
                        self.assertEqual(pixel.tolist(), [80, 80, 80, 255])
                    else:
                        self.assertEqual(
                            pixel.tolist(),
                            [data[index, 1, 1] for index in indices] + [255],
                        )
                    self.assertEqual(
                        raster.read(4, window=((0, 1), (0, 1)))[0, 0], 0
                    )

                info = output.with_suffix(".info").read_text(encoding="utf-8")
                self.assertIn("2026-09-30 (5%)", info)
                self.assertIn(variant, info)
                self.assertIn(output.with_suffix(".vrt").name, info)
                self.assertTrue(output.with_suffix(".vrt").exists())
                with rasterio.open(output.with_suffix(".vrt")) as vrt:
                    self.assertEqual(vrt.count, 4)
                    self.assertEqual(vrt.crs.to_epsg(), 4326)


if __name__ == "__main__":
    unittest.main()

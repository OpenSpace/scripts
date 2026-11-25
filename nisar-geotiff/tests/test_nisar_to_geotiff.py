import tempfile
import unittest
from pathlib import Path

import h5py
import numpy as np
import rasterio
from rasterio.enums import ColorInterp
from rasterio.windows import Window

from nisar_to_geotiff import _write_source, main


def _create_gcove_file(path: Path) -> None:
    height, width = 12, 16
    rows, columns = np.indices((height, width))
    hh = np.full((height, width), 0.1, dtype=np.float32)
    hv = np.full((height, width), 0.01, dtype=np.float32)
    hh += columns * 0.001
    mask = np.ones((height, width), dtype=np.uint8)
    mask[0, 0] = 255
    mask[1, 1] = 0
    hh[0, 0] = np.nan
    hv[0, 0] = np.nan
    hh[1, 1] = np.nan
    hv[1, 1] = np.nan

    with h5py.File(path, "w") as product:
        group = product.create_group(
            "/science/LSAR/GCOV/grids/frequencyA"
        )
        group.create_dataset("HHHH", data=hh)
        group.create_dataset("HVHV", data=hv)
        group.create_dataset("mask", data=mask)
        group.create_dataset(
            "xCoordinates", data=500000 + np.arange(width) * 10.0
        )
        group.create_dataset(
            "yCoordinates", data=4500000 - np.arange(height) * 10.0
        )
        projection = group.create_dataset("projection", data=np.uint32(32618))
        projection.attrs["epsg_code"] = np.int64(32618)


class NisarToGeoTiffTests(unittest.TestCase):
    def test_source_resolution_percent_decimates_pixels(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            input_path = directory / "sample_20260712T235152_product.h5"
            output_path = directory / "preview.tif"
            _create_gcove_file(input_path)

            width, height, _ = _write_source(
                input_path,
                output_path,
                "A",
                "single",
                "HHHH",
                (-30.0, 0.0),
                (0.0, 20.0),
                10.0,
            )

            self.assertEqual((width, height), (2, 2))
            with rasterio.open(output_path) as preview:
                self.assertEqual((preview.width, preview.height), (2, 2))
                self.assertEqual(preview.transform.a, 100.0)
                self.assertEqual(preview.transform.e, -100.0)
                self.assertAlmostEqual(preview.read(1)[0, 1], 0.11)

    def test_rgb_output_and_global_vrt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            input_path = directory / "sample_20260712T235152_product.h5"
            output_path = directory / "rgb.tif"
            _create_gcove_file(input_path)

            self.assertEqual(main([str(input_path), str(output_path)]), 0)
            vrt_path = output_path.with_suffix(".vrt")
            info_path = output_path.with_suffix(".info")
            info = info_path.read_text(encoding="utf-8")
            self.assertIn('Name = "NISAR 2026-07-12 (100%)"', info)
            self.assertIn('Identifier = "NISAR_rgb"', info)
            self.assertIn('ColorFile = "rgb.vrt"', info)
            self.assertIn('BlendMode = "Normal"', info)

            with rasterio.open(output_path) as image:
                self.assertEqual(image.crs, rasterio.crs.CRS.from_epsg(4326))
                self.assertEqual(image.count, 4)
                self.assertEqual(
                    image.colorinterp,
                    (
                        ColorInterp.red,
                        ColorInterp.green,
                        ColorInterp.blue,
                        ColorInterp.alpha,
                    ),
                )
                self.assertTrue(np.any(image.read(4) == 255))
                self.assertTrue(np.any(image.read(4) == 0))
                center_x, center_y = image.xy(image.height // 2, image.width // 2)

            with rasterio.open(vrt_path) as globe:
                self.assertEqual(globe.crs, rasterio.crs.CRS.from_epsg(4326))
                self.assertGreater(globe.width, 360)
                self.assertGreater(globe.height, 180)
                self.assertEqual(globe.count, 4)
                self.assertEqual(globe.colorinterp[3], ColorInterp.alpha)
                self.assertTrue(np.all(globe.read(4, window=Window(0, 0, 4, 4)) == 0))
                row, column = globe.index(center_x, center_y)
                alpha = globe.read(
                    4, window=Window(column - 2, row - 2, 5, 5)
                )
                self.assertTrue(np.any(alpha == 255))

    def test_single_band_output_and_vrt_alpha(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            input_path = directory / "sample_20260712T235152_product.h5"
            output_path = directory / "hh.tif"
            _create_gcove_file(input_path)

            main(
                [
                    str(input_path),
                    str(output_path),
                    "--mode",
                    "single",
                    "--polarization",
                    "HHHH",
                ]
            )
            info = output_path.with_suffix(".info").read_text(encoding="utf-8")
            self.assertIn('Name = "NISAR 2026-07-12 (100%)"', info)
            self.assertIn('ColorFile = "hh.vrt"', info)

            with rasterio.open(output_path) as image:
                self.assertEqual(image.crs, rasterio.crs.CRS.from_epsg(4326))
                self.assertEqual(image.count, 1)
                self.assertEqual(image.dtypes, ("float32",))
                self.assertTrue(np.isfinite(image.read(1)).any())
                center_x, center_y = image.xy(image.height // 2, image.width // 2)

            with rasterio.open(output_path.with_suffix(".vrt")) as globe:
                self.assertEqual(globe.count, 2)
                self.assertEqual(globe.colorinterp[1], ColorInterp.alpha)
                row, column = globe.index(center_x, center_y)
                alpha = globe.read(
                    2, window=Window(column - 2, row - 2, 5, 5)
                )
                self.assertTrue(np.any(alpha == 255))


if __name__ == "__main__":
    unittest.main()

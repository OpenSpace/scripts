import sys
from pathlib import Path

import h5py
import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import nisar_timelapse as nt  # noqa: E402


def make_gcov(path: Path, bright: float) -> None:
    # ~40 km square of UTM zone 57N (EPSG:32657) around 160.27E, 54.59N, 20 m pixels.
    x = 600000.0 + 20.0 * np.arange(2000)
    y = 6050000.0 - 20.0 * np.arange(2000)
    with h5py.File(path, "w") as f:
        g = f.create_group("science/LSAR/GCOV/grids/frequencyA")
        g["xCoordinates"] = x
        g["yCoordinates"] = y
        g.create_dataset("projection", data=32657).attrs["epsg_code"] = 32657
        data = np.full((2000, 2000), 0.01, dtype=np.float32)
        data[900:1100, 900:1100] = bright
        g["HHHH"] = data
        g["mask"] = np.full((2000, 2000), 1, dtype=np.uint8)


def test_timelapse_shared_grid(tmp_path):
    names = [
        "NISAR_L2_PR_GCOV_023_060_D_061_4005_DHDH_A_20260618T084927_20260618T085005_P05023_N_F_J_001.h5",
        "NISAR_L2_PR_GCOV_024_060_D_061_4005_DHDH_A_20260630T084926_20260630T085005_P05023_N_F_J_001.h5",
    ]
    for name, bright in zip(names, (0.05, 0.5)):
        make_gcov(tmp_path / name, bright)
    out = tmp_path / "out"
    # Center the crop on the synthetic data (find it via its UTM center).
    from rasterio.warp import transform
    lon, lat = transform("EPSG:32657", "EPSG:4326", [620000.0], [6030000.0])
    rc = nt.main([str(tmp_path), str(out), "--center", str(lon[0]), str(lat[0]),
                  "--half-size-km", "5", "--db-range", "-30", "0"])
    assert rc == 0
    tifs = sorted(out.glob("*.tif"))
    assert len(tifs) == 2
    shapes = set()
    for tif in tifs:
        with rasterio.open(tif) as ds:
            shapes.add((ds.width, ds.height, tuple(ds.transform)))
            assert ds.count == 4 and ds.crs.to_epsg() == 4326
            assert ds.read(4).any()
        assert tif.with_suffix(".vrt").exists() and tif.with_suffix(".info").exists()
    assert len(shapes) == 1  # identical grid
    with rasterio.open(tifs[1]) as late, rasterio.open(tifs[0]) as early:
        assert late.read(1).max() > early.read(1).max()

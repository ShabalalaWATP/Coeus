import json
import subprocess
import sys
from importlib import import_module
from pathlib import Path
from zipfile import ZipFile

GENERATOR_ROOT = Path(__file__).resolve().parents[3] / "packages" / "mock-product-generators"


def test_mock_catalog_default_counts_are_public_safe() -> None:
    catalog = _catalog()
    manifest = catalog.write_mock_catalog(Path("unused"), write_assets=False)

    assert manifest["banner"] == "MOCK DATA ONLY"
    assert manifest["productCount"] == 190
    assert manifest["assetCount"] == 410
    assert {acg["code"] for acg in manifest["acgs"]} >= {
        "ACG-ALPHA-REGIONAL",
        "ACG-BRAVO-COLLECTION",
        "ACG-CHARLIE-ASSESSMENT",
        "ACG-DELTA-GEO",
        "ACG-ECHO-DATA",
    }
    assert all("MOCK DATA ONLY" in product["summary"] for product in manifest["products"])
    assert all(product["status"] == "published" for product in manifest["products"])
    assert all(product["timePeriodStart"] for product in manifest["products"])
    assert all(product["timePeriodEnd"] for product in manifest["products"])
    assert all(product["semanticLabels"] for product in manifest["products"])
    assert {scenario["name"] for scenario in manifest["searchScenarios"]} >= {
        "maritime_port_disruption",
        "cyber_energy_intrusion",
        "geospatial_border_crossing",
        "collection_sensor_activity",
    }


def test_mock_catalog_generation_writes_safe_assets(tmp_path: Path) -> None:
    catalog = _catalog()
    counts = {family: 1 for family in catalog.DEFAULT_PRODUCT_COUNTS}
    manifest = catalog.write_mock_catalog(tmp_path, counts)

    paths = [
        asset["relativePath"] for product in manifest["products"] for asset in product["assets"]
    ]
    assert len(paths) == 16
    assert len(paths) == len(set(paths))
    assert all(not Path(path).is_absolute() and ".." not in Path(path).parts for path in paths)
    assert all((tmp_path / path).is_file() for path in paths)

    first_pdf = next(path for path in paths if path.endswith(".pdf"))
    first_docx = next(path for path in paths if path.endswith(".docx"))
    first_geojson = next(path for path in paths if path.endswith(".geojson"))
    geojson_product = next(product for product in manifest["products"] if product["geojsonRef"])
    assert b"MOCK DATA ONLY" in (tmp_path / first_pdf).read_bytes()
    assert geojson_product["geojsonRef"] in paths
    assert "MOCK DATA ONLY" in (tmp_path / first_geojson).read_text(encoding="utf-8")
    with ZipFile(tmp_path / first_docx) as archive:
        document = archive.read("word/document.xml").decode("utf-8")
    assert "MOCK DATA ONLY" in document


def test_mock_catalog_is_deterministic(tmp_path: Path) -> None:
    catalog = _catalog()
    counts = {family: 1 for family in catalog.DEFAULT_PRODUCT_COUNTS}
    first = catalog.write_mock_catalog(tmp_path / "first", counts)
    second = catalog.write_mock_catalog(tmp_path / "second", counts)

    first_products = first["products"]
    second_products = second["products"]
    assert first_products[0]["id"] == second_products[0]["id"]
    assert first_products[0]["assets"][0]["sha256"] == second_products[0]["assets"][0]["sha256"]


def test_seed_mock_products_script_writes_manifest(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[3] / "scripts" / "seed" / "seed_mock_products.py"
    result = subprocess.run(  # noqa: S603 - fixed local script path under test.
        [sys.executable, str(script), "--small", "--output-dir", str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
    )

    output = json.loads(result.stdout)
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert output["productCount"] == 7
    assert output["assetCount"] == 16
    assert manifest["banner"] == "MOCK DATA ONLY"


def _catalog():
    if str(GENERATOR_ROOT) not in sys.path:
        sys.path.insert(0, str(GENERATOR_ROOT))
    return import_module("mock_product_generators")

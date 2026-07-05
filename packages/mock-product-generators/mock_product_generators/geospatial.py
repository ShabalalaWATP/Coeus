import json
from pathlib import Path

from .models import MOCK_BANNER, SeedProduct


def write_geojson(path: Path, product: SeedProduct) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    west, south, east, north = product.bounding_box or (-7.0, 54.0, 31.0, 66.0)
    feature = {
        "type": "FeatureCollection",
        "name": product.title,
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "banner": MOCK_BANNER,
                    "reference": product.reference,
                    "title": product.title,
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [west, south],
                            [east, south],
                            [east, north],
                            [west, north],
                            [west, south],
                        ]
                    ],
                },
            }
        ],
    }
    path.write_text(json.dumps(feature, indent=2, sort_keys=True), encoding="utf-8")


def write_kml(path: Path, product: SeedProduct) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    west, south, east, north = product.bounding_box or (-7.0, 54.0, 31.0, 66.0)
    coordinates = f"{west},{south},0 {east},{south},0 {east},{north},0 {west},{north},0 {west},{south},0"
    path.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>{product.title}</name>
    <description>{MOCK_BANNER}</description>
    <Placemark>
      <name>{product.reference}</name>
      <Polygon><outerBoundaryIs><LinearRing><coordinates>{coordinates}</coordinates></LinearRing></outerBoundaryIs></Polygon>
    </Placemark>
  </Document>
</kml>
""",
        encoding="utf-8",
    )

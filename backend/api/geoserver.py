"""Legacy GeoServer integration is disabled in the standalone demo.

No GeoServer installation, credentials, raster upload, or network access is
required. Printing uses the browser's Print dialog.
"""


def create_geoserver_store(workspace, store_name):
    raise NotImplementedError("GeoServer publishing is not part of the local demo.")


def upload_geotiff(workspace, store_name, file_path):
    raise NotImplementedError("GeoServer publishing is not part of the local demo.")


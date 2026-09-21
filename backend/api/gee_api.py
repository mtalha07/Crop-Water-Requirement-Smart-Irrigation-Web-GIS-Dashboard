# import ee
# import rasterio
# from osgeo import gdal

# # Initialize Google Earth Engine
# ee.Initialize()

# # Load Evapotranspiration Data from OpenET
# def fetch_evapotranspiration():
#     et_image = ee.ImageCollection("OpenET/SSEBop/ETmonthly").filterDate("2023-01-01", "2023-12-31").mean()

#     # Define region of interest (Bangalore example)
#     region = ee.Geometry.Rectangle([77.5, 12.5, 78.0, 13.0])

#     # Export data as GeoTIFF
#     task = ee.batch.Export.image.toDrive(
#         image=et_image,
#         description="Evapotranspiration_Export",
#         scale=1000,
#         region=region.getInfo(),
#         fileFormat='GeoTIFF'
#     )
#     task.start()
#     return "Export started successfully!"

# # Test function
# if __name__ == "__main__":
#     print(fetch_evapotranspiration())

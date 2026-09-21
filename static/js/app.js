(function () {
  "use strict";
  var spatialUrl = document.currentScript.getAttribute("data-spatial-url");
  document.addEventListener("DOMContentLoaded", function () {
    function el(id) { return document.getElementById(id); }
    function number(value, digits) { return Number(value).toLocaleString(undefined, {maximumFractionDigits: digits, minimumFractionDigits: digits}); }
    var form = el("waterForm"), latInput = el("lat"), lonInput = el("lon");
    var select = el("demoPole"), mapStatus = el("map-status"), button = el("calculateButton");
    var poles = [], polygon = null, drawing = false, mapReady = false;
    var showPoles = null, centerMap = null, showPoint = null, startDraw = null;
    var stopDraw = null, clearGeometry = null, showWeatherSamples = null;
    var requestVersion = 0, activeRequest = null;
    function mode() { return form.elements.mode.value; }
    function revealOnSmallScreen(selector) {
      if (window.matchMedia("(max-width: 760px)").matches) {
        document.querySelector(selector).scrollIntoView({
          block: "start", behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"
        });
      }
    }
    function syncButton() {
      button.disabled = !!activeRequest || drawing || (mode() === "polygon" && !polygon);
      el("drawField").disabled = !mapReady || drawing;
      el("clearField").disabled = !polygon && !drawing;
    }
    function invalidate() {
      requestVersion += 1;
      if (activeRequest) activeRequest.abort();
      activeRequest = null;
      el("water-needed").textContent = "Ready for a new calculation";
      el("result-summary").textContent = mode() === "polygon" ? "Draw a boundary, then calculate its total daily water volume." : "Choose your crop and location, then calculate.";
      el("calculation-details").textContent = "";
      el("form-error").textContent = "";
      el("result-badge").textContent = "Inputs updated";
      el("field-metrics").hidden = true;
      el("sample-details").hidden = true;
      document.querySelector(".results-panel").setAttribute("aria-busy", "false");
      if (showWeatherSamples) showWeatherSamples([]);
      syncButton();
    }
    function setCoordinates(lat, lon) {
      latInput.value = Number(lat).toFixed(6);
      lonInput.value = Number(lon).toFixed(6);
      invalidate();
      if (showPoint) showPoint(Number(lonInput.value), Number(latInput.value));
    }
    function changeMode() {
      if (stopDraw) stopDraw();
      drawing = false;
      polygon = null;
      var fieldMode = mode() === "polygon";
      el("point-fields").hidden = fieldMode;
      el("polygon-fields").hidden = !fieldMode;
      latInput.disabled = lonInput.disabled = select.disabled = fieldMode;
      if (clearGeometry) clearGeometry(true);
      el("field-status").textContent = mapReady ? "Select Draw boundary to begin." : "Waiting for the map…";
      el("drawField").textContent = "Draw boundary";
      el("clearField").textContent = "Clear";
      if (!fieldMode && showPoint) showPoint(Number(lonInput.value), Number(latInput.value));
      mapStatus.textContent = fieldMode ? "Use Draw boundary. Click each corner, then double-click the final corner." : "Click anywhere on the map to select a location.";
      invalidate();
    }
    form.querySelectorAll("[name=mode]").forEach(function (radio) { radio.addEventListener("change", changeMode); });
    form.addEventListener("input", function (event) {
      if (event.target.name !== "mode") invalidate();
      if ((event.target === latInput || event.target === lonInput) && latInput.checkValidity() && lonInput.checkValidity() && showPoint) {
        showPoint(Number(lonInput.value), Number(latInput.value));
      }
    });
    select.addEventListener("change", function () {
      var pole = poles.find(function (p) { return String(p.PoleID) === select.value; });
      if (pole) {
        setCoordinates(pole.latitude, pole.longitude);
        if (centerMap) centerMap(pole.longitude, pole.latitude);
      }
    });
    el("drawField").addEventListener("click", function () {
      if (!startDraw) return;
      polygon = null;
      drawing = true;
      invalidate();
      clearGeometry(true);
      startDraw();
      revealOnSmallScreen(".map-panel");
      el("field-status").textContent = "Click each corner; double-click the last corner to finish.";
      el("clearField").textContent = "Cancel";
      mapStatus.textContent = "Drawing boundary · Double-click to finish, or use Cancel.";
      syncButton();
    });
    el("clearField").addEventListener("click", function () {
      if (stopDraw) stopDraw();
      polygon = null;
      drawing = false;
      if (clearGeometry) clearGeometry(true);
      el("field-status").textContent = "No field drawn. Select Draw boundary to begin.";
      el("drawField").textContent = "Draw boundary";
      el("clearField").textContent = "Clear";
      mapStatus.textContent = "Draw a field boundary to calculate its total water requirement.";
      invalidate();
    });

    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      if (!form.reportValidity() || drawing) return;
      if (mode() === "polygon" && !polygon) { el("form-error").textContent = "Draw a field boundary first."; return; }
      invalidate();
      var version = requestVersion;
      activeRequest = new AbortController();
      var body = new FormData(form);
      if (mode() === "polygon") body.set("polygon", JSON.stringify(polygon));
      el("water-needed").textContent = "Fetching today's weather…";
      el("result-summary").textContent = mode() === "polygon" ? "Sampling weather across your field and calculating total volume." : "Calculating for your selected point.";
      el("result-badge").textContent = "Calculating";
      document.querySelector(".results-panel").setAttribute("aria-busy", "true");
      syncButton();
      try {
        var response = await fetch(form.action, {
          method: "POST", credentials: "same-origin", signal: activeRequest.signal,
          headers: {"X-CSRFToken": form.querySelector("[name=csrfmiddlewaretoken]").value}, body: body
        });
        var data = await response.json();
        if (version !== requestVersion) return;
        if (!response.ok) throw new Error(data.error || "Calculation failed. Please try again.");
        el("result-badge").textContent = data.forecast_date + " · Forecast";
        if (data.mode === "polygon") {
          el("water-needed").textContent = number(data.total_water_m3, 2) + " m³/day for your field";
          el("result-summary").textContent = "Total estimated demand across " + data.sample_count + " area-weighted sample locations.";
          el("field-metrics").hidden = false;
          el("metric-area").textContent = number(data.area_hectares, 3) + " ha";
          el("metric-square-metres").textContent = number(data.area_m2, 1) + " m²";
          el("metric-depth").textContent = number(data.required_water, 2) + " mm/day";
          el("metric-volume").textContent = number(data.total_water_m3, 2) + " m³/day";
          el("metric-litres").textContent = number(data.total_water_litres, 0) + " litres/day";
          el("calculation-details").textContent = data.method + " Total = sum of each sample's water depth × represented area (1 mm over 1 m² = 1 litre). Rainfall effectiveness: " + data.rainfall_effectiveness + "%. " + data.source + " Retrieved: " + data.fetched_at;
          el("sample-rows").replaceChildren();
          data.samples.forEach(function (sample) {
            var row = document.createElement("tr");
            [sample.id, number(sample.area_m2 / 10000, 3), number(sample.required_water, 2), number(sample.volume_m3, 2)].forEach(function (value) {
              var cell = document.createElement("td"); cell.textContent = value; row.appendChild(cell);
            });
            el("sample-rows").appendChild(row);
          });
          el("sample-details").hidden = false;
          el("field-status").textContent = "Field area: " + number(data.area_hectares, 3) + " hectares · " + data.sample_count + " samples";
          if (showWeatherSamples) showWeatherSamples(data.samples);
          mapStatus.textContent = "Field calculated · Gold markers show the weather sample locations.";
        } else {
          el("water-needed").textContent = number(data.required_water, 2) + " mm/day";
          el("result-summary").textContent = "At " + data.latitude + ", " + data.longitude + " · " + data.timezone;
          el("calculation-details").textContent = "Estimate: max(0, " + data.reference_et + " × " + data.crop_coefficient + " − " + data.effective_rainfall + "). Rain: " + data.rainfall + " mm; assumed effective share: " + data.rainfall_effectiveness + "%. " + data.source + " Retrieved: " + data.fetched_at;
        }
        revealOnSmallScreen(".results-panel");
      } catch (err) {
        if (version !== requestVersion || err.name === "AbortError") return;
        el("water-needed").textContent = "Unable to calculate";
        el("result-summary").textContent = "Your selection is saved on the map. Please try again.";
        el("result-badge").textContent = "Needs attention";
        el("form-error").textContent = err.message;
      } finally {
        if (version === requestVersion) {
          activeRequest = null;
          document.querySelector(".results-panel").setAttribute("aria-busy", "false");
          syncButton();
        }
      }
    });
    el("btnCustomPrint").addEventListener("click", function () { window.print(); });
    fetch(spatialUrl, {credentials: "same-origin"}).then(function (response) {
      if (!response.ok) throw new Error("Unable to load local sample locations."); return response.json();
    }).then(function (data) {
      poles = data.poles;
      poles.forEach(function (pole) { var option = document.createElement("option"); option.value = pole.PoleID; option.textContent = pole.PoleSurveyNumber; select.appendChild(option); });
      el("data-status").textContent = poles.length + " synthetic sample locations · Your drawn field is used only for this calculation.";
      if (showPoles) showPoles();
    }).catch(function (error) { el("data-status").textContent = error.message; });

    var mapScript = document.createElement("script");
    mapScript.src = "https://js.arcgis.com/3.38/";
    mapScript.onerror = function () { mapStatus.textContent = "Map unavailable. Enter coordinates for a point calculation; drawing needs the map to load."; };
    mapScript.onload = function () {
      require([
        "esri/map", "esri/graphic", "esri/geometry/Point", "esri/symbols/SimpleMarkerSymbol",
        "esri/symbols/SimpleLineSymbol", "esri/Color", "esri/InfoTemplate", "esri/layers/GraphicsLayer",
        "esri/toolbars/draw", "esri/symbols/SimpleFillSymbol", "esri/geometry/webMercatorUtils", "dojo/domReady!"
      ], function (Map, Graphic, Point, SimpleMarkerSymbol, SimpleLineSymbol, Color, InfoTemplate, GraphicsLayer, Draw, SimpleFillSymbol, webMercatorUtils) {
        var map = new Map("mapDiv", {basemap: "satellite", center: [74.35, 31.63], zoom: 14});
        var samples = new GraphicsLayer({id: "sqliteDemoPoles"});
        var boundary = new GraphicsLayer({id: "selectedField"});
        var selectedPoint = new GraphicsLayer({id: "selectedPoint"});
        var weatherSamples = new GraphicsLayer({id: "fieldWeatherSamples"});
        map.addLayers([samples, boundary, selectedPoint, weatherSamples]);
        var toolbar = new Draw(map);
        function marker(colour, size) { return new SimpleMarkerSymbol(SimpleMarkerSymbol.STYLE_CIRCLE, size, new SimpleLineSymbol(SimpleLineSymbol.STYLE_SOLID, new Color("#ffffff"), 2), new Color(colour)); }
        var fieldSymbol = new SimpleFillSymbol(SimpleFillSymbol.STYLE_SOLID, new SimpleLineSymbol(SimpleLineSymbol.STYLE_SOLID, new Color("#b8e981"), 3), new Color([42, 119, 64, 0.28]));
        showPoles = function () {
          samples.clear();
          poles.forEach(function (pole) { samples.add(new Graphic(new Point(pole.longitude, pole.latitude), marker("#6c8f7a", 10), pole, new InfoTemplate("Synthetic sample location", "${PoleSurveyNumber}"))); });
        };
        showPoint = function (lon, lat) { selectedPoint.clear(); if (mode() === "point") selectedPoint.add(new Graphic(new Point(lon, lat), marker("#267457", 17))); };
        centerMap = function (lon, lat) { map.centerAt(new Point(lon, lat)); };
        clearGeometry = function (removeBoundary) { selectedPoint.clear(); weatherSamples.clear(); if (removeBoundary) boundary.clear(); };
        startDraw = function () { map.infoWindow.hide(); toolbar.activate(Draw.POLYGON); map.disableDoubleClickZoom(); };
        stopDraw = function () { toolbar.deactivate(); map.enableDoubleClickZoom(); };
        showWeatherSamples = function (points) {
          weatherSamples.clear();
          points.forEach(function (point) { weatherSamples.add(new Graphic(new Point(point.longitude, point.latitude), marker("#bd822b", 10), {label: "Sample " + point.id, depth: number(point.required_water, 2), area: number(point.area_m2 / 10000, 3)}, new InfoTemplate("${label}", "${depth} mm/day<br>Represents ${area} hectares"))); });
        };
        toolbar.on("draw-end", function (event) {
          stopDraw(); drawing = false;
          var geographic = webMercatorUtils.webMercatorToGeographic(event.geometry) || event.geometry;
          polygon = {type: "Polygon", coordinates: geographic.rings};
          boundary.clear(); boundary.add(new Graphic(event.geometry, fieldSymbol));
          el("field-status").textContent = "Boundary ready. Calculate to see area and total water volume.";
          el("drawField").textContent = "Redraw boundary";
          el("clearField").textContent = "Clear";
          mapStatus.textContent = "Field selected · Calculate to see its total daily requirement.";
          invalidate();
        });
        samples.on("click", function (event) {
          if (drawing || mode() !== "point") return;
          var pole = event.graphic.attributes; select.value = String(pole.PoleID); setCoordinates(pole.latitude, pole.longitude);
        });
        map.on("click", function (event) {
          if (drawing || mode() !== "point" || event.graphic) return;
          select.value = ""; setCoordinates(event.mapPoint.getLatitude(), event.mapPoint.getLongitude());
        });
        map.on("load", function () {
          mapReady = true; el("field-status").textContent = "Select Draw boundary to begin.";
          mapStatus.textContent = "Click a point, or choose Draw field to trace a boundary.";
          showPoint(Number(lonInput.value), Number(latInput.value)); syncButton();
        });
        map.on("error", function () { mapStatus.textContent = "Map could not load completely. Point calculations still work with entered coordinates."; });
        showPoles();
      }, function () { mapStatus.textContent = "Map tools could not load. You can still enter coordinates for a point calculation."; });
    };
    document.head.appendChild(mapScript);
  });
})();

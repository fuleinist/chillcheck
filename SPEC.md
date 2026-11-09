# SPEC - chillcheck

## 1. Problem

Deciduous fruit trees need a set number of cold hours each winter. This number is
the chill requirement of the variety. A warm winter gives a low chill total. The
tree then breaks dormancy late and unevenly. Fruit set drops. Fruit size drops.

Growers and home gardeners still choose varieties from old catalogues. Those
catalogues assume the climate of 1980. Winters in southern Australia have warmed.
Many popular varieties now sit near or below their chill limit.

No free tool answers one simple question for one address: which varieties still
work here, and which still work in 2050?

## 2. Goal

Give a grower one ranked list they can act on before they buy a tree. The tool
computes winter chill at a location from daily weather records. It compares the
result with the chill requirement of each variety. It repeats the test against a
2050 climate projection. Each variety gets a status: safe, marginal or at risk.

## 3. Users

- A home gardener who plans to buy two or three fruit trees this winter.
- A small orchardist who reviews the variety mix before replanting.
- A nursery or extension officer who answers "will this crop here?" questions.
- A council or landcare group that plans a community orchard.

## 4. Scope of the first release

### 4.1 In scope

1. Location input by place name, postcode, or latitude and longitude.
2. Winter season defined by hemisphere: May to September south, November to
   March north.
3. Daily minimum and maximum temperature for 30 complete seasons from the
   Open-Meteo Archive API. No API key.
4. Hourly temperature estimated from the daily pair with a piecewise cosine
   curve. Minimum at 05:00, maximum at 15:00.
5. Three chill metrics per season:
   - Chill hours: count of hours at 0 to 7.2 C.
   - Utah units: Richardson weights, including negative values above 15.9 C.
   - Chill portions: Dynamic Model of Erez, Fishman, Linsley-Noakes and Allan
     (1990).
6. A curated variety table with chill requirement ranges and source notes.
7. A match status for each variety at the baseline climate and at 2050.
8. A trend estimate in chill portions per decade.
9. A 2050 projection from the Open-Meteo Climate API, averaged over five
   seasons to reduce model noise.
10. A web UI with location search, summary cards, a season chart, and a
    variety table.
11. A CLI that prints the same assessment as text or JSON.
12. A JSON API for the web UI.

### 4.2 Out of scope

- Chill forcing models. The tool reports chill only.
- Per-variety rootstock, disease, or soil advice.
- Frost risk in spring.
- Pest and disease pressure.
- Any commercial recommendation to buy from a supplier.
- Irrigation and nutrition planning.

## 5. Data sources

| Source | Use | Cost |
| --- | --- | --- |
| Open-Meteo Archive API (`archive-api.open-meteo.com`) | Daily min and max temperature, ERA5 reanalysis | Free, no key |
| Open-Meteo Climate API (`climate-api.open-meteo.com`) | CMIP6 downscaled projection to 2050 | Free, no key |
| OpenStreetMap Nominatim (`nominatim.openstreetmap.org`) | Place name and postcode to coordinates | Free, no key |
| Open-Meteo Geocoding API (`geocoding-api.open-meteo.com`) | Place lookup fallback | Free, no key |
| Published chill requirement tables (UC Davis, NSW DPI) | Variety chill ranges | Public reference |

## 6. Model

### 6.1 Hourly temperature

Daily minimum and maximum temperatures are not enough for a chill model. The
Dynamic Model needs hourly values. The tool builds a continuous curve from
anchors at 05:00 (minimum) and 15:00 (maximum). A cosine half wave joins each
pair of anchors. This is the common sine or cosine method used in degree-day
work. It keeps the daily minimum and maximum exact.

### 6.2 Chill hours

Count the hours where temperature is at or above 0 C and at or below 7.2 C.
This is the unit that nursery tables use. It is a crude metric but it is the
only unit that can be compared with published requirements.

### 6.3 Utah units

Apply the Richardson (1974) weights per hour:

| Temperature (C) | Weight |
| --- | --- |
| below 1.4 | 0.0 |
| 1.4 to 2.4 | 0.5 |
| 2.4 to 9.1 | 1.0 |
| 9.1 to 12.4 | 0.5 |
| 12.4 to 15.9 | 0.0 |
| 15.9 to 18.0 | -0.5 |
| above 18.0 | -1.0 |

Sum the weights over the season. The result can be negative in a warm winter.

### 6.4 Chill portions

Implement the Dynamic Model exactly as published and as coded in the R package
`chillR` (`chilling.R`). Constants:

```
e0 = 4153.5
e1 = 12888.8
a0 = 139500
a1 = 2.567e18
slp = 1.6
tetmlt = 277
aa = a0 / a1
ee = e1 - e0
```

For each hour, with `TK` in kelvin:

```
ftmprt = slp * tetmlt * (TK - tetmlt) / TK
sr     = exp(ftmprt)
xi     = sr / (1 + sr)
xs     = aa * exp(ee / TK)
ak1    = a1 * exp(-e1 / TK)

S    = E_prev                        if E_prev < 1
S    = E_prev - E_prev * xi_prev     otherwise
E    = xs - (xs - S) * exp(-ak1)

if E >= 1:
    portions += E * xi
```

State carries across the whole season. The sum of the increments is the chill
portion total for the season.

### 6.5 Variety match

Each variety carries a chill requirement range in chill hours.

| Condition | Status |
| --- | --- |
| Season total at or above the upper bound | safe |
| Season total at or above the lower bound | marginal |
| Season total below the lower bound | at risk |

The same test runs against the baseline mean and the 2050 projection.

### 6.6 Model cross-check

The two metrics use different units. In a steady cold climate the ratio is about
30 chill hours per chill portion. Real sites differ. The report shows the
observed ratio for the location. A ratio below 6 marks a warm site, where the
hour count understates chill. A ratio above 45 marks a cold site. The report
adds a note in both cases. The tool never hides the disagreement.

### 6.7 Reanalysis model

The archive is read from ERA5 only. The default "best match" series changes
source around 2017. That change creates a step of a factor of five in the Sydney
chill hour record. A single model keeps the record homogeneous.

## 7. Acceptance criteria

1. `chillcheck --place "Orange NSW"` prints a report with baseline chill, recent
   chill, 2050 chill, and a variety table.
2. `chillcheck --lat -33.78 --lon 151.12 --json` returns valid JSON with the
   keys `location`, `baseline`, `recent`, `projection`, `varieties`, `notes`.
3. The Dynamic Model returns about 0.9 portions per day at a constant 6 C.
4. The Dynamic Model returns 0 portions at a constant 20 C.
5. The Utah model returns 1.0 per hour at 5 C and a negative value at 20 C.
6. Chill hours at a constant 5 C equals the number of hours in the series.
7. A southern location uses a May to September season. A northern location uses
   a November to March season.
8. The web UI accepts a place name and renders summary cards, a chart, and a
   variety table.
9. The API returns HTTP 200 for `/api/health` and `/api/assess`.
10. All tests pass with `python -m pytest`.

## 8. Verification plan

| Check | Method |
| --- | --- |
| Dynamic Model magnitude | Unit test at constant 6 C and constant 20 C |
| Utah weights | Unit test at 0, 5, 10, 14, 17, 20 C |
| Chill hours | Unit test at constant 5 C |
| Season window | Unit test at 45 N and 35 S |
| Projection parse | Unit test with a recorded response shape |
| End to end | Live run for Sydney and Orange |
| UI | Real screenshot from a local server |

## 9. Risks

- Variety tables differ between sources. Ranges are wide. The table states the
  source and the uncertainty.
- CMIP6 models disagree. The projection averages five seasons and one default
  model set. It is a planning signal, not a forecast.
- The cosine curve is a simplification. It cannot capture a warm night after a
  hot day. The Utah model can still go negative, so the error is bounded.
- Orographic effects matter in hill country. A grid cell may be cooler or
  warmer than the orchard. The report shows the grid elevation.

## 10. Kill criteria

Stop if the data APIs fail on three separate runs. Stop if the projection
cannot be fetched after two retries. Do not ship a report with invented data.
#!/bin/sh
# Pull the LFPG aerodrome extract from Overpass.
# Data (c) OpenStreetMap contributors, ODbL.
curl -s -m 240 -X POST -d @q.txt https://overpass-api.de/api/interpreter -o lfpg.json

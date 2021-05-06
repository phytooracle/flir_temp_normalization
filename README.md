# Temperature Normalization 

Calculates canopy temperature depression for single idenfitied plants from the FLIR pipeline.

## Execution instructions

### Command line

- REQUIRES: full folder of scanned data (contains subfolders with raw bin image and metadata)
- `-d`: date
- `-g, --geojson`: geojson containing plot boundaries
- `-s, --season`: season in the form of season_10_lettuce_yr_2020 OR season_11_sorghum_yr_2020
- `-t, --thermal`: individual thermal data extracted per plant
- example: `python3 merged.py 2020-03-03_subdir -g season10_multi_latlon_geno_up.geojson -s season_10_lettuce_yr_2020 -d 2020-03-03 -t 2020-03-03_indv_temps.csv`

### Docker 

- example: `sudo docker run --rm --mount "src=`pwd`,target=/mnt,type=bind" phytooracle/flir_temp_normalization 2020-03-03 -g /mnt/season10_multi_latlon_geno_up.geojson -s season_10_lettuce_yr_2020 -d 2020-03-03 -t /mnt/2020-03-03_indv_temps.csv`


### Singularity

- REQUIRES: clean Environmental Logger data (e.g. find data for season 10 at `https://datacommons.cyverse.org/browse/iplant/home/shared/phytooracle/season_10_lettuce_yr_2020/level_1/EnvironmentLogger`
- example: `singularity run -B $(pwd):/mnt --pwd /mnt docker://phytooracle/flir_temp_normalization 2020-02-03 -g season10_multi_latlon_geno_up.geojson -s season_10_lettuce_yr_2020 -d 2020-03-03 -t 2020-03-03_indv_temps.csv`



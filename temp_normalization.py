import os
import glob
import subprocess
import json
from terrautils.spatial import scanalyzer_to_latlon
import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import Polygon, Point
import urllib.request
import argparse

#----------------------------------

def get_args():
    """Get command-line arguments"""

    parser = argparse.ArgumentParser(
        description='Individual plant temperature extraction',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('dir',
                        metavar='dir',
                        help='Directory containing geoTIFFs')

    parser.add_argument('-g',
                        '--geojson',
                        help='GeoJSON containing plot boundaries',
                        metavar='geojson',
                        type=str,
                        default=None,
                        required=True)

    parser.add_argument('-s',
                        '--season',
                        help=' "season_10_lettuce_yr_2020" OR "season_11_sorghum_yr_2020" ',
                        metavar='season',
                        type=str,
                        default=None,
                        required=True)

    parser.add_argument('-d',
                        '--date',
                        help='date to process, usually the same as dir',
                        metavar='date',
                        type=str,
                        default=None,
                        required=True)

    parser.add_argument('-t',
                        '--thermal',
                        help=' "extracted thermal data from pipeline" ',
                        metavar='thermal',
                        type=str,
                        default=None,
                        required=True)

    return parser.parse_args()

#----------------------------------

## Gathers gantry x, y, z, coordinates as well as time
## Converts coordinates to lat lon
def md_shp():

    args = get_args()

    # Load required files as well as files to process
    pathlist = glob.glob(f'{args.dir}/*/*.json')
    print(pathlist)
    shp = gpd.read_file(f'{args.geojson}')
    print(shp)
    # print(pathlist)
    JSON_path_list = []
    for path in pathlist:
        path_str = str(path)
        JSON_path_list.append(path_str)

    # Create dictionary and populates it
    JSON_dict = {}
    cnt = 0
    # JSON_dict[time, filename, gantry_x, gantry_y, gantry_z] = "Date, Time, Gantry_x, Gantry_y, Gantry_z"
    for i in JSON_path_list:
        with open(i) as f:
            cnt += 1
            meta = json.load(f)['lemnatec_measurement_metadata']
            time = (meta['gantry_system_variable_metadata']['time'])
            filename = i.split('/')[-1]
            # Gantry loc metadata
            gantry_x = float(meta['gantry_system_variable_metadata']['position x [m]'])
            gantry_y = float(meta['gantry_system_variable_metadata']['position y [m]'])
            gantry_z = float(meta['gantry_system_variable_metadata']['position z [m]'])
            
            # Sensor loc metadata
            sens_x = float(meta['sensor_fixed_metadata']['location in camera box x [m]'])
            sens_y = float(meta['sensor_fixed_metadata']['location in camera box y [m]'])
            sens_z = float(meta['sensor_fixed_metadata']['location in camera box z [m]'])
            #  gantry_x_pos = 
            z_offset = 0.76
            sens_loc_x = gantry_x + sens_x
            sens_loc_y = gantry_y + sens_y
            sens_loc_z = gantry_z + z_offset + sens_z #offset in m
            fov_x, fov_y = float(meta['sensor_fixed_metadata']['field of view x [m]']), float(meta['sensor_fixed_metadata']['field of view y [m]'])
            B = sens_loc_z
            A_x = np.arctan((0.5*float(fov_x))/2)
            A_y = np.arctan((0.5*float(fov_y))/2)
            L_x = 2*B*np.tan(A_x)
            L_y = 2*B*np.tan(A_y)
            x_n = sens_loc_x + (L_x/2)
            x_s = sens_loc_x - (L_x/2)
            y_w = sens_loc_y + (L_y/2)
            y_e = sens_loc_y - (L_y/2)
            bbox_nw_latlon = scanalyzer_to_latlon(x_n, y_w)
            bbox_se_latlon = scanalyzer_to_latlon(x_s, y_e)

            # TERRA-REF
            lon_shift = 0.000020308287

            # Drone
            lat_shift = 0.000018292 #0.000015258894
            b_box =  ( bbox_se_latlon[0] - lat_shift,
                        bbox_nw_latlon[0] - lat_shift,
                        bbox_nw_latlon[1] + lon_shift,
                        bbox_se_latlon[1] + lon_shift)

            JSON_dict[cnt] = {
                "time": time,
                "filename": filename,
                # "gantry_x": gantry_x,
                # "gantry_y": gantry_y,
                # "gantry_z": gantry_z,
                # "sens_x": sens_loc_x,
                # "sens_y": sens_loc_y,
                # "sens_z": sens_loc_z,
                "gantry_x": sens_loc_x,
                "gantry_y": sens_loc_y,
                "gantry_z": sens_loc_z,
                "b_box": b_box}
            #  filename = os.path.basename(metadata)
    # JSON_df = pd.DataFrame.from_dict(JSON_dict, orient='index', columns=['time','filename','gantry_x','gantry_y','gantry_z', 'sens_x', 'sens_y', 'sens_z', 'b_box'])
    JSON_df = pd.DataFrame.from_dict(JSON_dict, orient='index', columns=['time','filename','gantry_x','gantry_y','gantry_z', 'b_box'])


    # Converts gantry/scanners location to lat lon
    GPS_latlon = scanalyzer_to_latlon(JSON_df['gantry_x'], JSON_df['gantry_y'])
    GPS_latlon_df = pd.DataFrame(GPS_latlon).transpose()
    GPS_latlon_df.columns = ['GPS_lat', 'GPS_lon']

    # Creates polygons for plots    
    polygon_list = []

    for i, row in JSON_df.iterrows():
        bbox = JSON_df['b_box'].loc[i]
        polygon = Polygon([[bbox[2], bbox[1]], [bbox[3], bbox[1]], [bbox[3], bbox[0]], [bbox[2], bbox[0]]])
        polygon_list.append(polygon)

    JSON_df['bbox_geometry'] = polygon_list

    JSON_df['time'] = pd.to_datetime(JSON_df.time)
    JSON_df = JSON_df.sort_values(by ='time')

    # Function in function! There's gotta be a better way...
    # Intersects polygons with shapefile
    def intersection(bbox_polygon):
        intersects = bbox_polygon.intersects
        plot = None
        intersection_list = []
        for i, row in shp.iterrows():
            plot_polygon = row['geometry']
            intersection = intersects(plot_polygon)
            if intersection == True:
                plot = [row['ID']]
                intersection_list.append(plot)
        return intersection_list

    JSON_df["plot"] = None
    for i, row in JSON_df.iterrows():
        bbox_polygon = row['bbox_geometry']
        print(bbox_polygon)
        plot = intersection(bbox_polygon)
        JSON_df.at[i,'plot'] = plot

    print(JSON_df)
    # JSON_df.to_csv("JSONdf.csv")

    return JSON_df

#----------------------------------

def Env_data():
    # Env logger data
    args = get_args()    
    command = f'iget -rKTPf -N 0 /iplant/home/shared/phytooracle/{args.season}/level_1/EnvironmentLogger/{args.date}_clean.tar.gz'
    subprocess.call(command, shell = True)
    command = f'tar -xvf {args.date}_clean.tar.gz'
    subprocess.call(command, shell = True)

## Retrieve csv data and organize/clean up
    EnvL_data = pd.read_csv(f'./{args.date}_clean.csv')
    EnvL_data['Time'] = pd.to_datetime(EnvL_data['Time'])
    Envlog_clean = EnvL_data[['Time', 'Sun Direction', 'Temperature', 'Photosynthetically active radiation', 'Wind velocity']]
    return Envlog_clean

#----------------------------------
def AZMget(JSON_df):
    args = get_args()
    season = args.season

    if season == "season_10_lettuce_yr_2020" or season == "season_11_sorghum_yr_2020":
        url = "https://cals.arizona.edu/azmet/data/0620rh.txt"
    else:
        url = "https://cals.arizona.edu/azmet/data/0621rh.txt"


    urllib.request.urlretrieve(url, 'AZmet_2020data_req.csv')
    AZmet_data = pd.read_csv("AZmet_2020data_req.csv", names = ["Year", "Day", "Hour", 
                                            "Air Temperature", "Relative Humidity", 
                                            "VPD", "Solar Radiation", "Precipitation", 
                                            "4 inch Soil T", "12 inch Soil T", 
                                            "Avg Wind Speed", "Wind Vector Magnitude", 
                                            "Wind Vector Direction", "Wind Direction STDEV", 
                                            "Max Wind Speed", "Reference Evapotranspiration", 
                                            "Actual Vapor Pressure", "Dewpoint"])
    print("Document downloaded, loaded")

    AZMet_df = pd.DataFrame(AZmet_data)

    AZMet_df['combined'] = AZMet_df["Year"]*1000 + AZMet_df["Day"]
    AZMet_df["date"] = pd.to_datetime(AZMet_df["combined"], format = "%Y%j")

    AZMet_df['date'] = pd.to_datetime(AZMet_df['date'])
    AZMet_df['Hour'] = pd.to_timedelta(AZMet_df['Hour'], unit='h')
    AZMet_df['date'] = AZMet_df['date'] + AZMet_df['Hour']
    AZMet_df = AZMet_df.set_index('date')

    del AZMet_df['combined']
    del AZMet_df['Year']
    del AZMet_df['Day']
    del AZMet_df['Hour']

    image_file = JSON_df
    image_file['time'] = pd.to_datetime(image_file['time'])
    AZmet_dict = {}
    AZMet_df.to_csv("needtoupder.csv")

    EL = Env_data()
    EL = EL.set_index('Time')
    # EL
    def azmet_dict(image_file):
        cnt = 0
        for i, row in image_file.iterrows():
            cnt += 1
            time = row['time'].round('H')
            result_index = time
            print(result_index)

            AZmet_temp = AZMet_df['Air Temperature'].loc[f'{result_index}']
            AZmet_wind = AZMet_df['Avg Wind Speed'].loc[f'{result_index}']
            AZmet_vpd = AZMet_df['VPD'].loc[f'{result_index}']
            AZmet_solar = AZMet_df['Solar Radiation'].loc[f'{result_index}']
            AZmet_rh = AZMet_df['Relative Humidity'].loc[f'{result_index}']
            Env_temp = EL['Temperature'].loc[f'{result_index}']
            Env_wind = EL['Wind velocity'].loc[f'{result_index}']
            AZmet_dict[cnt] = {'azmet_atm_temp': AZmet_temp, 'azmet_wind_velocity': AZmet_wind, 'azmet_VPD': AZmet_vpd, 'azmet_solar_radiation':
                            AZmet_solar, 'relative_humidity': AZmet_rh, 'env_temp': Env_temp, 'env_wind': Env_wind}
            print(f'Building AZMet dict:{cnt}/{len(image_file)}')
        return pd.DataFrame.from_dict(AZmet_dict)

    environmental_df = azmet_dict(image_file)
    environmental_df = environmental_df.transpose()
    # environmental_df
    image_file['azmet_atm_temp'] = environmental_df['azmet_atm_temp']
    image_file['azmet_wind_velocity'] = environmental_df['azmet_wind_velocity']
    image_file['azmet_VPD'] = environmental_df['azmet_VPD']
    image_file['azmet_solar_radiation'] = environmental_df['azmet_solar_radiation']
    image_file['relative_humidity'] = environmental_df['relative_humidity']
    image_file['env_temp'] = environmental_df['env_temp']
    image_file['env_wind'] = environmental_df['env_wind']
    full_image_file_mod = image_file[['time', 'filename', 'azmet_atm_temp', 'azmet_wind_velocity', 'azmet_VPD', 
                                        'azmet_solar_radiation', 'relative_humidity', 'env_temp','env_wind']]

    image_file.to_csv('imagefile_req.csv') #############################################OUTPUTS


    print('done buidling AZMet dict.')

    return image_file, full_image_file_mod

#----------------------------------

def all_temp_in(image_file):
    all_temp = pd.read_csv('imagefile_req.csv') #########################################INPUT

    def clean_alt_list(list_):
        list_ = list_.replace('[', '')
        list_ = list_.replace(']', '')
        return list_
    
    print("Let's get this figured out")
    
    print(all_temp)

    all_temp['plot'] = (all_temp['plot'].apply(clean_alt_list)).apply(eval)
    return all_temp

#----------------------------------

def expand_plots(all_temp):
    plot_expand = all_temp['plot'].apply(pd.Series)
    print('image_file loaded')
    plot_expand['time'] = all_temp['time']
    plot_expand['filename'] = all_temp['filename']
    plot_expand['env_temp'] = all_temp['env_temp']
    plot_expand['env_wind'] = all_temp['env_wind']
    plot_expand['azmet_atm_temp'] = all_temp['azmet_atm_temp']
    plot_expand['azmet_wind_velocity'] = all_temp['azmet_wind_velocity']
    plot_expand['azmet_VPD'] = all_temp['azmet_VPD']
    plot_expand['azmet_solar_radiation'] = all_temp['azmet_solar_radiation']
    plot_expand['relative_humidity'] = all_temp['relative_humidity']
    stacked = plot_expand.set_index(['time', 'filename', 'env_temp', 'env_wind', 'azmet_atm_temp', 'azmet_wind_velocity',
                                    'azmet_VPD', 'azmet_solar_radiation', 'relative_humidity']).stack()
    stack_df = pd.DataFrame(stacked).reset_index()
    del stack_df['level_9']
    final_df = stack_df.rename(columns = {0:'Plot'})
    return final_df


#----------------------------------

def main():
    args = get_args()
    season = args.season
    # md_shp()
    Env_data()
    AZMet_data = AZMget(md_shp())

    finale_df = expand_plots(all_temp_in(AZMet_data[0]))
    env_logger = AZMet_data[1].set_index('filename')
    finale_df_mod = finale_df[['filename', 'Plot']]
    print("Im through!")

    img_plot = finale_df_mod
    img_plot.columns = ['image', 'plot']
    ######

    img_plot['time'] = img_plot['azmet_atm_temp'] = img_plot['azmet_wind_velocity'] = img_plot['azmet_VPD'] = img_plot['azmet_solar_radiation'] = img_plot['relative_humidity'] = img_plot['env_temp'] = img_plot['env_wind'] = None

    for i, row in img_plot.iterrows():
        meta = row['image']
        try:
            datetime = env_logger.loc[meta, 'time']
            print(datetime)
            azmet_temp = env_logger.loc[meta, 'azmet_atm_temp']
            azmet_wind_vel = env_logger.loc[meta, 'azmet_wind_velocity']
            azmet_vpd = env_logger.loc[meta, 'azmet_VPD']
            sol_rad = env_logger.loc[meta, 'azmet_solar_radiation']
            temp = env_logger.loc[meta, 'env_temp']
            win_vel = env_logger.loc[meta, 'env_wind']
            rel_hum = env_logger.loc[meta, 'relative_humidity']
            
            img_plot.at[i, 'time'] = datetime
            img_plot.at[i, 'azmet_atm_temp'] = azmet_temp
            img_plot.at[i, 'azmet_wind_velocity'] = azmet_wind_vel
            img_plot.at[i, 'azmet_VPD'] = azmet_vpd
            img_plot.at[i, 'azmet_solar_radiation'] = sol_rad
            img_plot.at[i, 'env_temp'] = temp
            img_plot.at[i, 'env_wind'] = win_vel
            img_plot.at[i, 'relative_humidity'] = rel_hum
            
        except:
            pass

    df_agg = img_plot.drop(['image'], axis=1)#.set_index('plot')#.groupby('plot')
    print(df_agg['time'])

    ## Creates a dictionary that goes through the merged dataframe and calculates different statistical values for the data
    temp_dict = {}
    cnt = 0

    for plot in df_agg['plot'].unique().tolist():
        try:
            cnt += 1 

            select_df = df_agg.set_index('plot').loc[plot]

            if season == "season_10_lettuce_yr_2020":

                time = select_df['time'].to_string()
                firstDelPos=time.find("MAC")
                secondDelPos=time.find("202")
                time = time.replace('plot', '').replace(time[firstDelPos:secondDelPos], '').replace("\n", ' ')
                print(time)

            if season == "season_11_sorghum_yr_2020":

                time = select_df['time'].to_string()
                time = time.replace('plot', '').replace("\n", ' ').replace('    ', ' ')
                print(time)

            temp_median = select_df['azmet_atm_temp'].median()
            temp_mean = select_df['azmet_atm_temp'].mean()
            temp_std = select_df['azmet_atm_temp'].std()
            
            azmet_wind_vel = select_df['azmet_wind_velocity'].median()
            azmet_vpd = select_df['azmet_VPD'].median()
            sol_rad = select_df['azmet_solar_radiation'].median()
            temp = select_df['env_temp'].median()
            wind_vel = select_df['env_wind'].median()
            rel_hum = select_df['relative_humidity'].median()
            
            #print(temp_median)
            temp_dict[cnt] = {'plot': plot,
                            'time': time,
                            'median': temp_median,
                            'mean': temp_mean, 
                            'std_dev': temp_std, 
                            'azmet_wind_velocity': azmet_wind_vel, 
                            'azmet_VPD': azmet_vpd, 
                            'azmet_solar_radiation': sol_rad, 
                            'env_temp': temp, 
                            'env_wind': wind_vel,
                            'relative_humidity': rel_hum}
        except:
            pass

    ## Converts dictionary with stats into a dataframe and sets the plot as the index
    result = pd.DataFrame.from_dict(temp_dict, orient='index').set_index('plot')
    # result.to_csv("result.csv")

    ## Reads in the csv with the individual plant temperatures (produced by the pipeline)
    plant_detections = pd.read_csv(args.thermal)

    ## Adds the field information and PCT values to the already existing csv that is indexed by plot
    plant_detections['norm_temp'] = plant_detections['atm_temp'] = None

    for i, row in plant_detections.iterrows():

        if season == "season_11_sorghum_yr_2020":

            try:
                plot = row['plot'] #.replace('_', ' ')
                plot = str(plot)

                plant_temp = row['median']
                # print(plant_temp)
                # print(plot)
                # print(result.loc[plot]) #######
                # result.loc[plot]
                
                temp_df = result.loc[plot]
                atm_temp = temp_df['median']
                norm_temp =  atm_temp - (plant_temp - 273.15)
                azmet_wind_vel = temp_df['azmet_wind_velocity']
                azmet_vpd = temp_df['azmet_VPD']
                sol_rad = temp_df['azmet_solar_radiation']
                temp = temp_df['env_temp']
                wind_vel = temp_df['env_wind']
                rel_hum = temp_df['relative_humidity']
                
                plant_detections.at[i, 'norm_temp'] = norm_temp
                plant_detections.at[i, 'atm_temp'] = atm_temp
                # # print(plant_detections['atm_temp'])
                
                plant_detections.at[i, 'azmet_wind_velocity'] = azmet_wind_vel
                plant_detections.at[i, 'azmet_VPD'] = azmet_vpd
                plant_detections.at[i, 'azmet_solar_radiation'] = sol_rad
                plant_detections.at[i, 'env_temp'] = temp
                plant_detections.at[i, 'env_wind'] = wind_vel
                plant_detections.at[i, 'relative_humidity'] = rel_hum
                plant_detections.at[i, 'date'] = temp_df['time']
                print(plant_detections['date'])

                print(atm_temp)
            except:
                print("Skipping specific plot as there is no data found.")
                pass

        if season == "season_10_lettuce_yr_2020":

            try:
                plot = row['plot'] #.replace('_', ' ')
                plot = str(plot)

                plant_temp = row['median']
                
                temp_df = result.loc[plot]
                atm_temp = temp_df['median']
                norm_temp =  atm_temp - (plant_temp - 273.15)
                azmet_wind_vel = temp_df['azmet_wind_velocity']
                azmet_vpd = temp_df['azmet_VPD']
                sol_rad = temp_df['azmet_solar_radiation']
                temp = temp_df['env_temp']
                wind_vel = temp_df['env_wind']
                rel_hum = temp_df['relative_humidity']
                
                plant_detections.at[i, 'norm_temp'] = norm_temp
                plant_detections.at[i, 'atm_temp'] = atm_temp
                # # print(plant_detections['atm_temp'])
                
                plant_detections.at[i, 'azmet_wind_velocity'] = azmet_wind_vel
                plant_detections.at[i, 'azmet_VPD'] = azmet_vpd
                plant_detections.at[i, 'azmet_solar_radiation'] = sol_rad
                plant_detections.at[i, 'env_temp'] = temp
                plant_detections.at[i, 'env_wind'] = wind_vel
                plant_detections.at[i, 'relative_humidity'] = rel_hum
                plant_detections.at[i, 'date'] = temp_df['time']
                print(plant_detections['date'])

                print(atm_temp)
            except:
                print("Skipping specific plot as there is no data found.")
                pass
            
    print("done")
    plant_detections.to_csv(f'{args.date}_indiv_temp_depression.csv')

#----------------------------------
if __name__ == '__main__':
    main()

import pandas as pd
import folium
from folium.plugins import MousePosition
import branca
import requests
import streamlit as st
from streamlit_folium import folium_static
from datetime import date, datetime, timedelta, timezone
from streamlit_autorefresh import st_autorefresh
import streamlit.components.v1 as components
from streamlit_javascript import st_javascript
import pytz
import time

# TODO: Fix timezone switch

def utc_to_local(utc_dt):
    return utc_dt.replace(tzinfo=timezone.utc).astimezone(tz=None)


@st.cache_data
def get_earthquake_data(params):
    req_url = f'https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson'

    if 'start_time' in params:
        req_url += f'&starttime={params["start_time"]}'

    if 'end_time' in params:
        req_url += f'&endtime={params["end_time"]}'

    if 'limit' in params:
        limit = params['limit']
        req_url += f'&limit={limit}'
    
    if 'order' in params:
        req_url += f'&orderby={params["order"]}'

    if 'min_magnitude' in params:
        min_magnitude = params['min_magnitude']
        max_magnitude = params['max_magnitude']
        req_url += f'&minmagnitude={min_magnitude}&maxmagnitude={max_magnitude}'

    if 'min_depth' in params:
        min_depth = params['min_depth']
        max_depth = params['max_depth']
        req_url += f'&mindepth={min_depth}&maxdepth={max_depth}'

    use_circle_search = params['use_circle_search']
    circle_lat = params['circle_lat']
    circle_long = params['circle_long']
    circle_radius = params['circle_radius']
    
    if use_circle_search:
        if (circle_lat is not None) & (circle_long is not None) & (circle_radius is not None):
            req_url += f'&latitude={circle_lat}&longitude={circle_long}&maxradiuskm={circle_radius}'
        else:
            return None

    dataset = requests.get(req_url).json()
    if dataset['metadata']['count'] < 1:
        return None
    features = dataset['features']
    titles = []
    mags = []
    times = []
    lats = []
    longs = []
    depths = []
    urls = []

    for feature in features:
        titles.append(feature['properties']['title'])
        mags.append(feature['properties']['mag'])
        times.append(pd.to_datetime(feature['properties']['time'], unit='ms').strftime('%y/%m/%d %H:%M:%S'))
        lats.append(feature['geometry']['coordinates'][1])
        longs.append(feature['geometry']['coordinates'][0])
        depths.append(feature['geometry']['coordinates'][2])
        urls.append(feature['properties']['url'])

    df = pd.DataFrame({
        'title': titles,
        'magnitude': mags,
        'depth': depths,
        'date_time': times,
        'latitude': lats,
        'longitude': longs,
        'url': urls
    })
    return df

def get_plate_boundaries():
    geo_json_url = 'https://raw.githubusercontent.com/fraxen/tectonicplates/master/GeoJSON/PB2002_boundaries.json'
    boundaries = folium.GeoJson(
            geo_json_url,
            name='Plate Boundaries',
            style_function=lambda feature: {
                    "color": "red",
                    "weight": 0.75,
                    "dashArray": "5, 5",
                },
        )
    return boundaries

def get_earthquake_map(df, show_pbounds=False, utc_time=False):
    min_zoom = 2
    
    tile_graysale = folium.TileLayer(
        tiles = 'cartodb positron',
        attr = '© OpenStreetMap contributors © CARTO',
        name = 'Grayscale',
        overlay = False,
        control = True,
        min_zoom=min_zoom
       )
    
    m = folium.Map(location=[0, 0], tiles=tile_graysale, zoom_start=2, min_zoom=min_zoom, control_scale=True)

    folium.TileLayer(
        tiles = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr = 'Powered by Esri',
        name = 'Satellite',
        overlay = False,
        control = True,
        show=False,
        min_zoom=min_zoom
       ).add_to(m)
    
    folium.TileLayer(
        tiles="openstreetmap",
        attr='© OpenStreetMap contributors',
        name='Street',
        overlay=False,
        control=True,
        show=False,
        min_zoom=min_zoom
    ).add_to(m)


    for _, row in df.iterrows():
        if row.depth > 500:
            fcolor = 'red'
        elif row.depth > 300:
            fcolor = 'orange'
        elif row.depth > 150:
            fcolor = 'yellow'
        elif row.depth > 70:
            fcolor = 'green'
        elif row.depth > 35:
            fcolor = 'blue'
        else:
            fcolor = 'purple'
        
        if row.latitude > 0:
            ns_hem = 'N'
        elif row.latitude < 0:
            ns_hem = 'S'
        else:
            ns_hem = ''

        if row.longitude > 0:
            we_hem = 'E'
        elif row.longitude < 0:
            we_hem = 'W'
        else:
            we_hem = ''

        if utc_time:
            earthquake_time = datetime.strptime(row.date_time, '%y/%m/%d %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S (UTC%z)')
        else:
            earthquake_time = utc_to_local(datetime.strptime(row.date_time, '%y/%m/%d %H:%M:%S')).astimezone().strftime('%Y-%m-%d %H:%M:%S (UTC%z)')
        
        popup_html = f"""
            <div style="font-family: Arial;">
                <h3><a href={row.url} target="_top">{row.title}</a></h3>
                <font color="grey">Time:</font> {earthquake_time}<br>
                <font color="grey">Location:</font> {round(abs(row.latitude), 3)}&deg{ns_hem} {round(abs(row.longitude), 3)}&deg{we_hem}<br>
                <font color="grey">Depth:</font> {round(row.depth, 1)} km
            </div>
        """

        popup = folium.Popup(branca.element.IFrame(html=popup_html, width=320, height=150))
            
        folium.CircleMarker(
            location=[row.latitude, row.longitude],
            radius=round(abs(row.magnitude)) + 1,
            color='black',
            opacity=1.0,
            weight=1.0,
            fill_color=fcolor,
            fill_opacity=1.0,
            popup=popup
        ).add_to(m)

    if show_pbounds:
        plate_boundaries = get_plate_boundaries()
        plate_boundaries.add_to(m)

    folium.LayerControl().add_to(m)

    formatter = "function(num) {return L.Util.formatNum(num, 3) + ' &deg; ';};"
    MousePosition(
        lat_formatter=formatter,
        lng_formatter=formatter,
    ).add_to(m)

    return m

def get_map(params):
    df = get_earthquake_data(params)
    if df is not None:
        map = get_earthquake_map(df, params['show_pbounds'], params['use_utc'])
        return map
    else:
        print('No earthquakes found! Please change selection options.')
        return None

def app():
    st.set_page_config(page_title="Interactive Earthquake Map", layout="wide")
    st.markdown(f"""
        <style>
        iframe {{
            width: inherit;
        }}
        </style>
    """
    , unsafe_allow_html=True)

    st.title("Interactive Earthquake Map")

    
    data_params = {
        'use_circle_search': False,
        'circle_lat': 0,
        'circle_long': 0,
        'circle_radius': 2,
        'use_utc': False
    }

    with st.popover("Legend"):
        st.caption("Magnitude")
        components.html(
            """
            <div id='maplegend' class='maplegend' 
                style='position: absolute; z-index: 9999; background-color: rgba(255, 255, 255, 0.5);
                padding: 10px; font-size: 10.5px; left: 0; top: 0;'>
                <svg xmlns="http://www.w3.org/2000/svg" width="180" height="40">
                    <circle cx="10" cy="9" r="9" fill="gray" stroke="black"/>
                    <circle cx="30" cy="9" r="8" fill="gray" stroke="black"/>
                    <circle cx="50" cy="9" r="7" fill="gray" stroke="black"/>
                    <circle cx="70" cy="9" r="6" fill="gray" stroke="black"/>
                    <circle cx="90" cy="9" r="5" fill="gray" stroke="black"/>
                    <circle cx="110" cy="9" r="4" fill="gray" stroke="black"/>
                    <circle cx="130" cy="9" r="3" fill="gray" stroke="black"/>
                    <circle cx="150" cy="9" r="2" fill="gray" stroke="black"/>
                    <circle cx="170" cy="9" r="1" fill="gray" stroke="black"/>
                </svg>
                <div class="number-2" style="left: 20px;">9</div>
                <div class="number-2" style="left: 40px;">8</div>
                <div class="number-2" style="left: 60px;">7</div>
                <div class="number-2" style="left: 80px;">6</div>
                <div class="number-2" style="left: 100px;">5</div>
                <div class="number-2" style="left: 120px;">4</div>
                <div class="number-2" style="left: 140px;">3</div>
                <div class="number-2" style="left: 160px;">2</div>
                <div class="number-2" style="left: 180px;">1</div>
                
            </div>
            <style type='text/css'>
                .mag-legend {
                    position: relative;
                    width: 180px;
                    height: 60px;
                }
                .number-2 {
                    position: absolute;
                    bottom: 15px;
                    transform: translateX(-50%);
                    font-size: 12px;
                    color: #333;
                    font-family: Arial
                }
            </style>
            """,
        height=60)
        st.caption("Depth (km)")
        components.html(
            """
            <div id='maplegend' class='maplegend' 
                style='position: absolute; z-index: 9999; background-color: rgba(255, 255, 255, 0.5);
                padding: 10px; font-size: 10.5px; left: 0px; bottom: 0px;'>
                <div class="colormap-container">
                    <div class="colormap"></div><br>
                    <div class="number" style="left: 0px;">0</div>
                    <div class="number" style="left: 4%;">35</div>
                    <div class="number" style="left: 9%;">70</div>
                    <div class="number" style="left: 20%;">150</div>
                    <div class="number" style="left: 38%;">300</div>
                    <div class="number" style="left: 63%;">500</div>
                    <div class="number" style="left: 100%;">800</div>
                </div>
            </div>
                <style type='text/css'>
                .mag-legend {
                    position: relative;
                    width: 180px;
                    height: 40px;
                }
                .colormap-container {
                    position: relative;
                    width: 250px;
                    height: 25px;
                    margin-right: 10px;
                    float: left;
                }

                .colormap {
                    width: 250px;
                    height: 10px;
                    background: linear-gradient(to right, 
                        #a020f0 0%,
                        #a020f0 4.3756%,
                        #0000ff 4.375%,
                        #0000ff 8.75%,
                        #008000 8.75%,
                        #008000 18.75%, 
                        #ffff00 18.75%,
                        #ffff00 37.5%,
                        #ffa500 37.5%,
                        #ffa500 62.5%,
                        #ff0000 62.5%,
                        #ff0000 100%
                    );
                }

                /* Define the number divs */
                .number {
                    position: absolute;
                    bottom: 0;
                    left: 70%;
                    transform: translateX(-50%);
                    font-size: 9px;
                    color: #333;
                    font-family: Arial
                }

                </style>
            """,
        height=40)

    with st.sidebar:
        with st.expander('Limits', expanded=True):
            limit_lst = [
                10, 20, 50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000,
                1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 10000, 20000
            ]
            data_params['limit'] = st.selectbox('Max earthquakes', limit_lst, index=limit_lst.index(1000))
            order = st.selectbox('Select earthquakes by',
                                ['Newest', 'Largest'])

            if order == 'Newest':
                data_params['order'] = 'time'
            else:
                data_params['order'] = 'magnitude'



        with st.expander('Period'):
            time_range = st.radio(
                "Select time range:",
                ["Today", "This week", "This month", "This year", "All time", "Custom range"])
            
            #select_earliest = st.checkbox('Earliest Available', True)


            #select_latest = st.checkbox('Latest Available', True)
            today = date.today()
            today2 = datetime.now().isoformat()
            if time_range == "Today":
                data_params['start_time'] = datetime.combine(today, datetime.min.time()).isoformat()
                data_params['end_time'] = today2
            elif time_range == "This week":
                dt = datetime.combine(today, datetime.min.time())
                data_params['start_time'] = (dt - timedelta(days=dt.weekday())).isoformat()
                data_params['end_time'] = today2
            elif time_range == "This month":
                data_params['start_time'] = datetime.combine(today.replace(day=1), datetime.min.time())
                data_params['end_time'] = today2
            elif time_range == "This year":
                data_params['start_time'] = datetime.combine(today.replace(day=1, month=1), datetime.min.time())
                data_params['end_time'] = today2
            elif time_range == "Custom range":
                yesterday = datetime.combine(today, datetime.min.time()) - timedelta(1)
                start_time = st.date_input('From', value=yesterday)
                end_time = st.date_input('To', value='today')
                data_params['start_time'] = start_time.isoformat()
                data_params['end_time'] = end_time.isoformat()
            else:
                pass

        with st.expander('Magnitude Range', expanded=False):
            select_mag = st.checkbox('All Values', value=True, key="chk_mag")
            mag_min = st.number_input('Min', min_value=0, max_value=9, value=0, disabled=select_mag)
            mag_max = st.number_input('Max', min_value=1, max_value=10, value=10, disabled=select_mag)
            if not select_mag:
                data_params.update({
                    'min_magnitude': mag_min,
                    'max_magnitude': mag_max,
                })

        with st.expander('Depth Range', expanded=False):
            select_depth = st.checkbox('All Values', value=True, key="chk_depth")
            depth_min = st.number_input('Min', min_value=0, max_value=799, value=0, disabled=select_depth)
            depth_max = st.number_input('Max', min_value=1, max_value=800, value=800, disabled=select_depth)
            if not select_depth:
                data_params.update({
                    'min_depth': depth_min,
                    'max_depth': depth_max,
                })

        data_params['show_pbounds'] = st.checkbox('Show Plate Boundaries')

        
    col1, col2 = st.columns([0.8, 0.2])

    tz = st_javascript("""await (async () => {
                const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
                console.log(userTimezone)
                return userTimezone
    })().then(returnValue => returnValue)""")

    time.sleep(1)

    with col2:
        ar = st.checkbox('Auto Update', key="chk_ar")
        if data_params['use_utc']:
            st.caption(datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S (UTC%z)'))
        else:
            st.caption(datetime.now(pytz.timezone(tz)).strftime('%Y-%m-%d %H:%M:%S (UTC%z)'))
        if ar:
            st_autorefresh(interval=1*60*1000)
        if st.button("Refresh Earthquakes", disabled=ar):
            st.rerun()


        time_zone = st.radio(
            "Select time zone:",
            ["User Time Zone", "UTC"])
        if time_zone == "User Time Zone":
            data_params['use_utc'] = False
        else:
            data_params['use_utc'] = True

    with col1:
        m = get_map(data_params)
        folium_static(m)


    st.caption("Uses data from USGS Earthquake Catalog, courtesy of the U.S. Geological Survey")

app()
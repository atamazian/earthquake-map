import pandas as pd
import folium
from folium.plugins import MousePosition
import branca
from branca.element import Template, MacroElement
import requests
import streamlit as st
from streamlit_folium import st_folium, folium_static
from datetime import datetime, timedelta

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

#@st.cache_data
#def get_plate_boundaries():
#    geo_json_url = 'https://raw.githubusercontent.com/fraxen/tectonicplates/master/GeoJSON/PB2002_boundaries.json'
#    boundaries = folium.GeoJson(
#            geo_json_url,
#            name='Plate Boundaries',
#            style_function=lambda feature: {
#                    "color": "red",
#                    "weight": 0.75,
#                    "dashArray": "5, 5",
#                },
#        )
#    return boundaries

def get_earthquake_map(df):

    

    min_zoom = 2
    color_lst = ['purple', 'blue', 'green', 'yellow', 'orange', 'red']
    
    tile_graysale = folium.TileLayer(
        tiles = 'cartodb positron',
        attr = '© OpenStreetMap contributors © CARTO',
        name = 'Grayscale',
        overlay = False,
        control = True,
        min_zoom=min_zoom
       )
    
    m = folium.Map(location=[0, 0], tiles=tile_graysale, zoom_start=4, min_zoom=min_zoom, control_scale=True)

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


    #mc = MarkerCluster()

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
        
        popup_html = f"""
            <div style="font-family: Arial;">
                <h3><a href={row.url} target="_top">{row.title}</a></h3>
                <font color="grey">Time:</font> {row.date_time} (UTC)<br>
                <font color="grey">Location:</font> {abs(row.latitude)}&deg{ns_hem} {abs(row.longitude)}&deg{we_hem}<br>
                <font color="grey">Depth:</font> {row.depth} km
            </div>
        """

        popup = folium.Popup(branca.element.IFrame(html=popup_html, width=300, height=150))
            
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

    #mc.add_to(map)
    #plate_boundaries = get_plate_boundaries()
    #plate_boundaries.add_to(m)

    folium.LayerControl().add_to(m)

    formatter = "function(num) {return L.Util.formatNum(num, 3) + ' &deg; ';};"
    MousePosition(
        lat_formatter=formatter,
        lng_formatter=formatter,
    ).add_to(m)

    # Create the legend template as an HTML element
    depth_legend_template = """
    {% macro html(this, kwargs) %}
    <div id='maplegend' class='maplegend' 
        style='position: absolute; z-index: 9999; background-color: rgba(255, 255, 255, 0.5);
        border-radius: 6px; padding: 10px; font-size: 10.5px; left: 5px; bottom: 120px;'>

    Depth<br><br>
    <div class="colormap-container">
        <div class="colormap"></div><br>
        <div class="number" style="top: -7px;">0</div>
        <div class="number" style="top: 2%;">35</div>
        <div class="number" style="top: 8%;">70</div>
        <div class="number" style="top: 17%;">150</div>
        <div class="number" style="top: 35%;">300</div>
        <div class="number" style="top: 60%;">500</div>
        <div class="number" style="top: 97%;">800</div>
    </div>

    <style type='text/css'>
    .colormap-container {
        position: relative;
        width: 30px;
        height: 200px;
        margin-right: 10px;
        float: left;
    }

    .colormap {
        width: 10px;
        height: 200px;
        background: linear-gradient(to bottom, 
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
    }


    </style>
    {% endmacro %}
    """

    # Add the legend to the map
    macro = MacroElement()
    macro._template = Template(depth_legend_template)
    m.get_root().add_child(macro)

    # Create the legend template as an HTML element
    mag_legend_template = """
    {% macro html(this, kwargs) %}
    <div id='maplegend' class='maplegend' 
        style='position: absolute; z-index: 9999; background-color: rgba(255, 255, 255, 0.5);
        border-radius: 6px; padding: 10px; font-size: 10.5px; left: 0px; bottom: -70px;'>

    <div class='mag-legend'>
        Magnitude<br>
        <svg xmlns="http://www.w3.org/2000/svg" width="180" height="40">
            <circle cx="10" cy="9" r="10" fill="gray" stroke="black"/>
            <circle cx="30" cy="9" r="9" fill="gray" stroke="black"/>
            <circle cx="50" cy="9" r="8" fill="gray" stroke="black"/>
            <circle cx="70" cy="9" r="7" fill="gray" stroke="black"/>
            <circle cx="90" cy="9" r="6" fill="gray" stroke="black"/>
            <circle cx="110" cy="9" r="5" fill="gray" stroke="black"/>
            <circle cx="130" cy="9" r="4" fill="gray" stroke="black"/>
            <circle cx="150" cy="9" r="3" fill="gray" stroke="black"/>
            <circle cx="170" cy="9" r="2" fill="gray" stroke="black"/>
        </svg>
        <div class="number-2" style="left: 10px;">9</div>
        <div class="number-2" style="left: 30px;">8</div>
        <div class="number-2" style="left: 50px;">7</div>
        <div class="number-2" style="left: 70px;">6</div>
        <div class="number-2" style="left: 90px;">5</div>
        <div class="number-2" style="left: 110px;">4</div>
        <div class="number-2" style="left: 130px;">3</div>
        <div class="number-2" style="left: 150px;">2</div>
        <div class="number-2" style="left: 170px;">1</div>
        
    </div>
    </div> 
    <style type='text/css'>
    .mag-legend {
        position: relative;
        width: 180px;
        height: 40px;
    }
    .number-2 {
        position: absolute;
        bottom: -10px;
        transform: translateX(-50%);
        font-size: 12px;
        color: #333;
    }
    </style>
    {% endmacro %}
    """


    # Add the legend to the map
    macro = MacroElement()
    macro._template = Template(mag_legend_template)
    m.get_root().add_child(macro)

    return m

def get_map(params):
    df = get_earthquake_data(params)
    if df is not None:
        map = get_earthquake_map(df)
        return map
    else:
        print('No earthquakes found! Please change selection options.')
        return None
    
st.set_page_config(page_title="Interactive Earthquake Viewer", layout="wide")
st.title("Interactive Earthquake Viewer")

data_params = {
    'use_circle_search': False,
    'circle_lat': 0,
    'circle_long': 0,
    'circle_radius': 2
}

col1, col2 = st.columns([0.8, 0.2])

with col2:
    data_params['limit'] = st.number_input('Max earthquakes', min_value=10, max_value=20_000, value=1000, step=1)
    
    order = st.selectbox('Select by',
                        ['Newest', 'Largest'])

    if order == 'Newest':
        data_params['order'] = 'time'
    else:
        data_params['order'] = 'magnitude'

    with st.expander('Time Range'):
        select_earliest = st.checkbox('Earliest Available', True)
        yesterday = datetime.now() - timedelta(1)
        start_time = st.date_input('From', value=yesterday, disabled=select_earliest)

        select_latest = st.checkbox('Latest Available', True)
        end_time = st.date_input('To', value='today', disabled=select_latest)
        
        if not select_earliest:
            data_params['start_time'] = start_time.isoformat()

        if not select_latest:
            data_params['end_time'] = end_time.isoformat()

    with st.expander('Magnitude Range', expanded=False):
        select_mag = st.checkbox('All Magnitude values', True)
        mag_min = st.number_input('Min', min_value=0, max_value=9, value=3, disabled=select_mag)
        mag_max = st.number_input('Max', min_value=1, max_value=10, value=10, disabled=select_mag)
        if not select_mag:
            data_params.update({
                'min_magnitude': mag_min,
                'max_magnitude': mag_max,
            })

    with st.expander('Depth Range', expanded=False):
        select_depth = st.checkbox('All Depth values', True)
        depth_min = st.number_input('Min', min_value=0, max_value=799, value=0, disabled=select_depth)
        depth_max = st.number_input('Max', min_value=1, max_value=800, value=800, disabled=select_depth)
        if not select_depth:
            data_params.update({
                'min_depth': depth_min,
                'max_depth': depth_max,
            })

with col1:
    m = get_map(data_params)
    st_data = st_folium(m, width=1000, height=600)
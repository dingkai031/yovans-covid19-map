import pandas as pd
import geopandas as gpd
import json
from bokeh.models import GeoJSONDataSource, LinearColorMapper, ColorBar, DateRangeSlider, Select
from bokeh.plotting import figure
from bokeh.io import curdoc
from bokeh.palettes import brewer
from bokeh.layouts import column, row
from bokeh.models.callbacks import CustomJS


geoDF  = gpd.read_file("./data/geo_world_map/ne_110m_admin_0_countries.shp")[
    ['ADMIN', 'geometry']
]
geoDF = geoDF[geoDF['ADMIN'] != 'Antarctica']
covidDFRaw = pd.read_csv("./data/data-cvd19.csv")
covidDF = covidDFRaw[['date', 'location', 'new_cases', 'new_deaths', 'total_cases', 'total_deaths']]
covidDF.columns = ['Tanggal', 'Lokasi', 'Kasus_baru', 'Kematian_baru' ,'Total_kasus', 'Total_kematian']
covidDF = covidDF.convert_dtypes()
geoDF = geoDF.sort_values(by=['ADMIN']).reset_index(drop=True)
covidDF.loc[covidDF['Lokasi'] == 'Democratic Republic of Congo', 'Lokasi'] = 'Republic of the Congo'
covidDF.loc[covidDF['Lokasi'] == 'Eswatini', 'Lokasi'] = 'eSwatini'
covidDF.loc[covidDF['Lokasi'] == 'United States', 'Lokasi'] = 'United States of America'

CovidDFByCountry = covidDF[covidDF['Lokasi'].isin([x for x in geoDF['ADMIN']])].reset_index(drop=True)


TmpDF = CovidDFByCountry.groupby('Tanggal')['Lokasi'].nunique().reset_index()
TmpDF.columns = ['Tanggal', 'Jumlah']
TmpDF = TmpDF[TmpDF['Jumlah'] == 163].reset_index()

tanggalMin = TmpDF['Tanggal'][0]
tanggalMax = TmpDF['Tanggal'][49]

CovidDFByCountryFiltered = CovidDFByCountry[
    (CovidDFByCountry.Tanggal >= tanggalMin) & (CovidDFByCountry.Tanggal <= tanggalMax)
].reset_index(drop=True)
CovidDFByCountryFiltered
covidDFInitDate = CovidDFByCountryFiltered[CovidDFByCountryFiltered.Tanggal == tanggalMin].set_index('Lokasi')
geoDFNew = geoDF.set_index('ADMIN')
finalDF = geoDFNew.join(covidDFInitDate)
finalDF.drop(['Kematian_baru', 'Total_kematian', 'Total_kasus'], axis=1, inplace=True)
finalDF.reset_index(inplace=True)
finalDF.rename(columns={'Kasus_baru':'Kasus'}, inplace=True)

def findMinMaxValue(df,value) :
    listData = [x for x in df[value]]
    listData = [x for x in filter(lambda x: not pd.isna(x), listData)]
    listData.sort()
    return {
        'maxValue' : listData[-1],
        'minValue' : listData[0]
    }

def dfToJSONString(df) :
    DFDict = json.loads(df.to_json())
    return json.dumps(DFDict)



finalDF = finalDF.convert_dtypes().astype({'Tanggal': str})
geoDFJSON = dfToJSONString(finalDF)


geoSource = GeoJSONDataSource(geojson = geoDFJSON)
CovidDFByCountryFilteredJSONString = dfToJSONString(CovidDFByCountryFiltered)


palette = brewer['OrRd'][9]
palette = palette[::-1]
minMaxSum = findMinMaxValue(finalDF, 'Kasus')
selectMenu = ['Kasus_baru','Kematian_baru','Total_kasus','Total_kematian']


color_mapper = LinearColorMapper(palette=palette, low=minMaxSum['minValue'], high=minMaxSum['maxValue'])
color_bar = ColorBar(color_mapper=color_mapper)
date_range = DateRangeSlider(value=(tanggalMin, tanggalMax), 
                             start=tanggalMin, end=tanggalMax, 
                             step=1, title='Tanggal',
                             sizing_mode='scale_width')
select = Select(title="Jenis Kasus", value='Kasus_baru', options=selectMenu)


callbackSelect = CustomJS(
    args = dict( 
        source = geoSource, 
        dataset = CovidDFByCountryFilteredJSONString, 
        dateSlider = date_range,
        mapper=color_mapper
    ), 
    code = """
    function formatDate(date) {
        var d = new Date(date),
        month = '' + (d.getMonth() + 1),
        day = '' + d.getDate(),
        year = d.getFullYear();

        if (month.length < 2) month = '0' + month;
        if (day.length < 2) day = '0' + day;

        return [year, month, day].join('-');
    };
    const data = source.data;
    const dataSet = JSON.parse(dataset);
    const tanggalTerpilih = formatDate(dateSlider.value[0]);
    const negaraSource = data.ADMIN;
    const kasusSource = data.Kasus;
    const kasusFilteredByDate = [];
    const kasusFiltered = [];
    for (let i=0;i<Object.keys(dataSet.Tanggal).length;i++) {
        if (tanggalTerpilih == Object.values(dataSet.Tanggal)[i]) {
            kasusFilteredByDate.push({
                namaNegara: Object.values(dataSet.Lokasi)[i],
               jumKasus: Object.values(dataSet[this.value])[i]
            });
        };
    };
    for (let i=0;i<data.Kasus.length;i++){
        for (const country of kasusFilteredByDate) {
            if (negaraSource[i] == country.namaNegara) {
                kasusSource[i] = country.jumKasus;
            };
        };
    };
    for (const kasus of kasusSource ) {
        if (kasus) {
            kasusFiltered.push(kasus);
        };
    };
    mapper.low = Math.min(...kasusFiltered);
    mapper.high = Math.max(...kasusFiltered);
    source.change.emit();
    """
)

callbackDateSlider = CustomJS(
    args=dict(
        source=geoSource, 
        dataset=CovidDFByCountryFilteredJSONString,
        select=select,
        mapper=color_mapper
    ), 
    code="""
        function formatDate(date) {
            var d = new Date(date),
            month = '' + (d.getMonth() + 1),
            day = '' + d.getDate(),
            year = d.getFullYear();

            if (month.length < 2) month = '0' + month;
            if (day.length < 2) day = '0' + day;

            return [year, month, day].join('-');
        };
        const data = source.data;
        const tanggalSource = data.Tanggal
        const kasusSource = data.Kasus;
        const negaraSource = data.ADMIN;
        const dataSet = JSON.parse(dataset);
        const tanggal = formatDate(new Date(cb_obj.value[0]));
        const kasusFilteredByDate = [];
        const kasusFiltered = [];
        for (let i=0;i<Object.keys(dataSet.Tanggal).length;i++) {
            if (tanggal == Object.values(dataSet.Tanggal)[i]) {
                kasusFilteredByDate.push({
                    namaNegara: Object.values(dataSet.Lokasi)[i],
                    jumKasus: Object.values(dataSet[select.value])[i]
                });
            };
        };
        for (let i=0;i<tanggalSource.length;i++){
            tanggalSource[i] = tanggal;
            for (const country of kasusFilteredByDate) {
                if (negaraSource[i] == country.namaNegara) {
                    kasusSource[i] = country.jumKasus;
                };
            };
        };
        for (const kasus of kasusSource ) {
            if (kasus) {
                kasusFiltered.push(kasus);
            };
        };
        mapper.low = Math.min(...kasusFiltered);
        mapper.high = Math.max(...kasusFiltered);
        source.change.emit();
    """)

date_range.js_on_change('value_throttled',callbackDateSlider)
select.js_on_change('value',callbackSelect)

fill_colorOpt = {'field': 'Kasus', 'transform': color_mapper}
bokeh_map = figure(
    title='Persebaran Covid 19 di Dunia (2020-2021)',
    plot_height=720,
    plot_width=1280,
    tooltips=[
        ('Tanggal', '@Tanggal'),
        ('Nama Negara', '@ADMIN'),
        ('Kasus', '@Kasus')
    ]
)
bokeh_map.add_layout(color_bar, 'below')
bokeh_map.patches(source=geoSource,
                  fill_color=fill_colorOpt,
                  line_color='black',
                  line_width=0.5
                 )
bokeh_map.axis.visible = False

kolom = column([select, date_range])
kolom.sizing_mode='scale_width'
layout = row([bokeh_map, kolom])
curdoc().title = 'Yovans covid19 Map'
curdoc().add_root(layout)


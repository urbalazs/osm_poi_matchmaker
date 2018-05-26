# -*- coding: utf-8 -*-

try:
    import traceback
    import logging
    import json
    import pandas as pd
    from osm_poi_matchmaker.dao.data_handlers import insert_poi_dataframe
    from osm_poi_matchmaker.libs.address import extract_all_address
    from osm_poi_matchmaker.libs.geo import check_geom
    from osm_poi_matchmaker.libs.osm import query_postcode_osm_external
    from osm_poi_matchmaker.dao import poi_array_structure
except ImportError as err:
    print('Error {0} import module: {1}'.format(__name__, err))
    traceback.print_exc()
    exit(128)


POI_COLS = poi_array_structure.POI_COLS


class hu_kh_bank():

    def __init__(self, session, download_cache, prefer_osm_postcode, link, name):
        self.session = session
        self.download_cache = download_cache
        self.link = link
        self.prefer_osm_postcode = prefer_osm_postcode
        self.name = name

    @staticmethod
    def types():
        data = [{'poi_code': 'hukhbank', 'poi_name': 'K&H bank', 'poi_type': 'bank',
                 'poi_tags': "{'amenity': 'bank', 'brand': 'K&H', 'operator': 'K&H Bank Zrt.', 'bic': 'OKHBHUHB', 'atm': 'yes'}",
                 'poi_url_base': 'https://www.kh.hu'},
                {'poi_code': 'hukhatm', 'poi_name': 'K&H', 'poi_type': 'atm',
                 'poi_tags': "{'amenity': 'atm', 'brand': 'K&H', 'operator': 'K&H Bank Zrt.'}",
                 'poi_url_base': 'https://www.kh.hu'}]
        return data

    def process(self):
        if self.link:
            with open(self.link, 'r') as f:
                insert_data = []
                text = json.load(f)
                for poi_data in text['results']:
                    first_element = next(iter(poi_data))
                    if self.name == 'K&H bank':
                        name = 'K&H bank'
                        code = 'hukhbank'
                    else:
                        name = 'K&H'
                        code = 'hukhatm'
                    postcode, city, street, housenumber, conscriptionnumber = extract_all_address(
                        poi_data[first_element]['address'])
                    branch = None
                    website = None
                    if code == 'hukhatm':
                        nonstop = True
                    else:
                        nonstop = False
                    mo_o = None
                    th_o = None
                    we_o = None
                    tu_o = None
                    fr_o = None
                    sa_o = None
                    su_o = None
                    mo_c = None
                    th_c = None
                    we_c = None
                    tu_c = None
                    fr_c = None
                    sa_c = None
                    su_c = None
                    lat = poi_data[first_element]['latitude']
                    lon = poi_data[first_element]['longitude']
                    geom = check_geom(lat, lon)
                    postcode = query_postcode_osm_external(self.prefer_osm_postcode, self.session, lat, lon, postcode)
                    original = poi_data[first_element]['address']
                    ref = None
                    phone = None
                    email = None
                    insert_data.append(
                        [code, postcode, city, name, branch, website, original, street, housenumber, conscriptionnumber,
                         ref, phone, email, geom, nonstop, mo_o, th_o, we_o, tu_o, fr_o, sa_o, su_o, mo_c, th_c, we_c,
                         tu_c, fr_c, sa_c, su_c])
                if len(insert_data) < 1:
                    logging.warning('Resultset is empty. Skipping ...')
                else:
                    df = pd.DataFrame(insert_data)
                    df.columns = POI_COLS
                    insert_poi_dataframe(self.session, df)

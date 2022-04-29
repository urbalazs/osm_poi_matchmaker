# -*- coding: utf-8 -*-

try:
    import logging
    import sys
    import math
    import os
    import datetime
    import traceback
    from urllib.parse import quote
    from osm_poi_matchmaker.dao.data_structure import OSM_object_type
    from osm_poi_matchmaker.utils import config
    from osm_poi_matchmaker.libs.address import clean_url
    from osm_poi_matchmaker.libs.file_output_helper import url_tag_generator
    from osm_poi_matchmaker.libs.osm import relationer, timestamp_now
    from osm_poi_matchmaker.libs.compare_strings import compare_strings
    from sqlalchemy.orm import scoped_session, sessionmaker
    from osm_poi_matchmaker.dao.poi_base import POIBase
    from lxml import etree
    import lxml
except ImportError as err:
    logging.error('Error %s import module: %s', __name__, err)
    logging.exception('Exception occurred')

    sys.exit(128)

POI_TAGS = {'poi_name': 'name', 'poi_city': 'addr:city', 'poi_postcode': 'addr:postcode',
            'poi_addr_street': 'addr:street', 'poi_addr_housenumber': 'addr:housenumber',
            'poi_conscriptionnumber': 'addr:conscriptionnumber', 'poi_branch': 'branch', 'poi_email': 'email'}

# TODO: Separete adblue_pack, adblue_car and adblue_truck tags
# TODO: fuel:adblue=yes; fuel:adblue:canister=yes;fuel:adblue:motorcar=yes;fuel:adblue:hgv=yes

POI_YESNO_TAGS = {'poi_fuel_adblue': 'fuel:adblue', 'poi_fuel_octane_100': 'fuel:octane_100',
                  'poi_fuel_octane_98': 'fuel:octane_98', 'poi_fuel_octane_95': 'fuel:octane_95',
                  'poi_fuel_diesel_gtl': 'fuel:GTL_diesel', 'poi_fuel_diesel': 'fuel:diesel',
                  'poi_fuel_lpg': 'fuel:lpg', 'poi_fuel_e85': 'fuel:e85', 'poi_rent_lpg_bottles': 'rent:lpg_bottles',
                  'poi_compressed_air': 'compressed_air', 'poi_restaurant': 'restaurant', 'poi_food': 'food',
                  'poi_truck': 'truck', 'poi_authentication_app': 'authentication:app',
                  'poi_authentication_membership_card': 'authentication:membership_card', 'poi_fee': 'fee',
                  'poi_parking_fee': 'parking_fee', 'poi_motorcar': 'motorcar'}

POI_EV_TAGS = {'poi_capacity': 'capacity',
               'poi_socket_chademo': 'socket:chademo', 'poi_socket_chademo_output': 'socket:chademo:output',
               'poi_socket_type2_combo': 'socket:type2_combo',
               'poi_socket_type2_combo_output': 'socket:type2_combo:output',
               'poi_socket_type2_cable': 'socket:type2_cable',
               'poi_socket_type2_cable_output': 'socket:type2_cable:output',
               'poi_socket_type2': 'socket:type2', 'poi_socket_type2_output': 'socket:type2:output',
               'poi_manufacturer': 'manufacturer', 'poi_model': 'model'}

TESTCASE_GEN_KEYS = ('original', 'poi_postcode', 'poi_city', 'poi_addr_street', 'poi_addr_housenumber', 'poi_conscriptionnumber')

TIMESTAMP_FORMAT = '{:{dfmt}T{tfmt}Z}'
DATE_FOTMAT = '%Y-%m-%d'
TIME_FORMAT = '%H:%M:%S'


def ascii_numcoder(text):
    output = ''
    for i in text:
        if i in range(0, 10, 1):
            output += i
        else:
            output += str(ord(i))
    return output


def save_csv_file(path: str, file: str, data, message: str):
    """Save Pandas dataframe to a CSV file

    Args:
        path (str): Path of newly created CVS file
        file (str): Filename of newly created CVS file
        data (pd.DataFrame): Pandas dataframe to write
        message (str): Addtion information to display
    """
    try:
        # Save file to CSV file
        logging.info('Saving %s to file: %s', message, file)
        res = data.to_csv(os.path.join(path, file))
        logging.info('The %s was sucessfully saved', file)
    except Exception as e:
        logging.exception('Exception occurred: {}'.format(e))
        logging.error(traceback.print_exc())


def add_osm_node(osm_id: int, node_data: dict, prefix: str = 'poi') -> dict:
    """Generate OpenStreetMap node header information as string

    Args:
        osm_id (int): OpenStreetMap ID
        node_data (dict): [description]
        prefix (str): Prefix for field names in database

    Returns:
        str: [description]
    """
    if node_data.get('osm_timestamp') is None:
        osm_timestamp = datetime.datetime.now()
    else:
        osm_timestamp = node_data.get('osm_timestamp')
    osm_version = '99999' if node_data.get('osm_version') is None else node_data.get('osm_version')
    osm_data = {'action': 'modify', 'id': str(osm_id),
                'lat': '{}'.format(node_data.get('{}_lat'.format(prefix))),
                'lon': '{}'.format(node_data.get('{}_lon'.format(prefix))),
                'user': '{}'.format('osm_poi_matchmaker'), 'uid': '{}'.format('8635934'), 'version': '{}'.format(osm_version),
                'timestamp': TIMESTAMP_FORMAT.format(osm_timestamp, dfmt=DATE_FOTMAT, tfmt=TIME_FORMAT)}
    logging.info('Created OSM data: {}'.format(osm_data))
    return osm_data


def list_osm_node(osm_id: int, node_data: dict, prefix='poi') -> dict:
    """Generate OpenStreetMap node header information as string

    Args:
        osm_id (int): OpenStreetMap ID
        node_data (dict): [description]
        prefix (str): Prefix for field names in database

    Returns:
        str: [description]
    """
    logging.debug(node_data)
    osm_user = 'osm_poi_matchmaker' if node_data.get('osm_user') is None else node_data.get('osm_user')
    osm_user_id = '8635934' if node_data.get('osm_user_id') is None else node_data.get('osm_user_id')
    if node_data.get('osm_timestamp') is None:
        osm_timestamp = datetime.datetime.now()
    else:
        osm_timestamp = node_data.get('osm_timestamp')
    osm_version = '99999' if node_data.get('osm_version') is None else node_data.get('osm_version')
    osm_data = {'id': str(osm_id),
                'lat': '{}'.format(node_data.get('{}_lat'.format(prefix))),
                'lon': '{}'.format(node_data.get('{}_lon'.format(prefix))),
                'user': '{}'.format(osm_user), 'uid': '{}'.format(osm_user_id), 'version': '{}'.format(osm_version),
                'timestamp': TIMESTAMP_FORMAT.format(osm_timestamp, dfmt=DATE_FOTMAT, tfmt=TIME_FORMAT)}
    logging.debug(osm_data)
    return osm_data


def add_osm_way(osm_id: int, node_data: dict) -> dict:
    """Generate OpenStreetMap way header information as dictionary

    Args:
        osm_id (int): [description]
        node_data (dict): [description]

    Returns:
        str: [description]
    """
    if node_data.get('osm_timestamp') is None:
        osm_timestamp = datetime.datetime.now()
    else:
        osm_timestamp = node_data.get('osm_timestamp')
    osm_version = '99999' if node_data.get('osm_version') is None else node_data.get('osm_version')
    osm_data = {'action': 'modify', 'id': str(osm_id),
                'user': '{}'.format('osm_poi_matchmaker'), 'uid': '{}'.format('8635934'),
                'version': '{}'.format(osm_version),
                'timestamp': TIMESTAMP_FORMAT.format(osm_timestamp, dfmt=DATE_FOTMAT, tfmt=TIME_FORMAT)}
    return osm_data


def add_osm_link_comment(osm_id: int, osm_type) -> str:
    """Create OpenStreetMap osm.org link from OSM object

    Args:
        osm_id (int): [description]
        osm_type ([type]): [description]

    Returns:
        str: [description]
    """
    osm_comment = ' OSM link: https://osm.org/{}/{} '.format(osm_type.name, str(osm_id))
    return osm_comment


def generate_osm_xml(df, session=None):
    """Crete OpenStreetMap (OSM XML) file from passed Panda Dataframe

    Args:
        df ([type]): [description]
        session ([type], optional): [description]. Defaults to None.

    Returns:
        [type]: [description]
    """
    db = POIBase('{}://{}:{}@{}:{}/{}'.format(config.get_database_type(), config.get_database_writer_username(),
                                              config.get_database_writer_password(),
                                              config.get_database_writer_host(),
                                              config.get_database_writer_port(),
                                              config.get_database_poi_database()))
    pgsql_pool = db.pool
    session_factory = sessionmaker(pgsql_pool)
    Session = scoped_session(session_factory)
    session = Session()
    osm_xml_data = etree.Element('osm', version='0.6', generator='JOSM')
    default_osm_id = -1
    current_osm_id = default_osm_id
    added_nodes = []
    try:
        for index, row in df.iterrows():
            try:
                logging.info('Start processing: {}. item'.format(index+1))
                logging.debug(row.to_string())
                tags = {}
                xml_node_tags = None
                osm_live_tags = {}
                main_data = {}
                current_osm_id = default_osm_id if row.get('osm_id') is None else row.get('osm_id')
                osm_version = '99999' if row.get('osm_version') is None else row.get('osm_version')
            except Exception as e:
                logging.exception('Exception occurred: {}'.format(e))
                logging.error(traceback.print_exc())
            try:
                # OSM Object type is node and select this for new node to where osm_node type is not defined (None)
                if row.get('osm_node') is None or row.get('osm_node') == OSM_object_type.node:
                    try:
                        logging.debug('Object type is node or new node.')
                        josm_object = 'n{}'.format(current_osm_id)
                        main_data = etree.SubElement(osm_xml_data, 'node', add_osm_node(current_osm_id, row))
                    except Exception as e:
                        logging.exception('Exception occurred: {}'.format(e))
                        logging.error(traceback.print_exc())
                elif row.get('osm_node') is not None and row.get('osm_node') == OSM_object_type.way:
                    try:
                        logging.debug('Object type is way.')
                        main_data = etree.SubElement(osm_xml_data, 'way', add_osm_way(current_osm_id, row))
                        josm_object = 'w{}'.format(current_osm_id)
                    # Add way nodes without any modification)
                        node_data = []
                        for n in row.get('osm_nodes'):
                            data = etree.SubElement(main_data, 'nd', ref=str(n))
                        if session is not None:
                            # Go through the list except the last value (which is same as the first)
                            for n in row.get('osm_nodes'):
                                # Add nodes only when it is not already added.
                                if n not in added_nodes:
                                    added_nodes.append(n)
                                    way_node = db.query_from_cache(n, OSM_object_type.node)
                                    if way_node is not None:
                                        node_data = etree.SubElement(osm_xml_data, 'node',
                                                                     list_osm_node(n, way_node, 'osm'))
                                        if node_data.get('osm_live_tags') is not None and \
                                           node_data.get('osm_live_tags') != '':
                                            node_osm_live_tags = node_data.get('osm_live_tags')
                                            for k, v in sorted(node_osm_live_tags).items():
                                                xml_node_tags = etree.SubElement(node_data, 'tag', k=k, v='{}'.format(v))
                    except TypeError as e:
                        logging.warning('Missing nodes on this way: %s.', row.get('osm_id'))
                        logging.exception('Exception occurred: {}'.format(e))
                        logging.error(traceback.print_exc())
                elif row.get('osm_node') is not None and row.get('osm_node') == OSM_object_type.relation:
                    try:
                        logging.debug('Object type is relation.')
                        main_data = etree.SubElement(osm_xml_data, 'relation', add_osm_way(current_osm_id, row))
                        josm_object = 'r{}'.format(current_osm_id)
                        relations = relationer(row.get('osm_nodes'))
                        for i in relations:
                            data = etree.SubElement(main_data, 'member', type=i.get('type'), ref=i.get('ref'),
                                                    role=i.get('role'))
                    except TypeError as e:
                        logging.warning('Missing nodes on this relation: %s.', row['osm_id'])
                        logging.exception('Exception occurred: {}'.format(e))
                        logging.error(traceback.print_exc())
            except Exception as e:
                logging.exception('Exception occurred: {}'.format(e))
                logging.error(traceback.print_exc())
            # Add already existing node, way, relation OpenStreetMap reference as comment
            try:
                logging.debug('Add OSM reference as comment.')
                if current_osm_id > 0:
                    osm_xml_data.append(etree.Comment(add_osm_link_comment(current_osm_id, row.get('osm_node'))))
                # Add original POI coordinates as comment
                comment = etree.Comment(' Original coordinates: {} '.format(row.get('poi_geom')))
                osm_xml_data.append(comment)
                logging.debug('Add OSM - POI distance as comment.')
                if 'poi_distance' in row and row.get('poi_distance') is not None:
                    comment = etree.Comment(' OSM <-> POI distance: {} m'.format(row.get('poi_distance')))
                else:
                    logging.debug('New POI, have not got distance data.')
                    comment = etree.Comment(' OSM <-> POI distance: Non exist')
                osm_xml_data.append(comment)
                if 'poi_good' in row and 'poi_bad' in row:
                    logging.debug('Add good/bad quality comments.')
                    comment = etree.Comment(' Checker good: {}; bad {}'.format(row.get('poi_good'), row.get('poi_bad')))
                    osm_xml_data.append(comment)
                # Using already defined OSM tags if exists
                logging.debug('Add OSM live tags.')
                if row.get('osm_live_tags') is not None:
                    logging.debug('Add OSM live tags.')
                    logging.debug('Add OSM live tags.')
                    tags.update(row.get('osm_live_tags').copy())
                    logging.info('Additional live tags'.format(row.get('osm_live_tags')))
                    osm_live_tags.update(row.get('osm_live_tags').copy())
                # Adding POI common tags
                logging.debug('Add POI common tags.')
                if row.get('poi_tags') is not None:
                    tags.update(row.get('poi_tags'))
            except Exception as e:
                logging.exception('Exception occurred: {}'.format(e))
                logging.error(traceback.print_exc())
            try:
                # Save live name tags if preserve name is enabled
                logging.debug('Preserve item name tag.')
                if row.get('preserve_original_name') is True:
                    preserved_name = tags.get('name')
            except KeyError as e:
                logging.debug('No name tag is specified to save in original OpenStreetMap data.')
            try:
                # Overwriting with data from data providers
                logging.debug('Overwrite item tags from common tags.')
                for k, v in POI_TAGS.items():
                    if row.get(k) is not None:
                        tags[v] = row.get(k)
            except Exception as e:
                logging.exception('Exception occurred: {}'.format(e))
                logging.error(traceback.print_exc())
            try:
                logging.debug('Decide opening_hours tag key.')
                if config.get_geo_alternative_opening_hours():
                    alternative_oh_tag = config.get_geo_alternative_opening_hours_tag()
                    # Alternative opening_hours handling for COVID-19 code path
                    if tags.get('opening_hours') is not None and tags.get('opening_hours') != '':
                        if row.get('poi_opening_hours') is not None and row.get('poi_opening_hours') != '':
                            if tags.get('opening_hours') == row.get('poi_opening_hours'):
                                tags[alternative_oh_tag] = 'same'
                            else:
                                tags[alternative_oh_tag] = row.get('poi_opening_hours')
                    else:
                        if row.get('poi_opening_hours') is not None and row.get('poi_opening_hours') != '':
                            tags['opening_hours'] = row.get('poi_opening_hours')
                            tags[alternative_oh_tag] = 'same'
                else:
                    # Alternative opening_hours handling for NON COVID-19 code path: just simply add opening_hours to tags
                    if row.get('poi_opening_hours') is not None and row.get('poi_opening_hours') != '':
                        tags['opening_hours'] = row.get('poi_opening_hours')
            except Exception as e:
                logging.exception('Exception occurred: {}'.format(e))
                logging.error(traceback.print_exc())
            try:
                # If we got POI phone tag use it as OSM contact:phone tag
                logging.debug('Add contact:phone tag with phone numbers.')
                if row.get('poi_phone') is not None and row.get('poi_phone') != '':
                    tags['contact:phone'] = row.get('poi_phone')
            except Exception as e:
                logging.exception('Exception occurred: {}'.format(e))
                logging.error(traceback.print_exc())
            try:
                # If we got POI website tag use it as OSM contact:website tag
                logging.debug('Add contact:website tag with website URL.')
                tags['contact:website'] = url_tag_generator(row.get('poi_url_base'), row.get('poi_website'))
            except Exception as e:
                logging.exception('Exception occurred: {}'.format(e))
                logging.error(traceback.print_exc())
            try:
                # Short URL for source OSM tag
                # Can disable in app.conf via use.general.source.website.date key (deafault)
                logging.debug('Add source OSM tag.')
                if row['poi_url_base'] is not None and config.get_use_general_source_website_date() is False:
                    source_url = 'source:{}:date'.format(row.get('poi_url_base').split('/')[2])
                else:
                    # Issue #97: Remove source:(website):date tag and add source:website:date tag
                    # Then make it configurable via issue #98
                    if config.get_use_general_source_website_date_tag() is None:
                        source_url = 'source:date'
                    else:
                        source_url = config.get_use_general_source_website_date_tag()
                    if row['poi_url_base'] is not None:
                        source_url_2 = 'source:{}:date'.format(row.get('poi_url_base').split('/')[2])
                        tags.pop(source_url_2, None)
                tags[source_url] = '{:{dfmt}}'.format(datetime.datetime.now(), dfmt=DATE_FOTMAT)
            except Exception as e:
                logging.exception('Exception occurred: {}'.format(e))
                logging.error(traceback.print_exc())
            try:
                # Write back the saved name tag
                logging.debug('Add back preserved name.')
                if 'preserved_name' in locals():
                    tags['name'] = preserved_name
                # Rewrite old contact tags to contact:* tag form
                logging.debug('Rewrite old contact tags to contact:* tag form.')
                tags_rewrite = ['website', 'phone', 'email', 'facebook', 'instagram', 'youtube', 'pinterest', 'fax']
                for tr in tags_rewrite:
                    if tr in tags:
                        # Never overwrite already existing contact:* tags
                        if 'contact:' + tr in tags:
                            # We already have this contact:* tag so remove the simple contact tag
                            tags.pop(tr, None)
                        else:
                            # Rewrite simple contact tag to contact:* tag
                            tags['contact:' + tr] = tags.pop(tr, None)
                        # rewrite email and website as small caps
                        if tr in ['email', 'website' ]:
                            if isinstance(str, tags.get('contact:' + tr)) and tags.get('contact:' + tr) is not None:
                                tags['contact:' + tr] = str(tags.get('contact:' + tr)).lower()
            except Exception as e:
                logging.exception('Exception occurred: {}'.format(e))
                logging.error(traceback.print_exc())
            try:
                logging.debug('Add description OSM tag.')
                if row.get('poi_description') is not None and row.get('poi_description') != '':
                    tags['description'] = row.get('poi_description')
            except Exception as e:
                logging.exception('Exception occurred: {}'.format(e))
                logging.error(traceback.print_exc())
            try:
                # Write tags with yes/no value
                logging.debug('Add boolean OSM tags.')
                for k, v in POI_YESNO_TAGS.items():
                    if row.get(k) is not None and row.get(k) != '':
                        tags[v] = 'yes' if row.get(k) is True else 'no'
                for k, v in POI_EV_TAGS.items():
                    if row.get(k) is not None and row.get(k) != '':
                        if isinstance(row.get(k), float):
                            if not math.isnan(row.get(k)):
                                tags[v] = int(row.get(k))
                        else:
                            tags[v] = row.get(k)
            except Exception as e:
                logging.exception('Exception occurred: {}'.format(e))
                logging.error(traceback.print_exc())
            try:
                # This is a new POI - will add fix me tag to the new items.
                if row.get('poi_new') is not None and row.get('poi_new') is True:
                    logging.debug('Add "fixme:verify import" OSM tag for new item.')
                    tags['fixme'] = 'verify import'
                # Remove unwanted addr:country from file output as we discussed in Issue #33
                logging.debug('Remove addr:country OSM tag.')
                tags.pop('addr:country', None)
                # tags['import'] = 'osm_poi_matchmaker'
            except Exception as e:
                logging.exception('Exception occurred: {}'.format(e))
                logging.error(traceback.print_exc())
            try:
                # Rendering tags to the XML file and JOSM magic link
                logging.debug('Rendering OSM tag as XML comments.')
                josm_link = ''
                comment = '\nKey\t\t\t\tStatus\t\tNew value\t\tOSM value\n'
                for k, v in sorted(tags.items()):
                    xml_tags = etree.SubElement(main_data, 'tag', k=k, v='{}'.format(v))
                    josm_link = '{}|{}={}'.format(josm_link, k, v)
                    # Add original POI tags as comment
                    try:
                        if isinstance(v, str):
                            v = v.replace('-', '\-').replace('\n', '')
                        w = osm_live_tags[k]
                    except KeyError:
                        comment += "{:32} NEW\t\t'{}'\n".format(k, v)
                    else:
                        if isinstance(w, str):
                            w = w.replace('-', '\-').replace('\n', '')
                        comment += "{:32} {}\t\t'{}'\t\t\t'{}'\n".format(k, compare_strings(v, w), v, w)
                logging.debug('Adding OSM tag XML comments to XML file representation.')
                comment = etree.Comment(comment)
                osm_xml_data.append(comment)
            except Exception as e:
                logging.exception('Exception occurred: {}'.format(e))
                logging.error(traceback.print_exc())
            try:
                logging.debug('Rendering JOSM link as XML comment.')
                # URL encode link and '--' in comment
                josm_link = quote(josm_link)
                josm_link = josm_link.replace('--', '%2D%2D')
                logging.debug('Adding JOSM link as XML comments to XML file representation.')
                comment = etree.Comment(' JOSM magic link: {}?new_layer=false&objects={}&addtags={} '.format
                                        ('http://localhost:8111/load_object', josm_object, josm_link))
                osm_xml_data.append(comment)
            except Exception as e:
                logging.exception('Exception occurred: {}'.format(e))
                logging.error(traceback.print_exc())
            try:
                logging.debug('Rendering test data as XML comment.')
                test_case = {k: row.get(k, None) for k in TESTCASE_GEN_KEYS}
                comment = etree.Comment("ˇ'original': '{t[original]}', 'postcode': '{t[poi_postcode]}', 'city': '{t[poi_city]}', 'street': '{t[poi_addr_street]}', 'housenumber': '{t[poi_addr_housenumber]}', 'conscriptionnumber': '{t[poi_conscriptionnumber]}'°".format(t=test_case))
                osm_xml_data.append(comment)
            except Exception as e:
                logging.exception('Exception occurred: {}'.format(e))
                logging.error(traceback.print_exc())
            try:
                logging.debug('XML node tags check.')
                if xml_node_tags is not None:
                    logging.debug('Add XML node tags.')
                    osm_xml_data.append(xml_node_tags)
            except UnboundLocalError as e:
                logging.debug('Unbound local error extra node tags')
                logging.error(traceback.print_exc())
                logging.debug(etree.dump(osm_xml_data))
                logging.debug(etree.dump(xml_node_tags))
            except Exception as e:
                logging.exception('Exception occurred: {}'.format(e))
                logging.error(traceback.print_exc())
                logging.debug(etree.dump(osm_xml_data))
                logging.debug(etree.dump(xml_node_tags))
            try:
                logging.debug('Attach POI data to main XML node.')
                osm_xml_data.append(main_data)
                # Next default OSM id is one more less for non existing objects
                logging.debug('Decrease OSM id (negative number) of new POI for the next round.')
                default_osm_id -= 1
            except Exception as e:
                logging.exception('Exception occurred: {}'.format(e))
                logging.error(traceback.print_exc())
            logging.info('Finished processing: {}. item'.format(index+1))
        logging.info('What is happening here')
    except ValueError as e:
        logging.exception('ValueError Exception occurred: {}'.format(e))
        logging.error(traceback.print_exc())

    except Exception as e:
        logging.exception('Exception occurred: {}'.format(e))
        logging.error(traceback.print_exc())
    logging.info('Processed {}. items'.format(len(df)))
    logging.critical('---------------------------------------------')
    logging.debug(lxml.etree.tostring(osm_xml_data, pretty_print=True, xml_declaration=True, encoding="UTF-8"))
    logging.critical('---------------------------------------------')
    return lxml.etree.tostring(osm_xml_data, pretty_print=True, xml_declaration=True, encoding="UTF-8")

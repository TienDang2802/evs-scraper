from googleplaces import GooglePlaces, types, lang
import googlemaps
import csv
from time import sleep
import requests
import sys
import re
from send_mail import *


def scrape(query, city, filters_exclude, filters_include, user, uid):
    results = [['Name', 'Company Domain', 'Phone Number', 'Company owner', 'Lifecycle stage', 'Country', 'City']]

    results_process = process_filter(query, city, filters_exclude, filters_include, user)

    if results_process:
        results += results_process
        # create file that will be send to user and admin (in BCC)
        with open(str(user) + str(uid) + '_leads.csv', 'w', newline='') as f:
            writer = csv.writer(f)
            for result in results:
                writer.writerow(result)


def process_filter(query, city, filters_exclude, filters_include, user, is_web=False):
    results = []
    query_list = query.split(',')
    city_list = city.split(',')

    filters_exclude_list = []
    if filters_exclude != '':
        filters_exclude_list = filters_exclude.split(',')
        filters_exclude_list = [x.strip() for x in filters_exclude_list]

    filters_include_list = []
    if filters_include != '':
        filters_include_list = filters_include.split(',')
        filters_include_list = [x.strip() for x in filters_include_list]

    total_city = len(city_list)
    print('Total cities: {}'.format(total_city))

    radius = int(os.environ.get('SEARCH_RADIUS'))

    google_places_api = GooglePlaces(os.environ['GP_API_KEY1'])

    gmaps = googlemaps.Client(key=os.environ['GP_API_KEY1'])

    query_result = {}

    for city in city_list:
        print('Processing city: {}'.format(city))
        for query in query_list:
            print('Processing query string {} of city {} with radius={}'.format(query, city, radius))

            geocode_result = gmaps.geocode(city)
            latlng = '{}, {}'.format(geocode_result[0]['geometry']['location']['lat'],
                                     geocode_result[0]['geometry']['location']['lng'])
            try:
                query_result = google_places_api.nearby_search(keyword=query, radius=radius, location=latlng)
            except:
                sleep(30)
                try:
                    google_places_api2 = GooglePlaces(os.environ['GP_API_KEY2'])
                    query_result = google_places_api2.nearby_search(keyword=query, radius=radius, location=latlng)
                except:
                    send_error(user)

            while True:
                if query_result:
                    for place in query_result.places:
                        place.get_details()
                        if place.website:
                            if filters_exclude_list:
                                if any(word.strip().lower() in place.name.lower() for word in filters_exclude_list):
                                    print('exclude full continue')
                                    continue

                        if not place.website or 'https' in place.website:
                            results.append(render_result(place, is_web))
                            continue

                        # filter
                        page_content_text = ''
                        try:
                            page_content = requests.get(place.website)
                            page_content_text = page_content.text
                        except Exception as e:
                            print('Error on line {}'.format(sys.exc_info()[-1].tb_lineno), type(e).__name__, e)
                            results.append(render_result(place, is_web))

                        if page_content_text and filters_exclude_list:
                            filter_exclude = is_filters_exclude(page_content_text, filters_exclude_list)
                            if filter_exclude:
                                print('Filter exclude')
                                continue

                        if page_content_text and filters_include_list:
                            filter_include = is_filters_include(page_content_text, filters_include_list)
                            if not filter_include:
                                print('Filter include')
                                continue

                        results.append(render_result(place, is_web))

                if not query_result.has_next_page_token or is_web:
                    break

                sleep(30)

                print('Next page token: {}'.format(query_result.next_page_token))

                query_result = google_places_api.nearby_search(
                    pagetoken=query_result.next_page_token
                )

    return results


def render_result(place, is_web=False):
    if is_web:
        return [place.name, place.website, place.formatted_address, place.international_phone_number, '']
    return [
        place.name,
        place.website,
        place.international_phone_number,
        os.environ.get('NOTIFY_EMAIL'),
        'Subscriber',
        '',
        ''
    ]


def is_filters_exclude(place_website_content, filters_exclude_list):
    for exclude in filters_exclude_list:
        search = re.search(r'[^"\r\n]*' + str(exclude) + '[^"\r\n]*', place_website_content)
        if search:
            return True
    return False


def is_filters_include(place_website_content, filters_include_list):
    for include in filters_include_list:
        search = re.search(r'[^"\r\n]*' + str(include) + '[^"\r\n]*', place_website_content)
        if search:
            return True
    return False


def send_error(user):
    toaddr = os.environ.get('ERROR_EMAIL')

    subject = '{user} had a FATAL ERROR!'.format(user=str(user))
    body = "Look into heroku logs and notify user"
    send_mail(toaddr, subject, body)


if __name__ == '__main__':
    scrape()

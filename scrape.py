from googleplaces import GooglePlaces, types, lang
import json
import csv
from time import sleep
import boto
from boto.s3.key import Key
import requests
import sys
import re
import os
from send_mail import *

def scrape(query, city, filters_exclude, filters_include, max_leads, user, uid):
    results = []
    results.append(['Name', 'Website URL', 'Phone Number', 'Company owner', 'Lifecycle stage'])

    query_list = query.split(',')
    city_list = city.split(',')
    filters_exclude_list = filters_exclude.split(',')
    filters_exclude_list = [x.strip() for x in filters_exclude_list]
    filters_include_list = filters_include.split(',')
    filters_include_list = [x.strip() for x in filters_include_list]
    
    if filters_exclude == '':
        filters_exclude_list = 0
        
    if filters_include == '':
        filters_include_list = 0

    # load <user>.csv from S3 and append to [] list

    user_place_ids = []

    boto_key = os.environ['AWS_S3_KEY']
    boto_s_key = os.environ['AWS_S3_SECRET']

    conn = boto.connect_s3(boto_key, boto_s_key, host=os.environ['AWS_S3_DOMAIN'])

    bucket = conn.get_bucket(os.environ['AWS_S3_BUCKET'])

    k = Key(bucket)
    
    lead_count = 0

    try:
        k.key = str(user) + '.csv'
        k.get_contents_to_filename(str(user) + '.csv')
        with open(str(user) + '.csv', 'r', errors='ignore') as f:
            reader = csv.reader(f)
            for row in reader:
                user_place_ids.append(row[0])
    except:
        # first user submit and therefore no file yet
        user_place_ids = []
    
    ##### ACTUAL SCRAPING BEGINS ####
    for city in city_list:
        
        print('next city of', len(city_list), 'cities')
            
        for query in query_list:
            
            print('next query of', len(query_list), 'queries')

            YOUR_API_KEY = os.environ['GP_API_KEY2']
            google_places = GooglePlaces(YOUR_API_KEY)

            try:
                query_result = google_places.nearby_search(keyword=query, radius=int(os.environ.get('SEARCH_RADIUS')), location=city)
            except:
                sleep(30)
                try:
                    query_result = google_places.nearby_search(keyword=query, radius=int(os.environ.get('SEARCH_RADIUS')), location=city)
                except:
                    try:
                        YOUR_API_KEY = os.environ['GP_API_KEY1']
                        google_places = GooglePlaces(YOUR_API_KEY)
                        query_result = google_places.nearby_search(keyword=query, radius=int(os.environ.get('SEARCH_RADIUS')), location=city)
                    except:
                        send_error(user)

            for place in query_result.places:

                place.get_details()

                if place.website != None:
                    
                    if filters_exclude_list != 0:
                        if any(word.strip().lower() in place.name.lower() for word in filters_exclude_list):
                            print('exclude full continue')
                            continue

                    base_url = place.website.replace('https://', '').replace('http://', '').replace('www.', '')
                    base_url = base_url[:base_url.find('/')]
                    
                    if base_url in user_place_ids:
                        continue
                    else:
                        user_place_ids.append(base_url)

                    results.append([place.name, place.website, place.international_phone_number, 'duarte.lucena@everystay.com', 'Subscriber'])


    final_results = []
    
    if filters_exclude_list != 0:
        for result in results:
            if 'http://' in result[1]:
                pass
            else:
                final_results.append(result)
                continue
                
            try:
                page = requests.get(result[1])
                text = page.text
                
                # FILTERS
                
                excl_filters = []
                incl_filters = []
                
                if filters_exclude_list != 0:
                    for exclude in filters_exclude_list:
                        search = re.search(r'[^"\r\n]*' + str(exclude) + '[^"\r\n]*', text)
                        if search == None:
                            print('exclude filter found nothing with filter:', exclude)
                            pass
                        else:
                            print('exclude filter found something with filter:', exclude)
                            excl_filters.append(search)
                            
                if filters_include_list != 0:
                    for include in filters_include_list:
                        search = re.search(r'[^"\r\n]*' + str(include) + '[^"\r\n]*', text)
                        if search == None:
                            print('include filter found nothing with filter:', include)
                            pass
                        else:
                            print('include filter found something with filter:', include)
                            incl_filters.append(search)
                            
                if filters_exclude_list != 0 and len(excl_filters) > 0:
                    print('exclude full continue')
                    continue
                    
                if filters_include_list != 0 and len(incl_filters) == 0:
                    print('include full continue')
                    continue

            except Exception as e:
                print('Error on line {}'.format(sys.exc_info()[-1].tb_lineno), type(e).__name__, e)
                final_results.append(result)
                lead_count += 1
                print('Lead count:', lead_count)
                continue
                
            lead_count += 1
            print('Lead count:', lead_count)

            final_results.append(result)
    else:
        final_results = results

                    
    # append place.place_ids to user_place_ids on S3 bucket
    with open(str(user) + '.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        for result in user_place_ids:
            writer.writerow([result])

    # send to S3
    k.key = str(user) + '.csv'
    k.set_contents_from_filename(str(user) + '.csv')

    print("Sent to S3")

    # create file that will be send to user and admin (in BCC)
    with open(str(user) + str(uid) + '_leads.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        for result in final_results:
            writer.writerow(result)


def send_error(user):
    toaddr = os.environ.get('ERROR_EMAIL')

    subject = '{user} had a FATAL ERROR!'.format(user=str(user))
    body = "Look into heroku logs and notify user"
    send_mail(toaddr, subject, body)

if __name__ == '__main__':
    scrape()

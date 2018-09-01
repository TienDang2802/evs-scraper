from googleplaces import GooglePlaces, types, lang
import http.client, urllib.request, urllib.parse, urllib.error, base64
from validate_email import validate_email
from urllib.request import urlopen
import json
import csv
from bs4 import BeautifulSoup
from time import sleep
import boto
from boto.s3.key import Key
import requests
import sys
import re
import os
from send_mail import *

def scrape(query, city, place_type, filters_exclude, filters_include, max_leads, user, uid):
    results = []
    results.append(['Name', 'Meta Title', 'Address', 'Website', 'E-Mail', 'Phone Number', 'Google Rating (0-5)', 'Facebook', 'Twitter', 'LinkedIn', 'Instagram'])

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
    lead_count = 0

    boto_key = os.environ['AWS_S3_KEY']
    boto_s_key = os.environ['AWS_S3_SECRET']

    conn = boto.connect_s3(boto_key, boto_s_key, host=os.environ['AWS_S3_DOMAIN'])

    bucket = conn.get_bucket(os.environ['AWS_S3_BUCKET'])

    k = Key(bucket)

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

    # TODO
    # use JSON instead of messy csv method - maybe later haha :D
    # scrape meta descriptions
    # use meta title and description for filtering as well

    ####### Looking for country args ##########
    # Hint: don't look into this code, it's cringy AF

    indexes = []

    with open('countries.csv', 'r', errors='ignore') as g:
        reader = csv.reader(g, delimiter=",")
        header = next(reader)
        for i in range(len(header)):
            for city in city_list:
                if city.strip().lower() in header[i]:
                    indexes.append(i)

    ###### Appending cities of found country args ########

    with open('countries.csv', 'r', errors='ignore') as g:
        reader = csv.reader(g, delimiter=",")
        next(reader)
        for row in reader:
            for i in indexes:
                if row[i] != 'flop':
                    city_list.append(row[i])

    ##### ACTUAL SCRAPING BEGINS ####
    #while len(results) <= int(max_leads):
    
    addresses = []

    for city in city_list:
        if len(results) > int(max_leads):
            break
            
        for query in query_list:
            if len(results) > int(max_leads):
                break

            YOUR_API_KEY = os.environ['GP_API_KEY2']
            google_places = GooglePlaces(YOUR_API_KEY)

            try:
                if place_type != 'choose':
                    query_result = google_places.nearby_search(keyword=query, radius=int(os.environ.get('SEARCH_RADIUS')), location=city, types=[place_type])
                else:
                    query_result = google_places.nearby_search(keyword=query, radius=int(os.environ.get('SEARCH_RADIUS')), location=city)
            except Exception as e:
                print(e)
                print("Geocoding API failed. Now sleeping for 1.5min")
                sleep(90)
                try:
                    if place_type != 'choose':
                        query_result = google_places.nearby_search(keyword=query, radius=int(os.environ.get('SEARCH_RADIUS')), location=city, types=[place_type])
                    else:
                        query_result = google_places.nearby_search(keyword=query, radius=int(os.environ.get('SEARCH_RADIUS')), location=city)
                except:
                    try:
                        YOUR_API_KEY = os.environ['GP_API_KEY1']
                        google_places = GooglePlaces(YOUR_API_KEY)
                        if place_type != 'choose':
                            query_result = google_places.nearby_search(keyword=query, radius=int(os.environ.get('SEARCH_RADIUS')), location=city, types=[place_type])
                        else:
                            query_result = google_places.nearby_search(keyword=query, radius=int(os.environ.get('SEARCH_RADIUS')), location=city)
                    except:
                        send_error(user)

            for place in query_result.places:
                
                if len(results) > int(max_leads):
                    break

                if place.place_id in user_place_ids:
                    continue
                else:
                    user_place_ids.append(place.place_id)
                
                try:
                    place.get_details()
                except:
                    continue
                
                if place.formatted_address in addresses:
                    continue
                else:
                    addresses.append(place.formatted_address)

                if place.website != None:

                    # Skips results that don't have the city in the result but only if it wasn't a country wide search
                    if len(indexes) == 0 and city.strip().lower() not in place.formatted_address.lower():
                        continue

                    base_url = place.website.replace('https://', '').replace('http://', '').replace('www.', '')
                    base_url = base_url[:base_url.find('/')]

                    try: # if this block fails, append everything that's not on the website
                        page = requests.get(place.website)
                        soup = BeautifulSoup(page.content, 'html.parser')
                        text = page.text

                        try:
                            title = soup.find('title').text.strip()
                        except:
                            title = 'n/a'
                        
                        # FILTERS
                        
                        excl_filters = []
                        incl_filters = []
                        
                        if filters_exclude_list != 0:
                            if any(word.strip().lower() in place.name.lower() for word in filters_exclude_list):
                                print('exclude full continue')
                                continue
                            for exclude in filters_exclude_list:
                                search = re.search(r'[^"\r\n]*' + str(exclude) + '[^"\r\n]*', text)
                                if search == None:
                                    print('exclude filter found nothing with filter:', exclude)
                                    pass
                                else:
                                    print('exclude filter found somehing with filter:', exclude)
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
                            
                        # don't forget meta description, title and name filters

                        # FILTERS END

                        try:
                            fb_all = soup.find_all(href=re.compile(r'[^"\r\n]*' + 'facebook.com' + '[^"\r\n]*'))
                            facebook = []

                            for fb in fb_all:
                                if 'share' in fb['href']:
                                    pass
                                else:
                                    facebook.append(fb['href'])
                            facebook = facebook[0]
                        except:
                            facebook = 'n/a'
                        try:
                            tw_all = soup.find_all(href=re.compile(r'[^"\r\n]*' + 'twitter.com' + '[^"\r\n]*'))
                            twitter = []

                            for tw in tw_all:
                                if 'share' in tw['href']:
                                    pass
                                elif 'tweet' in tw['href']:
                                    pass
                                else:
                                    twitter.append(tw['href'])
                            twitter = twitter[0]
                        except:
                            twitter = 'n/a'
                        try:
                            lkn_all = soup.find_all(href=re.compile(r'[^"\r\n]*' + 'linkedin' + '[^"\r\n]*'))
                            
                            linkedin = []

                            for lkn in lkn_all:
                                if 'share' in lkn['href']:
                                    pass
                                else:
                                    linkedin.append(lkn['href'])
                            linkedin = linkedin[0]
                        except:
                            linkedin = 'n/a'
                        try:
                            instagram = soup.find(href=re.compile(r'[^"\r\n]*' + 'instagram.com' + '[^"\r\n]*'))['href']
                        except:
                            instagram = 'n/a'

                        # refine
                        try:
                            email = re.findall(r"[A-Za-z0-9._%+-]+@" + base_url, text)
                            email = email[0]

                        except Exception as e:
                            print('Email not found on main page')
                            email = 'n/a'

                        if email == 'n/a' and validate_email('info@' + base_url ,verify=True) == True:
                            email = 'info@' + base_url
                        else:
                            try:
                                try:
                                    result = soup.find('a', text=re.compile(r'[^"\r\n]*' + 'mpressum' + '[^"\r\n]*'))['href']
                                except:
                                    try:
                                        result = soup.find('a', text=re.compile(r'[^"\r\n]*' + 'ontact' + '[^"\r\n]*'))['href']
                                    except Exception as e:
                                        print('Error on line {}'.format(sys.exc_info()[-1].tb_lineno), type(e).__name__, e)
                                        email = 'n/a'
                                        results.append([place.name, title, place.formatted_address, place.website, email, place.international_phone_number, place.rating, facebook, twitter, linkedin, instagram])
                                        lead_count += 1
                                        print('Found', lead_count)
                                        continue

                                count = result.count('/')

                                if base_url in result and 'http' not in result and 'https' not in result:
                                    impressum = 'http://' + result
                                elif base_url not in result and count >= 1 and result[0] != '/':
                                    impressum = "http://" + base_url + '/' + result
                                elif base_url not in result and count >= 1 and result[0] == '/':
                                    impressum = "http://" + base_url + result
                                elif base_url not in result and count == 0:
                                    impressum = "http://" + base_url + '/' + result
                                elif "http" in result or "https" in result:
                                    impressum = result
                                else:
                                    pass

                                r = requests.get(impressum)
                                text2 = r.text
                                
                                try:
                                    email = re.findall(r"[A-Za-z0-9._%+-]+@" + base_url, text2)
                                    email = email[0]
                                except:
                                    email = 'n/a'
                                    results.append([place.name, title, place.formatted_address, place.website, email, place.international_phone_number, place.rating, facebook, twitter, linkedin, instagram])
                                    lead_count += 1
                                    print('Found', lead_count)
                                    continue

                            except Exception as e:
                                print('1st exception. Error on line {}'.format(sys.exc_info()[-1].tb_lineno), type(e).__name__, e)
                                email = 'n/a'
                                results.append([place.name, title, place.formatted_address, place.website, email, place.international_phone_number, place.rating, facebook, twitter, linkedin, instagram])
                                lead_count += 1
                                print('Found', lead_count)
                                continue

                    except Exception as e:
                        print('2nd exception. Error on line {}'.format(sys.exc_info()[-1].tb_lineno), type(e).__name__, e)
                        results.append([place.name, 'n/a', place.formatted_address, place.website, "n/a", place.international_phone_number, place.rating, "n/a", "n/a", "n/a", "n/a"])
                        lead_count += 1
                        print('Found', lead_count)
                        continue
                        
                    lead_count += 1
                    print('Found', lead_count)
                    results.append([place.name, title, place.formatted_address, place.website, email, place.international_phone_number, place.rating, facebook, twitter, linkedin, instagram])

    # append place.place_ids to user_place_ids on S3 bucket
    with open(str(user) + '.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        for result in user_place_ids:
            writer.writerow([result])

    # send to S3
    k.key = str(user) + '.csv'
    k.set_contents_from_filename(str(user) + '.csv')

    # create file that will be send to user and admin (in BCC)
    with open(str(user) + str(uid) + '_leads.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        for result in results:
            writer.writerow(result)

def send_error(user):
        toaddr = os.environ.get('ERROR_EMAIL')

        subject = '{user} had a FATAL ERROR!'.format(user=str(user))
        body = "Look into heroku logs and notify user"
        send_mail(toaddr, subject, body)

if __name__ == '__main__':
    scrape()
